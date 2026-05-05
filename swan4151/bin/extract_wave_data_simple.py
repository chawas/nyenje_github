#!/usr/bin/env python3

import re
import datetime

# Open and read the file
with open('kariba_output.raw', 'r') as f:
    lines = f.readlines()

# Extract wave heights
wave_heights = []
wave_periods = []
wave_directions = []
x_coords = []
y_coords = []

for i, line in enumerate(lines):
    # Look for data lines starting with "  0    "
    if re.match(r'\s+0\s+', line):
        parts = line.strip().split()
        if len(parts) >= 4:
            hs = float(parts[1])      # Wave height
            tm = float(parts[2])      # Period
            direc = float(parts[3])   # Direction
            wave_heights.append(hs)
            wave_periods.append(tm)
            wave_directions.append(direc)
            
            # Get coordinates from previous line
            if i > 0:
                prev_line = lines[i-1]
                coord_match = re.search(r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+\'grid_point\'', prev_line)
                if coord_match:
                    x_coords.append(float(coord_match.group(1)))
                    y_coords.append(float(coord_match.group(2)))

print(f"{'='*60}")
print(f"LAKE KARIBA - NYENJE WAVE ANALYSIS")
print(f"{'='*60}")
print(f"Analysis Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Wind: 10 m/s from 090° (East wind)")
print(f"{'='*60}")
print()

print(f"Total grid points found: {len(wave_heights)}")
print()

if wave_heights:
    print(f"{'='*60}")
    print("WAVE HEIGHT SUMMARY (HSIGN)")
    print(f"{'='*60}")
    print(f"  Minimum wave height: {min(wave_heights):.4f} m ({min(wave_heights)*100:.2f} cm)")
    print(f"  Maximum wave height: {max(wave_heights):.4f} m ({max(wave_heights)*100:.2f} cm)")
    print(f"  Average wave height: {sum(wave_heights)/len(wave_heights):.4f} m")
    print()
    
    print(f"{'='*60}")
    print("WAVE PERIOD SUMMARY (TM01)")
    print(f"{'='*60}")
    print(f"  Minimum period: {min(wave_periods):.2f} s")
    print(f"  Maximum period: {max(wave_periods):.2f} s")
    print(f"  Average period: {sum(wave_periods)/len(wave_periods):.2f} s")
    print()
    
    print(f"{'='*60}")
    print("WAVE DIRECTION SUMMARY (DIR)")
    print(f"{'='*60}")
    print(f"  Minimum direction: {min(wave_directions):.1f}°")
    print(f"  Maximum direction: {max(wave_directions):.1f}°")
    print(f"  Average direction: {sum(wave_directions)/len(wave_directions):.1f}°")
    print()

# Create a grid view (assuming 9x8 grid)
if len(wave_heights) >= 72:
    print(f"{'='*60}")
    print("WAVE HEIGHT GRID (meters)")
    print(f"{'='*60}")
    print("North (top) to South (bottom), West (left) to East (right)")
    print()
    
    # Reshape to 8 rows (Y) x 9 columns (X)
    for row in range(8):
        start = row * 9
        end = start + 9
        row_heights = wave_heights[start:end]
        row_str = "  "
        for h in row_heights:
            row_str += f"{h:6.3f} "
        print(row_str)
    
    print()
    print("  WIND → → → 10 m/s FROM EAST (090°)")