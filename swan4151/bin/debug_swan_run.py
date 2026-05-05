#!/usr/bin/env python3
"""
Debug SWAN run function - Corrected paths
"""

import os
import subprocess
import shutil
import glob

# Configuration
SWAN_BASE_DIR = "/home/chawas/deployed/charara_github/swan4151/bin"
SWAN_EXE = os.path.join(SWAN_BASE_DIR, "swan.exe")
INPUT_FILE = os.path.join(SWAN_BASE_DIR, "INPUT")

# Directories
SWAN_INPUTS_DIR = os.path.join(SWAN_BASE_DIR, "swan_input_files")
SWAN_OUTPUTS_DIR = os.path.join(SWAN_BASE_DIR, "swan_era5_debiased_outputs")
WIND_ARCHIVE_DIR = os.path.join(SWAN_BASE_DIR, "swan_wind_archive")

# Source wind files directory (where your extracted winds are)
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
    """
    Run SWAN for a specific timestamp with organized file storage
    """
    
    # Create year-specific directories
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
    
    print(f"\nDebug info:")
    print(f"  Year: {year}")
    print(f"  Timestamp: {timestamp}")
    print(f"  Wind file path: {wind_file_path}")
    print(f"  File exists: {os.path.exists(wind_file_path)}")
    
    # Copy wind file to archive
    if os.path.exists(wind_file_path):
        shutil.copy(wind_file_path, archived_wind)
        print(f"  Copied wind file to: {archived_wind}")
    else:
        print(f"  ERROR: Wind file not found!")
        return None, None
    
    # Create SWAN input file
    swan_content = f"""PROJECT 'ERA5' '{timestamp}' 'ERA5 wind {timestamp}' ' ' ' '
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
    print(f"  Created SWAN input: {swn_file}")
    
    # Create INPUT file for SWAN
    input_content = f"""PROJECT 'ERA5' '{timestamp}' 'ERA5 wind {timestamp}' ' ' ' '
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
    print(f"  Created INPUT file in SWAN directory")
    
    # Run SWAN
    print(f"  Running SWAN...")
    original_dir = os.getcwd()
    os.chdir(SWAN_BASE_DIR)
    result = subprocess.run([SWAN_EXE], capture_output=True, text=True)
    os.chdir(original_dir)
    
    print(f"  SWAN return code: {result.returncode}")
    
    # Check if output was created
    if os.path.exists(output_file):
        print(f"  ✅ Output created: {output_file}")
        return output_file, swn_file
    else:
        # Check if output is in SWAN directory
        alt_output = os.path.join(SWAN_BASE_DIR, os.path.basename(output_file))
        if os.path.exists(alt_output):
            print(f"  Found output in SWAN directory, moving...")
            shutil.move(alt_output, output_file)
            return output_file, swn_file
    
    print(f"  ❌ Output not created")
    return None, None

# Test with a single file from 1971
print("=" * 60)
print("Testing Organized SWAN Runner (Corrected Paths)")
print("=" * 60)

# Find the first wind file in 1971
wind_source_dir = "/home/chawas/deployed/charara_github/swan4151/bin/nyenje_era5_debiased"
year = 1971
year_dir = os.path.join(wind_source_dir, str(year))

print(f"\nLooking for wind files in: {year_dir}")

if os.path.exists(year_dir):
    wind_files = sorted(glob.glob(os.path.join(year_dir, "nyenje_wind_*.wnd")))
    print(f"Found {len(wind_files)} wind files")
    
    if wind_files:
        # Take the first file for testing
        test_wind = wind_files[0]
        filename = os.path.basename(test_wind)
        timestamp = filename.replace('nyenje_wind_', '').replace('.wnd', '')
        
        print(f"\nTest file: {filename}")
        print(f"Timestamp: {timestamp}")
        
        output_file, swn_file = run_swan_for_timestamp(year, timestamp, test_wind)
        
        if output_file:
            print(f"\n✅ SUCCESS!")
            print(f"   SWAN input file: {swn_file}")
            print(f"   Output file: {output_file}")
            
            stats = parse_swan_output(output_file)
            if stats:
                print(f"\n📊 Wave Height Results:")
                print(f"   Max: {stats['max_hs']:.4f} m")
                print(f"   Mean: {stats['mean_hs']:.4f} m")
                print(f"   Min: {stats['min_hs']:.4f} m")
        else:
            print("\n❌ FAILED - Check the debug output above")
    else:
        print(f"No wind files found in {year_dir}")
else:
    print(f"Directory does not exist: {year_dir}")
    print("\nListing contents of nyenje_era5_debiased:")
    if os.path.exists(wind_source_dir):
        print(f"  Subdirectories: {os.listdir(wind_source_dir)}")
    else:
        print(f"  Directory not found: {wind_source_dir}")
