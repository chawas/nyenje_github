#!/usr/bin/env python3
"""
SWAN Output Processor for Lake Kariba - Version 2
Parses NOHEADER LAYOUT 4 output format
"""

import numpy as np
import datetime
import re
import sys
from pathlib import Path

# Configuration
GRID_X = 9   # number of points in X direction (West-East)
GRID_Y = 8   # number of points in Y direction (South-North)
DOMAIN_X = 4000.0  # meters
DOMAIN_Y = 3500.0  # meters
WIND_SPEED = 10.0  # m/s
WIND_DIRECTION = 90.0  # degrees (East wind)

def parse_swan_output_nobeader(filename):
    """
    Parse SWAN NOHEADER LAYOUT 4 output format.
    LAYOUT 4 writes each value on a new line.
    Format: HSIGN values (GRID_X*GRID_Y lines), then TM01, then DIR
    """
    
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Remove empty lines and strip whitespace
    numbers = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('!'):
            try:
                # Handle scientific notation
                num = float(line)
                numbers.append(num)
            except ValueError:
                continue
    
    print(f"Found {len(numbers)} numbers in file")
    
    expected = GRID_X * GRID_Y * 3
    if len(numbers) != expected:
        print(f"Warning: Expected {expected} numbers, got {len(numbers)}")
        print(f"Attempting to continue with available data...")
    
    # Split into three blocks
    points_per_grid = GRID_X * GRID_Y
    
    if len(numbers) >= points_per_grid:
        hs_block = numbers[0:points_per_grid]
    else:
        print("Error: Not enough data for HSIGN")
        return None, None, None
    
    if len(numbers) >= 2 * points_per_grid:
        tm_block = numbers[points_per_grid:2*points_per_grid]
    else:
        tm_block = [0] * points_per_grid
    
    if len(numbers) >= 3 * points_per_grid:
        dir_block = numbers[2*points_per_grid:3*points_per_grid]
    else:
        dir_block = [0] * points_per_grid
    
    # Reshape to grid (Y rows, X columns)
    hs_grid = np.array(hs_block[:points_per_grid]).reshape(GRID_Y, GRID_X)
    tm_grid = np.array(tm_block[:points_per_grid]).reshape(GRID_Y, GRID_X)
    dir_grid = np.array(dir_block[:points_per_grid]).reshape(GRID_Y, GRID_X)
    
    return hs_grid, tm_grid, dir_grid

def create_coordinates():
    """Create X and Y coordinates for grid points"""
    x_coords = np.linspace(0, DOMAIN_X, GRID_X)
    y_coords = np.linspace(0, DOMAIN_Y, GRID_Y)
    return x_coords, y_coords

def generate_summary_table(hs_grid, tm_grid, dir_grid):
    """Generate wave height summary table"""
    
    hs_flat = hs_grid.flatten()
    tm_flat = tm_grid.flatten()
    dir_flat = dir_grid.flatten()
    
    # Remove zeros (land points)
    valid = hs_flat > 0.001
    hs_valid = hs_flat[valid]
    tm_valid = tm_flat[valid]
    dir_valid = dir_flat[valid]
    
    if len(hs_valid) == 0:
        return "No valid wave data found!"
    
    summary = f"""
{'='*70}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*70}
Run Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}° (East wind)
Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km
Grid: {GRID_X} × {GRID_Y} points ({DOMAIN_X/(GRID_X-1):.0f} m resolution)
{'='*70}

┌─────────────────────┬─────────────┬──────────────────────────────────────────┐
│ Statistic           │ Value       │ Interpretation                           │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Hs          │ {hs_valid.min():8.4f} m  │ {hs_valid.min()*100:.2f} cm                                    │
│ Maximum Hs          │ {hs_valid.max():8.4f} m  │ {hs_valid.max()*100:.2f} cm                                    │
│ Mean Hs             │ {hs_valid.mean():8.4f} m  │ {hs_valid.mean()*100:.2f} cm                                    │
│ Median Hs           │ {np.median(hs_valid):8.4f} m  │                                                          │
│ Std Dev Hs          │ {hs_valid.std():8.4f} m  │                                                          │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Tm01        │ {tm_valid.min():8.2f} s   │                                                          │
│ Maximum Tm01        │ {tm_valid.max():8.2f} s   │                                                          │
│ Mean Tm01           │ {tm_valid.mean():8.2f} s   │                                                          │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum DIR         │ {dir_valid.min():8.1f}°   │                                                          │
│ Maximum DIR         │ {dir_valid.max():8.1f}°   │                                                          │
│ Mean DIR            │ {dir_valid.mean():8.1f}°   │                                                          │
└─────────────────────┴─────────────┴──────────────────────────────────────────┘
"""
    return summary

def generate_grid_tables(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    """Generate formatted grid tables"""
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Helper to create table
    def make_table(title, unit, grid, fmt):
        table = f"""
{'='*70}
{title} - {unit}
{'='*70}
Time: {timestamp}
Rows: North (top) to South (bottom)
Columns: West (left) to East (right)
{'='*70}

{'Y (km)':>8} |"""
        for x in x_coords:
            table += f" {x/1000:6.1f}km |"
        table += "\n" + "-" * (12 + 11 * GRID_X) + "\n"
        
        for i in range(GRID_Y):
            table += f"{y_coords[i]/1000:8.1f} |"
            for j in range(GRID_X):
                table += f" {grid[i,j]:{fmt}} |"
            table += "\n"
        return table
    
    hs_table = make_table("SIGNIFICANT WAVE HEIGHT", "meters", hs_grid, "7.4f")
    tm_table = make_table("MEAN WAVE PERIOD", "seconds", tm_grid, "6.2f")
    dir_table = make_table("MEAN WAVE DIRECTION", "degrees (Nautical)", dir_grid, "6.1f")
    
    return hs_table, tm_table, dir_table

def generate_visual_map(hs_grid, y_coords):
    """Generate ASCII visual map of wave heights"""
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    map_str = f"""
{'='*70}
WAVE HEIGHT VISUAL MAP (HSIGN in meters)
{'='*70}
Time: {timestamp}
Wind: {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (→ → → East wind)
North is TOP of map
{'='*70}

                    NORTH (Y={y_coords[-1]/1000:.1f} km)
    ┌─────────────────────────────────────────────────────────────────┐
"""
    
    # Add rows from North to South
    for i in range(GRID_Y):
        row_str = "    │"
        for j in range(GRID_X):
            hs_val = hs_grid[i, j]
            if hs_val < 0.01:
                row_str += "  0.000  "
            else:
                row_str += f" {hs_val:6.3f} "
        row_str += "│"
        
        # Add annotation
        if i == 0:
            row_str += " ← North shore (very shallow, wave breaking)"
        elif i == GRID_Y - 1:
            row_str += " ← South shore"
        elif i == GRID_Y // 2:
            row_str += f" ← Center (max: {hs_grid[i].max():.3f}m)"
        
        map_str += row_str + "\n"
    
    map_str += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH (Y={y_coords[0]/1000:.1f} km)
    
    WIND → → → → → {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (East wind)

Note: Values are in meters. Very small values (< 0.01 m) indicate wave breaking in shallow areas.
"""
    return map_str

def generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    """Generate CSV file for easy import into Excel/spreadsheet"""
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'kariba_wave_data_{timestamp}.csv'
    
    with open(csv_filename, 'w') as f:
        f.write(f"# SWAN Wave Data - Lake Kariba Nyenje\n")
        f.write(f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}°\n")
        f.write(f"# Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km\n")
        f.write(f"# Grid: {GRID_X} × {GRID_Y} points\n")
        f.write("\nX_km,Y_km,HSIGN_m,TM01_s,DIR_deg\n")
        
        for i in range(GRID_Y):
            for j in range(GRID_X):
                f.write(f"{x_coords[j]/1000:.2f},{y_coords[i]/1000:.2f},")
                f.write(f"{hs_grid[i,j]:.4f},{tm_grid[i,j]:.2f},{dir_grid[i,j]:.1f}\n")
    
    print(f"CSV file saved as: {csv_filename}")
    return csv_filename

def generate_point_table(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    """Generate table of all grid points"""
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    table = f"""
{'='*70}
POINT-BY-POINT DATA TABLE
{'='*70}
Time: {timestamp}
{'='*70}

{'Point':>5} | {'X (km)':>8} | {'Y (km)':>8} | {'HSIGN (m)':>10} | {'TM01 (s)':>8} | {'DIR (deg)':>8}
{'-'*5}-+-{'-'*8}-+-{'-'*8}-+-{'-'*10}-+-{'-'*8}-+-{'-'*8}
"""
    
    point_num = 1
    for i in range(GRID_Y):
        for j in range(GRID_X):
            table += f"{point_num:5d} | {x_coords[j]/1000:8.2f} | {y_coords[i]/1000:8.2f} | "
            table += f"{hs_grid[i,j]:10.4f} | {tm_grid[i,j]:8.2f} | {dir_grid[i,j]:8.1f}\n"
            point_num += 1
    
    return table

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'kariba_output.txt'
    
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found!")
        print("Usage: python process_swan_output_v2.py [output.txt]")
        sys.exit(1)
    
    print(f"Processing SWAN output from: {input_file}")
    
    # Parse the SWAN output
    hs_grid, tm_grid, dir_grid = parse_swan_output_nobeader(input_file)
    
    if hs_grid is None:
        print("Failed to parse output file!")
        sys.exit(1)
    
    print(f"Successfully parsed {GRID_X}x{GRID_Y} grid")
    print(f"HSIGN range: {hs_grid.min():.4f} - {hs_grid.max():.4f} m")
    
    # Create coordinates
    x_coords, y_coords = create_coordinates()
    
    # Generate all outputs
    summary = generate_summary_table(hs_grid, tm_grid, dir_grid)
    hs_table, tm_table, dir_table = generate_grid_tables(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    visual_map = generate_visual_map(hs_grid, y_coords)
    point_table = generate_point_table(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    csv_file = generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    
    # Write complete report
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f'kariba_wave_report_{timestamp}.txt'
    
    with open(report_filename, 'w') as f:
        f.write(summary)
        f.write(hs_table)
        f.write(tm_table)
        f.write(dir_table)
        f.write(point_table)
        f.write(visual_map)
    
    print(f"\n{'='*70}")
    print(f"REPORT GENERATED SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"Report saved as: {report_filename}")
    print(f"CSV data saved as: {csv_file}")
    
    # Print summary to screen
    print(summary)
    print(visual_map)

if __name__ == "__main__":
    main()