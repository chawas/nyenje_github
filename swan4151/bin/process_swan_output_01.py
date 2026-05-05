#!/usr/bin/env python3
"""
SWAN Output Processor for Lake Kariba
Converts raw SWAN output to formatted tables with date/time
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

def parse_swan_output(filename):
    """Parse SWAN block output file with HEADER"""
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Find blocks by looking for variable names in headers
    # SWAN HEADER format has lines with variable names
    
    # Extract numeric values (scientific notation)
    pattern = r'[-+]?\d+\.\d+E[+-]\d+'
    all_numbers = re.findall(pattern, content)
    
    if len(all_numbers) < GRID_X * GRID_Y * 3:
        print(f"Warning: Found {len(all_numbers)} numbers, expected {GRID_X * GRID_Y * 3}")
        print("Trying alternative parsing...")
        
        # Alternative: parse line by line
        all_numbers = []
        for line in content.split('\n'):
            # Skip header lines
            if line.strip().startswith('$') or line.strip().startswith('PROJECT'):
                continue
            if line.strip() == '':
                continue
            # Extract numbers from line
            nums = re.findall(r'[-+]?\d+\.\d+E[+-]\d+', line)
            all_numbers.extend(nums)
    
    numbers = [float(x) for x in all_numbers]
    
    # First block: HSIGN (GRID_X * GRID_Y values)
    hs_block = numbers[0:GRID_X * GRID_Y]
    # Second block: TM01 (next GRID_X * GRID_Y values)
    tm_block = numbers[GRID_X * GRID_Y:2 * GRID_X * GRID_Y]
    # Third block: DIR (next GRID_X * GRID_Y values)
    dir_block = numbers[2 * GRID_X * GRID_Y:3 * GRID_X * GRID_Y]
    
    # Reshape to grid (Y rows, X columns)
    hs_grid = np.array(hs_block).reshape(GRID_Y, GRID_X)
    tm_grid = np.array(tm_block).reshape(GRID_Y, GRID_X)
    dir_grid = np.array(dir_block).reshape(GRID_Y, GRID_X)
    
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
    
    summary = f"""
{'='*70}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*70}
Run Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}° (East wind)
Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km
Grid: {GRID_X} × {GRID_Y} points ({DOMAIN_X/(GRID_X-1):.0f} m resolution)
{'='*70}

┌─────────────────┬─────────────┬────────────────────────────────────┐
│ Statistic       │ Value       │ Interpretation                     │
├─────────────────┼─────────────┼────────────────────────────────────┤
│ Minimum Hs      │ {hs_valid.min():6.4f} m  │ {hs_valid.min()*100:.2f} cm - very shallow/protected area │
│ Maximum Hs      │ {hs_valid.max():6.4f} m  │ {hs_valid.max()*100:.2f} cm                                 │
│ Mean Hs         │ {hs_valid.mean():6.4f} m  │ {hs_valid.mean()*100:.2f} cm                                 │
│ Median Hs       │ {np.median(hs_valid):6.4f} m  │                                        │
│ Std Dev Hs      │ {hs_valid.std():6.4f} m  │                                        │
├─────────────────┼─────────────┼────────────────────────────────────┤
│ Minimum Tm01    │ {tm_valid.min():6.2f} s   │                                        │
│ Maximum Tm01    │ {tm_valid.max():6.2f} s   │                                        │
│ Mean Tm01       │ {tm_valid.mean():6.2f} s   │                                        │
├─────────────────┼─────────────┼────────────────────────────────────┤
│ Minimum DIR     │ {dir_valid.min():6.1f}°   │                                        │
│ Maximum DIR     │ {dir_valid.max():6.1f}°   │                                        │
│ Mean DIR        │ {dir_valid.mean():6.1f}°   │                                        │
└─────────────────┴─────────────┴────────────────────────────────────┘
"""
    return summary

def generate_grid_table(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    """Generate formatted grid tables"""
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Significant Wave Height Table
    hs_table = f"""
{'='*70}
SIGNIFICANT WAVE HEIGHT (HSIGN) - meters
{'='*70}
Time: {timestamp}
Rows: North (top) to South (bottom)
Columns: West (left) to East (right)
{'='*70}

"""
    # Add header row with X coordinates
    hs_table += "     Y\\X    |"
    for x in x_coords:
        hs_table += f" {x/1000:5.1f}km |"
    hs_table += "\n" + "-" * (12 + 9 * GRID_X) + "\n"
    
    for i in range(GRID_Y):
        hs_table += f" {y_coords[i]/1000:8.1f}km |"
        for j in range(GRID_X):
            hs_table += f" {hs_grid[i,j]:7.4f} |"
        hs_table += "\n"
    
    # Mean Wave Period Table
    tm_table = f"""
{'='*70}
MEAN WAVE PERIOD (TM01) - seconds
{'='*70}
Time: {timestamp}
{'='*70}

     Y\\X    |"""
    for x in x_coords:
        tm_table += f" {x/1000:5.1f}km |"
    tm_table += "\n" + "-" * (12 + 9 * GRID_X) + "\n"
    
    for i in range(GRID_Y):
        tm_table += f" {y_coords[i]/1000:8.1f}km |"
        for j in range(GRID_X):
            tm_table += f" {tm_grid[i,j]:7.2f} |"
        tm_table += "\n"
    
    # Wave Direction Table
    dir_table = f"""
{'='*70}
MEAN WAVE DIRECTION (DIR) - degrees (Nautical: where waves come from)
{'='*70}
Time: {timestamp}
{'='*70}

     Y\\X    |"""
    for x in x_coords:
        dir_table += f" {x/1000:5.1f}km |"
    dir_table += "\n" + "-" * (12 + 9 * GRID_X) + "\n"
    
    for i in range(GRID_Y):
        dir_table += f" {y_coords[i]/1000:8.1f}km |"
        for j in range(GRID_X):
            dir_table += f" {dir_grid[i,j]:7.1f} |"
        dir_table += "\n"
    
    return hs_table, tm_table, dir_table

def generate_visual_map(hs_grid, y_coords):
    """Generate ASCII visual map of wave heights"""
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    map_str = f"""
{'='*70}
WAVE HEIGHT VISUAL MAP
{'='*70}
Time: {timestamp}
Wind: {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (→ → → East wind)
North is TOP of map
{'='*70}

                    NORTH (Y={y_coords[-1]/1000:.1f} km)
    ┌─────────────────────────────────────────────────────────┐
"""
    
    # Add rows from North to South
    for i in range(GRID_Y):
        row_str = "    │"
        for j in range(GRID_X):
            hs_val = hs_grid[i, j]
            if hs_val < 0.01:
                row_str += "   ~0   "
            elif hs_val < 0.10:
                row_str += f" {hs_val:5.3f} "
            else:
                row_str += f" {hs_val:5.3f} "
        row_str += "│"
        
        # Add annotation for first and last rows
        if i == 0:
            row_str += " ← Very small waves (shallow north shore)"
        elif i == GRID_Y - 1:
            row_str += " ← South shore (deeper water)"
        elif i == GRID_Y // 2:
            row_str += f" ← Center (max Hs: {hs_grid[i].max():5.3f}m)"
        
        map_str += row_str + "\n"
    
    map_str += f"""    └─────────────────────────────────────────────────────────┘
                    SOUTH (Y={y_coords[0]/1000:.1f} km)
    WIND → → → → → {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (East wind)

Legend:
  ~0   = negligible waves (< 0.01 m)
  0.xxx = wave height in meters
"""
    
    return map_str

def generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords, filename='wave_data.csv'):
    """Generate CSV file for easy import into Excel/spreadsheet"""
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'wave_data_{timestamp}.csv'
    
    with open(csv_filename, 'w') as f:
        f.write(f"# SWAN Wave Data - Lake Kariba Nyenje\n")
        f.write(f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}°\n")
        f.write(f"# Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km\n")
        f.write(f"# Grid: {GRID_X} × {GRID_Y} points\n")
        f.write("\n# X (km), Y (km), HSIGN (m), TM01 (s), DIR (deg)\n")
        
        for i in range(GRID_Y):
            for j in range(GRID_X):
                f.write(f"{x_coords[j]/1000:.2f}, {y_coords[i]/1000:.2f}, ")
                f.write(f"{hs_grid[i,j]:.4f}, {tm_grid[i,j]:.2f}, {dir_grid[i,j]:.1f}\n")
    
    print(f"CSV file saved as: {csv_filename}")
    return csv_filename

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'kariba_output.raw'
    
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found!")
        print("Usage: python process_swan_output.py [output_file.raw]")
        sys.exit(1)
    
    print(f"Processing SWAN output from: {input_file}")
    
    # Parse the SWAN output
    hs_grid, tm_grid, dir_grid = parse_swan_output(input_file)
    
    # Create coordinates
    x_coords, y_coords = create_coordinates()
    
    # Generate all outputs
    summary = generate_summary_table(hs_grid, tm_grid, dir_grid)
    hs_table, tm_table, dir_table = generate_grid_tables(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    visual_map = generate_visual_map(hs_grid, y_coords)
    csv_file = generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    
    # Write complete report
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f'kariba_wave_report_{timestamp}.txt'
    
    with open(report_filename, 'w') as f:
        f.write(summary)
        f.write(hs_table)
        f.write(tm_table)
        f.write(dir_table)
        f.write(visual_map)
    
    print(f"\n{'='*70}")
    print(f"REPORT GENERATED SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"Report saved as: {report_filename}")
    print(f"CSV data saved as: {csv_file}")
    print(f"\n{summary}")
    print(f"\n{visual_map}")

if __name__ == "__main__":
    main()