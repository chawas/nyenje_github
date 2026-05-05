#!/usr/bin/env python3
"""
Extract wave height data from SWAN POINTS/GRID output format
"""

import re
import datetime
import numpy as np

# Configuration
GRID_X = 9   # X direction points (West to East)
GRID_Y = 8   # Y direction points (South to North)
DOMAIN_X = 4000.0  # meters
DOMAIN_Y = 3500.0  # meters
WIND_SPEED = 10.0
WIND_DIRECTION = 90.0

def parse_swan_grid_output(filename):
    """Parse the grid point output format"""
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Pattern to match each grid point line
    # Format: "X Y 'grid_point' 0 depth ..."
    # Wave data appears on next line: "0 Hs ..."
    
    lines = content.strip().split('\n')
    
    hs_values = []
    tm_values = []
    dir_values = []
    x_coords = []
    y_coords = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for grid point line with coordinates
        coord_match = re.search(r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+\'grid_point\'', line)
        if coord_match:
            x = float(coord_match.group(1))
            y = float(coord_match.group(2))
            x_coords.append(x)
            y_coords.append(y)
            
            # Next line contains wave data
            if i + 1 < len(lines):
                data_line = lines[i + 1].strip()
                # Extract wave height (first number after the initial 0)
                # Format: "0 Hs TM01 DIR ..."
                parts = data_line.split()
                if len(parts) >= 4:
                    # Skip the first '0', then Hs, TM01, DIR
                    hs = float(parts[1])
                    tm = float(parts[2])
                    direc = float(parts[3])
                    hs_values.append(hs)
                    tm_values.append(tm)
                    dir_values.append(direc)
        
        i += 1
    
    print(f"Found {len(hs_values)} grid points")
    
    if len(hs_values) == 0:
        return None, None, None, None, None
    
    # Reshape to grid (assuming ordered by Y then X)
    # The data appears to be ordered by decreasing Y (North to South)
    unique_x = sorted(set(x_coords))
    unique_y = sorted(set(y_coords), reverse=True)  # North to South
    
    print(f"Unique X: {len(unique_x)} points")
    print(f"Unique Y: {len(unique_y)} points")
    
    if len(unique_x) != GRID_X or len(unique_y) != GRID_Y:
        print(f"Warning: Expected {GRID_X}x{GRID_Y}, got {len(unique_x)}x{len(unique_y)}")
    
    # Create grid
    hs_grid = np.zeros((len(unique_y), len(unique_x)))
    tm_grid = np.zeros((len(unique_y), len(unique_x)))
    dir_grid = np.zeros((len(unique_y), len(unique_x)))
    
    for idx, (x, y, hs, tm, direc) in enumerate(zip(x_coords, y_coords, hs_values, tm_values, dir_values)):
        i = unique_y.index(y)
        j = unique_x.index(x)
        hs_grid[i, j] = hs
        tm_grid[i, j] = tm
        dir_grid[i, j] = direc
    
    return hs_grid, tm_grid, dir_grid, unique_x, unique_y

def generate_report(hs_grid, tm_grid, dir_grid, x_coords, y_coords):
    """Generate formatted report"""
    
    hs_flat = hs_grid.flatten()
    hs_valid = hs_flat[hs_flat > 0.001]
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""
{'='*70}
LAKE KARIBA - NYENJE AREA WAVE ANALYSIS
{'='*70}
Report Date/Time: {timestamp}
Wind: {WIND_SPEED} m/s from {WIND_DIRECTION}° (East wind)
Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km
Grid: {len(x_coords)} × {len(y_coords)} points
{'='*70}

{'='*70}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*70}

┌─────────────────────┬─────────────┬──────────────────────────────────────────┐
│ Statistic           │ Value       │ Interpretation                           │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Hs          │ {hs_valid.min():8.4f} m  │ {hs_valid.min()*100:.2f} cm                                    │
│ Maximum Hs          │ {hs_valid.max():8.4f} m  │ {hs_valid.max()*100:.2f} cm                                    │
│ Mean Hs             │ {hs_valid.mean():8.4f} m  │ {hs_valid.mean()*100:.2f} cm                                    │
└─────────────────────┴─────────────┴──────────────────────────────────────────┘

{'='*70}
WAVE HEIGHT GRID (HSIGN in meters)
{'='*70}
Rows: North (top) to South (bottom)
Columns: West (left) to East (right)

     Y\\X    |"""
    
    for x in x_coords:
        report += f" {x/1000:6.1f}km |"
    report += "\n" + "-" * (12 + 11 * len(x_coords)) + "\n"
    
    for i in range(len(y_coords)):
        report += f"{y_coords[i]/1000:8.1f} |"
        for j in range(len(x_coords)):
            report += f" {hs_grid[i,j]:7.4f} |"
        report += "\n"
    
    # Visual map
    report += f"""
{'='*70}
WAVE HEIGHT VISUAL MAP
{'='*70}
Wind: {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (→ → → East wind)

                    NORTH (Y={y_coords[0]/1000:.1f} km)
    ┌─────────────────────────────────────────────────────────────────┐
"""
    
    for i in range(len(y_coords)):
        row_str = "    │"
        for j in range(len(x_coords)):
            hs_val = hs_grid[i, j]
            if hs_val < 0.01:
                row_str += "  0.000  "
            else:
                row_str += f" {hs_val:6.3f} "
        row_str += "│"
        if i == 0:
            row_str += " ← North shore"
        elif i == len(y_coords) - 1:
            row_str += " ← South shore"
        report += row_str + "\n"
    
    report += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH (Y={y_coords[-1]/1000:.1f} km)
    
    WIND → → → → → {WIND_SPEED} m/s FROM {WIND_DIRECTION}° (East wind)
"""
    
    return report

def main():
    input_file = 'kariba_output.raw'
    
    print(f"Processing: {input_file}")
    
    hs_grid, tm_grid, dir_grid, x_coords, y_coords = parse_swan_grid_output(input_file)
    
    if hs_grid is None:
        print("Failed to parse output!")
        return
    
    report = generate_report(hs_grid, tm_grid, dir_grid, x_coords, y_coords)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'kariba_wave_report_{timestamp}.txt'
    
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(report)
    print(f"\nReport saved to: {report_file}")

if __name__ == "__main__":
    main()