#!/usr/bin/env python3
"""
Run SWAN for a specific 6-hourly timestamp
"""

import os
import subprocess
import shutil

# Configuration
SWAN_BASE_DIR = "/home/chawas/deployed/charara_github/swan4151/bin"
SWAN_EXE = os.path.join(SWAN_BASE_DIR, "swan.exe")
INPUT_FILE = os.path.join(SWAN_BASE_DIR, "INPUT")

# Directories
SWAN_INPUTS_DIR = os.path.join(SWAN_BASE_DIR, "swan_input_files")
SWAN_OUTPUTS_DIR = os.path.join(SWAN_BASE_DIR, "swan_era5_debiased_outputs")
WIND_ARCHIVE_DIR = os.path.join(SWAN_BASE_DIR, "swan_wind_archive")
WIND_SOURCE_DIR = os.path.join(SWAN_BASE_DIR, "nyenje_era5_debiased")

# Create directories
os.makedirs(SWAN_INPUTS_DIR, exist_ok=True)
os.makedirs(SWAN_OUTPUTS_DIR, exist_ok=True)
os.makedirs(WIND_ARCHIVE_DIR, exist_ok=True)

def parse_swan_output(output_file):
    """Parse SWAN output to extract wave statistics"""
    import re
    import numpy as np
    
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        numbers = re.findall(r'[-+]?\d+\.\d+E[+-]\d+', content)
        if len(numbers) >= 72:
            wave_heights = [float(x) for x in numbers[:72]]
            valid_waves = [w for w in wave_heights if w > 0.001]
            
            if valid_waves:
                return {
                    'max_hs': max(valid_waves),
                    'mean_hs': np.mean(valid_waves),
                    'min_hs': min(valid_waves)
                }
    except Exception as e:
        print(f"Error parsing: {e}")
    
    return None

def run_swan_for_timestamp(year, timestamp, wind_file_path):
    """Run SWAN for a specific timestamp"""
    
    # Create directories
    input_year_dir = os.path.join(SWAN_INPUTS_DIR, str(year))
    output_year_dir = os.path.join(SWAN_OUTPUTS_DIR, str(year))
    wind_year_dir = os.path.join(WIND_ARCHIVE_DIR, str(year))
    
    os.makedirs(input_year_dir, exist_ok=True)
    os.makedirs(output_year_dir, exist_ok=True)
    os.makedirs(wind_year_dir, exist_ok=True)
    
    # File paths
    swn_file = os.path.join(input_year_dir, f"swan_{timestamp}.swn")
    output_file = os.path.join(output_year_dir, f"waves_{timestamp}.txt")
    archived_wind = os.path.join(wind_year_dir, f"nyenje_wind_{timestamp}.wnd")
    
    # Short run ID (4 characters max)
    short_id = timestamp[-4:]
    
    print(f"\n{'='*50}")
    print(f"Running SWAN for: {timestamp}")
    print(f"{'='*50}")
    
    # Copy wind file to archive
    if not os.path.exists(wind_file_path):
        print(f"ERROR: Wind file not found: {wind_file_path}")
        return None, None
    
    shutil.copy(wind_file_path, archived_wind)
    print(f"  ✓ Wind file archived")
    
    # Create SWAN input file
    swan_content = f"""PROJECT 'ERA5' '{short_id}' 'ERA5 run' ' ' ' '
MODE STATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_9x8.bot' 1 0 FREE
INPGRID WIND REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP WIND 1 '{archived_wind}' 4 0 FREE
GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73
NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01
BLOCK 'COMPGRID' NOHEADER '{output_file}' LAYOUT 4 HSIGN TM01 DIR
COMPUTE
STOP
"""
    
    with open(swn_file, 'w') as f:
        f.write(swan_content)
    print(f"  ✓ SWAN input created: {swn_file}")
    
    # Create INPUT file for SWAN
    input_content = f"""PROJECT 'ERA5' '{short_id}' 'ERA5 run' ' ' ' '
MODE STATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_9x8.bot' 1 0 FREE
INPGRID WIND REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP WIND 1 '{archived_wind}' 4 0 FREE
GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73
NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01
BLOCK 'COMPGRID' NOHEADER '{output_file}' LAYOUT 4 HSIGN TM01 DIR
COMPUTE
STOP
"""
    
    with open(INPUT_FILE, 'w') as f:
        f.write(input_content)
    
    # Run SWAN
    original_dir = os.getcwd()
    os.chdir(SWAN_BASE_DIR)
    result = subprocess.run([SWAN_EXE], capture_output=True, text=True)
    os.chdir(original_dir)
    
    if result.returncode != 0:
        print(f"  ⚠️ SWAN return code: {result.returncode}")
    
    # Check output
    if os.path.exists(output_file):
        print(f"  ✓ Output created: {output_file}")
        return output_file, swn_file
    else:
        alt_output = os.path.join(SWAN_BASE_DIR, os.path.basename(output_file))
        if os.path.exists(alt_output):
            shutil.move(alt_output, output_file)
            print(f"  ✓ Output moved to: {output_file}")
            return output_file, swn_file
    
    print(f"  ❌ Output not created")
    return None, None

# Test with 1971-01-01 06:00 (first 6-hourly)
year = 1971
timestamp = "19710101_0600"
wind_file = os.path.join(WIND_SOURCE_DIR, str(year), f"nyenje_wind_{timestamp}.wnd")

print(f"Testing with: {timestamp}")
print(f"Wind file: {wind_file}")
print(f"Exists: {os.path.exists(wind_file)}")

if os.path.exists(wind_file):
    output_file, swn_file = run_swan_for_timestamp(year, timestamp, wind_file)
    
    if output_file:
        stats = parse_swan_output(output_file)
        if stats:
            print(f"\n{'='*50}")
            print(f"RESULTS FOR {timestamp}")
            print(f"{'='*50}")
            print(f"  Max Wave Height: {stats['max_hs']:.4f} m ({stats['max_hs']*100:.2f} cm)")
            print(f"  Mean Wave Height: {stats['mean_hs']:.4f} m ({stats['mean_hs']*100:.2f} cm)")
            print(f"  Min Wave Height: {stats['min_hs']:.4f} m ({stats['min_hs']*100:.2f} cm)")
else:
    print(f"\nAvailable wind files for 1971:")
    import glob
    files = glob.glob(os.path.join(WIND_SOURCE_DIR, str(year), "*.wnd"))
    for f in sorted(files)[:10]:
        print(f"  {os.path.basename(f)}")
