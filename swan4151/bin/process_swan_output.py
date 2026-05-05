#!/usr/bin/env python3
"""
SWAN Output Processor for HEADER format
Parses the output from BLOCK with HEADER option
"""

import numpy as np
import datetime
import re
import sys
from pathlib import Path

# Configuration
GRID_X = 9   # number of points in X direction
GRID_Y = 8   # number of points in Y direction
DOMAIN_X = 4000.0  # meters
DOMAIN_Y = 3500.0  # meters
WIND_SPEED = 10.0  # m/s
WIND_DIRECTION = 90.0  # degrees

def parse_swan_header_output(filename):
    """
    Parse SWAN BLOCK output with HEADER option.
    The format has header lines followed by data in scientific notation.
    """
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Find all numbers in scientific notation
    # Pattern matches: 0.6848E-02, 0.1804E+00, etc.
    pattern = r'[-+]?\d+\.\d+E[+-]\d+'
    numbers = re.findall(pattern, content)
    
    print(f"Found {len(numbers)} numbers in file")
    
    if len(numbers) == 0:
        # Try alternative pattern for regular decimals
        pattern2 = r'[-+]?\d+\.\d+'
        numbers = re.findall(pattern2, content)
        print(f"Found {len(numbers)} decimal numbers")
    
    # Convert to float
    floats = [float(x) for x in numbers]
    
    expected = GRID_X * GRID_Y * 3
    if len(floats) < expected:
        print(f"Warning: Expected {expected} numbers, got {len(floats)}")
        print("This might be because the file has headers that were filtered out")
        
        # Try to read line by line
        return parse_line_by_line(filename)
    
    # Split into three blocks
    n_per_grid = GRID_X * GRID_Y
    hs = floats[0:n_per_grid]
    tm = floats[n_per_grid:2*n_per_grid]
    direc = floats[2*n_per_grid:3*n_per_grid]
    
    # Reshape
    hs_grid = np.array(hs).reshape(GRID_Y, GRID_X)
    tm_grid = np.array(tm).reshape(GRID_Y, GRID_X)
    dir_grid = np.array(direc).reshape(GRID_Y, GRID_X)
    
    return hs_grid, tm_grid, dir_grid

def parse_line_by_line(filename):
    """Alternative parser: read line by line and extract numbers"""
    
    numbers = []
    with open(filename, 'r') as f:
        for line in f:
            # Skip comment lines
            if line.strip().startswith('$') or line.strip().startswith('PROJECT'):
                continue
            if line.strip().startswith('MODE') or line.strip().startswith('COORD'):
                continue
            if line.strip().startswith('CGRID') or line.strip().startswith('INPGRID'):
                continue
            if line.strip().startswith('WIND') or line.strip().startswith('GEN3'):
                continue
            if line.strip().startswith('BLOCK') or line.strip().startswith('COMPUTE'):
                continue
            if line.strip().startswith('STOP'):
                continue
            
            # Extract numbers from line
            # Scientific notation
            sci_nums = re.findall(r'[-+]?\d+\.\d+E[+-]\d+', line)
            for num in sci_nums:
                numbers.append(float(num))
            
            # Regular decimals
            dec_nums = re.findall(r'[-+]?\d+\.\d+', line)
            for num in dec_nums:
                # Avoid duplicates if already captured
                if num not in sci_nums:
                    numbers.append(float(num))
    
    print(f"Line-by-line parsing found {len(numbers)} numbers")
    
    expected = GRID_X * GRID_Y * 3
    if len(numbers) >= expected:
        n_per_grid = GRID_X * GRID_Y
        hs = numbers[0:n_per_grid]
        tm = numbers[n_per_grid:2*n_per_grid]
        direc = numbers[2*n_per_grid:3*n_per_grid]
        
        hs_grid = np.array(hs).reshape(GRID_Y, GRID_X)
        tm_grid = np.array(tm).reshape(GRID_Y, GRID_X)
        dir_grid = np.array(direc).reshape(GRID_Y, GRID_X)
        
        return hs_grid, tm_grid, dir_grid
    else:
        print(f"ERROR: Only found {len(numbers)} numbers, need {expected}")
        return None, None, None

def create_coordinates():
    x_coords = np.linspace(0, DOMAIN_X, GRID_X)
    y_coords = np.linspace(0, DOMAIN_Y, GRID_Y)
    return x_coords, y_coords

def generate_summary_table(hs_grid, tm_grid, dir_grid):
    hs_flat = hs_grid.flatten()
    tm_flat = tm_grid.flatten()
    dir_flat = dir_grid.flatten()
    
    valid = hs_flat > 0.001
    hs_valid = hs_flat[valid]
    tm_valid = tm_flat[valid]
    dir_valid = dir_flat[valid]
    
    if len(hs_valid) == 0:
        return "No valid wave data found!"
    
    summary = f"""
{'='*70}
LAKE KARIBA - NYENJE AREA WAVE ANALYSIS
{'='*70}
Run Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}° (East wind)
Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km
Grid: {GRID_X} × {GRID_Y} points
{'='*70}

┌─────────────────────┬─────────────┬──────────────────────────────────────────┐
│ Statistic           │ Value       │ Interpretation                           │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Hs          │ {hs_valid.min():8.4f} m  │ {hs_valid.min()*100:.2f} cm                                    │
│ Maximum Hs          │ {hs_valid.max():8.4f} m  │ {hs_valid.max()*100:.2f} cm                                    │
│ Mean Hs             │ {hs_valid.mean():8.4f} m  │ {hs_valid.mean()*100:.2f} cm                                    │
│ Median Hs           │ {np.median(hs_valid):8.4f} m  │                                                          │
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

def generate_visual_map(hs_grid, y_coords):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Find max value for center annotation
    center_row = GRID_Y // 2
    center_max = hs_grid[center_row].max()
    
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
    
    for i in range(GRID_Y):
        row_str = "    │"
        for j in range(GRID_X):
            hs_val = hs_grid[i, j]
            if hs_val < 0.01:
                row_str += "  0.000  "
            else:
                row_str += f" {hs_val:6.3f} "
        row_str += "│"
        
        if i == 0:
            row_str += " ← North shore (very shallow, wave breaking)"
        elif i == GRID_Y - 1:
            row_str += " ← South shore"
        elif i == center_row:
            row_str += f" ← Center (max: {center_max:.3f}m)"
        
        map_str += row_str + "\n"
    
    map_str += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH (Y={y_coords[0]/1000:.1f} km)
    
    WIND → → → → → {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (East wind)

Note: Values are in meters. Very small values (< 0.01 m) indicate wave breaking in shallow areas.
"""
    return map_str

def generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'kariba_wave_data_{timestamp}.csv'
    
    with open(csv_filename, 'w') as f:
        f.write(f"# SWAN Wave Data - Lake Kariba Nyenje\n")
        f.write(f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}°\n")
        f.write(f"# Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km\n")
        f.write("\nX_km,Y_km,HSIGN_m,TM01_s,DIR_deg\n")
        
        for i in range(GRID_Y):
            for j in range(GRID_X):
                f.write(f"{x_coords[j]/1000:.2f},{y_coords[i]/1000:.2f},")
                f.write(f"{hs_grid[i,j]:.4f},{tm_grid[i,j]:.2f},{dir_grid[i,j]:.1f}\n")
    
    return csv_filename

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'kariba_output.raw'
    
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found!")
        print("Usage: python process_swan_output_header.py [output.raw]")
        sys.exit(1)
    
    print(f"Processing SWAN output from: {input_file}")
    
    hs_grid, tm_grid, dir_grid = parse_swan_header_output(input_file)
    
    if hs_grid is None:
        print("Failed to parse output file!")
        print("\nTrying to read raw file content...")
        with open(input_file, 'r') as f:
            content = f.read()
            print(f"File size: {len(content)} characters")
            print(f"First 500 characters:\n{content[:500]}")
        sys.exit(1)
    
    x_coords, y_coords = create_coordinates()
    
    summary = generate_summary_table(hs_grid, tm_grid, dir_grid)
    visual_map = generate_visual_map(hs_grid, y_coords)
    csv_file = generate_csv_output(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f'nyenje_wave_report_{timestamp}.txt'
    
    with open(report_filename, 'w') as f:
        f.write(summary)
        f.write(visual_map)
    
    print(f"\n{'='*70}")
    print(f"REPORT GENERATED!")
    print(f"{'='*70}")
    print(f"Report: {report_filename}")
    print(f"CSV: {csv_file}")
    print(summary)
    print(visual_map)

if __name__ == "__main__":
    main()