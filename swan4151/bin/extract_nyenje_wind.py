#!/usr/bin/env python3
"""
Extract wind data for Nyenje Bay from ERA5 NetCDF files
and create SWAN-compatible wind forcing files

Author: Key Informatics
Date: 2026-04-07
"""

import numpy as np
import xarray as xr
import pandas as pd
import os
import glob
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Nyenje Bay location (Charara Bay area)
NYENJE_LAT = -16.53   # degrees (negative for South)
NYENJE_LON = 28.83    # degrees (positive for East)

# Debiasing factor from CCMP validation
DEBIAS_FACTOR = 0.718

# SWAN grid parameters for Nyenje Bay (9×8 points at 500m resolution)
# Domain: 4 km × 3.5 km
NX = 9   # points in X direction (West-East)
NY = 8   # points in Y direction (South-North)
DOMAIN_X = 4000.0   # meters
DOMAIN_Y = 3500.0   # meters

# Calculate grid spacing
DX = DOMAIN_X / (NX - 1)   # 500 m
DY = DOMAIN_Y / (NY - 1)   # 500 m

# Create grid coordinates (local Cartesian)
x_coords = np.linspace(0, DOMAIN_X, NX)
y_coords = np.linspace(0, DOMAIN_Y, NY)
X_grid, Y_grid = np.meshgrid(x_coords, y_coords)

# Convert to geographic coordinates for ERA5 extraction
# Approximate conversion: 1° ≈ 111 km for latitude, 106 km for longitude at this latitude
CENTER_LAT = NYENJE_LAT
CENTER_LON = NYENJE_LON

lon_grid = CENTER_LON + (X_grid - DOMAIN_X/2) / 106000
lat_grid = CENTER_LAT + (Y_grid - DOMAIN_Y/2) / 111000

# ============================================================================
# FUNCTIONS
# ============================================================================

def find_era5_files(data_dir):
    """Find all ERA5 NetCDF files in the directory"""
    patterns = ['*.nc', '*.nc4', '*.grib', '*.grb']
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(os.path.join(data_dir, pattern)))
        all_files.extend(glob.glob(os.path.join(data_dir, f"*{pattern}")))
    return sorted(set(all_files))

def extract_wind_for_point(nc_file, lat, lon):
    """
    Extract wind data for a single point from NetCDF file
    
    Returns:
    --------
    dict with u10, v10, time, speed, direction
    """
    try:
        ds = xr.open_dataset(nc_file, engine='netcdf4')
        
        # Handle different variable names
        if 'u10' in ds.variables:
            u10 = ds['u10']
            v10 = ds['v10']
        elif 'u10n' in ds.variables:
            u10 = ds['u10n']
            v10 = ds['v10n']
        else:
            # Try to find wind variables
            u_vars = [v for v in ds.variables if 'u' in v.lower() and '10' in v]
            v_vars = [v for v in ds.variables if 'v' in v.lower() and '10' in v]
            if u_vars and v_vars:
                u10 = ds[u_vars[0]]
                v10 = ds[v_vars[0]]
            else:
                print(f"  No wind variables found in {nc_file}")
                ds.close()
                return None
        
        # Extract at nearest point
        u_point = u10.sel(latitude=lat, longitude=lon, method='nearest')
        v_point = v10.sel(latitude=lat, longitude=lon, method='nearest')
        
        # Get time values
        times = u_point.time.values
        
        # Convert to numpy arrays
        u_values = u_point.values
        v_values = v_point.values
        
        # Apply debiasing
        u_values = u_values * DEBIAS_FACTOR
        v_values = v_values * DEBIAS_FACTOR
        
        # Calculate wind speed and direction
        speed = np.sqrt(u_values**2 + v_values**2)
        direction = np.arctan2(u_values, v_values) * 180 / np.pi
        direction = 270 - direction  # Meteorological convention
        direction = direction % 360
        
        ds.close()
        
        return {
            'time': times,
            'u10': u_values,
            'v10': v_values,
            'speed': speed,
            'direction': direction,
            'file': os.path.basename(nc_file)
        }
        
    except Exception as e:
        print(f"  Error processing {nc_file}: {e}")
        return None

def extract_wind_for_grid(nc_file, lon_grid, lat_grid):
    """
    Extract wind data for the full 9×8 grid from NetCDF file
    
    Returns:
    --------
    dict with u10_grid, v10_grid, time, speed_grid, direction_grid
    """
    try:
        ds = xr.open_dataset(nc_file, engine='netcdf4')
        
        # Handle different variable names
        if 'u10' in ds.variables:
            u10 = ds['u10']
            v10 = ds['v10']
        elif 'u10n' in ds.variables:
            u10 = ds['u10n']
            v10 = ds['v10n']
        else:
            u_vars = [v for v in ds.variables if 'u' in v.lower() and '10' in v]
            v_vars = [v for v in ds.variables if 'v' in v.lower() and '10' in v]
            if u_vars and v_vars:
                u10 = ds[u_vars[0]]
                v10 = ds[v_vars[0]]
            else:
                print(f"  No wind variables found in {nc_file}")
                ds.close()
                return None
        
        # Interpolate to grid points
        u_grid = u10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        v_grid = v10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        
        # Get time
        times = u_grid.time.values
        
        # Apply debiasing
        u_values = u_grid.values * DEBIAS_FACTOR
        v_values = v_grid.values * DEBIAS_FACTOR
        
        # Calculate speed and direction for each point
        speed_grid = np.sqrt(u_values**2 + v_values**2)
        direction_grid = np.arctan2(u_values, v_values) * 180 / np.pi
        direction_grid = 270 - direction_grid
        direction_grid = direction_grid % 360
        
        ds.close()
        
        return {
            'time': times,
            'u10': u_values,
            'v10': v_values,
            'speed': speed_grid,
            'direction': direction_grid,
            'file': os.path.basename(nc_file)
        }
        
    except Exception as e:
        print(f"  Error processing {nc_file}: {e}")
        return None

def create_swan_wind_file(wind_data, output_file, time_index=None):
    """
    Create SWAN wind forcing file from extracted wind data
    
    Format for SWAN BLOCK input:
    For stationary run with constant wind: use single time step
    For nonstationary run: use multiple time steps
    """
    
    if time_index is None:
        time_index = 0
    
    # Get data for the specified time
    if len(wind_data['time'].shape) > 0:
        current_time = wind_data['time'][time_index]
        u_current = wind_data['u10'][time_index] if len(wind_data['u10'].shape) > 1 else wind_data['u10']
        v_current = wind_data['v10'][time_index] if len(wind_data['v10'].shape) > 1 else wind_data['v10']
    else:
        current_time = wind_data['time']
        u_current = wind_data['u10']
        v_current = wind_data['v10']
    
    # Calculate domain average for summary
    if len(u_current.shape) > 1:
        avg_speed = np.mean(np.sqrt(u_current**2 + v_current**2))
        avg_dir = np.mean(np.arctan2(u_current, v_current) * 180 / np.pi)
        avg_dir = (270 - avg_dir) % 360
    else:
        avg_speed = np.sqrt(u_current**2 + v_current**2)
        avg_dir = (270 - np.arctan2(u_current, v_current) * 180 / np.pi) % 360
    
    # Write SWAN wind file
    with open(output_file, 'w') as f:
        f.write("! SWAN wind file for Nyenje Bay\n")
        f.write(f"! Extracted from: {wind_data['file']}\n")
        f.write(f"! Time: {pd.to_datetime(current_time)}\n")
        f.write(f"! Domain average wind: {avg_speed:.2f} m/s from {avg_dir:.1f}°\n")
        f.write("! Format: u10 (m/s) v10 (m/s)\n")
        f.write(f"! Grid: {NX} × {NY} points (West to East, South to North)\n\n")
        
        # Write grid data (South to North, West to East)
        # SWAN expects rows from South to North? Let's check orientation
        for iy in range(NY):  # South to North
            row_str = ""
            for ix in range(NX):  # West to East
                if len(u_current.shape) > 1:
                    u_val = u_current[iy, ix]
                    v_val = v_current[iy, ix]
                else:
                    u_val = u_current
                    v_val = v_current
                row_str += f" {u_val:8.3f} {v_val:8.3f}"
            f.write(row_str + "\n")
    
    return {
        'file': output_file,
        'time': current_time,
        'avg_speed': avg_speed,
        'avg_direction': avg_dir,
        'grid_size': f"{NX}×{NY}"
    }

def create_swan_input_with_wind(wind_file, output_swn_file, is_stationary=True):
    """
    Create SWAN input file that uses the extracted wind file
    """
    
    if is_stationary:
        swan_content = f"""!===============================================================================
! SWAN INPUT FILE FOR NYENJE BAY - WITH EXTRACTED ERA5 WIND
!===============================================================================

PROJECT 'Nyenje' 'ERA5' 'Wave simulation with ERA5 wind' ' ' ' '

MODE STATIONARY TWODIMENSIONAL

COORDINATES CARTESIAN

! Computational grid: 4 km × 3.5 km, 500m resolution
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

! Bathymetry
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_8x7.bot' 1 0 FREE

! Wind from ERA5 (gridded, 9×8 points)
INPGRID WIND REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP WIND 1.0 '{os.path.basename(wind_file)}' 1 0 FREE

! Physics
GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73

! Numerics
NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01

! Output
BLOCK 'COMPGRID' NOHEADER 'nyenje_wave_output.txt' LAYOUT 4 HSIGN TM01 DIR

COMPUTE

STOP
"""
    else:
        swan_content = f"""!===============================================================================
! SWAN INPUT FILE FOR NYENJE BAY - NONSTATIONARY WITH EXTRACTED ERA5 WIND
!===============================================================================

PROJECT 'Nyenje' 'ERA5' 'Nonstationary wave simulation' ' ' ' '

MODE NONSTATIONARY TWODIMENSIONAL

COORDINATES CARTESIAN

CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_8x7.bot' 1 0 FREE

! Time-varying wind from ERA5
! Assuming hourly data for one day as example
INPGRID WIND REGULAR 0.0 0.0 0.0 8 7 500.0 500.0 NONSTATIONARY 20200101.000000 3600.0 SEC 20200101.230000
READINP WIND 1.0 '{os.path.basename(wind_file)}' 1 0 FREE

GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73

NUMERIC NONSTAT 1

! Output point at center
POINTS 'center' 2000.0 1750.0
TABLE 'center' HEADER 'nyenje_wave_timeseries.txt' HSIGN TM01 DIR

COMPUTE NONSTATIONARY 20200101.000000 3600.0 SEC 20200101.230000

STOP
"""
    
    with open(output_swn_file, 'w') as f:
        f.write(swan_content)
    
    return output_swn_file

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    print("=" * 70)
    print("NYENJE BAY - ERA5 WIND EXTRACTION FOR SWAN")
    print("=" * 70)
    
    # Find ERA5 files
    data_dir = "/home/chawas/deployed/charara_github/data/era5/debiased"  # Update this path
    print(f"\nSearching for ERA5 files in: {data_dir}")
    
    nc_files = find_era5_files(data_dir)
    
    if not nc_files:
        print("\n❌ No NetCDF files found!")
        print("Please update the data_dir path to your ERA5 data location.")
        print("\nCommon locations to check:")
        print("  - ~/deployed/era5_data/")
        print("  - ~/deployed/data/era5/")
        print("  - ~/Downloads/era5/")
        return None
    
    print(f"✅ Found {len(nc_files)} NetCDF files")
    
    # Use the first file for testing (you can modify to select specific year)
    test_file = nc_files[0]
    print(f"\n📁 Using test file: {os.path.basename(test_file)}")
    
    # Extract wind for the full grid
    print("\n🔄 Extracting wind data for Nyenje Bay grid...")
    wind_data = extract_wind_for_grid(test_file, lon_grid, lat_grid)
    
    if wind_data is None:
        print("❌ Failed to extract wind data")
        return None
    
    print(f"✅ Extracted {len(wind_data['time'])} time steps")
    print(f"   Grid shape: {wind_data['u10'].shape}")
    
    # Create SWAN wind file for the first time step
    output_dir = "/home/chawas/deployed/charara_github/swan4151/bin/"
    os.makedirs(output_dir, exist_ok=True)
    
    wind_file = os.path.join(output_dir, "nyenje_era5_wind.wnd")
    result = create_swan_wind_file(wind_data, wind_file, time_index=0)
    
    print(f"\n📝 Created SWAN wind file: {result['file']}")
    print(f"   Time: {result['time']}")
    print(f"   Domain average wind: {result['avg_speed']:.2f} m/s from {result['avg_direction']:.1f}°")
    print(f"   Grid: {result['grid_size']}")
    
    # Create SWAN input file
    swn_file = os.path.join(output_dir, "nyenje_era5_run.swn")
    create_swan_input_with_wind(wind_file, swn_file, is_stationary=True)
    
    print(f"\n📝 Created SWAN input file: {swn_file}")
    
    # Display wind statistics
    print("\n" + "=" * 70)
    print("WIND STATISTICS FOR NYENJE BAY")
    print("=" * 70)
    
    # Calculate statistics across the grid
    u_grid = wind_data['u10'][0] if len(wind_data['u10'].shape) > 1 else wind_data['u10']
    v_grid = wind_data['v10'][0] if len(wind_data['v10'].shape) > 1 else wind_data['v10']
    
    speeds = np.sqrt(u_grid**2 + v_grid**2)
    dirs = (270 - np.arctan2(u_grid, v_grid) * 180 / np.pi) % 360
    
    print(f"\nGrid Statistics (9×8 = 72 points):")
    print(f"  Wind Speed - Min: {np.min(speeds):.2f} m/s")
    print(f"  Wind Speed - Max: {np.max(speeds):.2f} m/s")
    print(f"  Wind Speed - Mean: {np.mean(speeds):.2f} m/s")
    print(f"  Wind Speed - Std: {np.std(speeds):.2f} m/s")
    print(f"  Wind Direction - Mean: {np.mean(dirs):.1f}°")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print(f"1. Copy bathymetry file to: {output_dir}")
    print(f"2. Run SWAN: cd {output_dir} && ./swan.exe nyenje_era5_run.swn")
    print(f"3. Check output: nyenje_wave_output.txt")
    print("=" * 70)
    
    return {
        'wind_file': wind_file,
        'swn_file': swn_file,
        'wind_data': wind_data,
        'stats': {
            'min_speed': np.min(speeds),
            'max_speed': np.max(speeds),
            'mean_speed': np.mean(speeds),
            'std_speed': np.std(speeds),
            'mean_direction': np.mean(dirs)
        }
    }

if __name__ == "__main__":
    result = main()