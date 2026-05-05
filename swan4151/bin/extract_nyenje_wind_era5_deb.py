#!/usr/bin/env python3
"""
Extract wind speed and direction from ERA5 debiased NetCDF files
Create SWAN wind input file for Nyenje Bay (9×8 grid)
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

NX = 9   # points in X direction (West-East)
NY = 8   # points in Y direction (South-North)
DOMAIN_X = 4000.0   # meters
DOMAIN_Y = 3500.0   # meters
CENTER_LAT = -16.53
CENTER_LON = 28.83
DEBIAS_FACTOR = 0.718

def create_nyenje_grid():
    """Create 9×8 grid of coordinates for Nyenje Bay"""
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    
    # Convert to geographic coordinates
    lon = CENTER_LON + (X - DOMAIN_X/2) / 106000
    lat = CENTER_LAT + (Y - DOMAIN_Y/2) / 111000
    
    return {
        'lon': lon, 
        'lat': lat, 
        'nx': NX, 
        'ny': NY,
        'x': x_coords,
        'y': y_coords
    }

def find_era5_files(data_dir):
    """Find all ERA5 NetCDF files"""
    all_files = glob.glob(os.path.join(data_dir, "*.nc"))
    all_files.extend(glob.glob(os.path.join(data_dir, "*.nc4")))
    return sorted(set(all_files))

def extract_wind_from_nc(nc_file, lon_grid, lat_grid, time_index=0):
    """
    Extract wind speed and direction from NetCDF file for a specific time step
    
    Returns:
        speed_grid: 2D array (NY, NX) of wind speeds in m/s
        dir_grid: 2D array (NY, NX) of wind directions in degrees
        time: the timestamp of the extracted data
    """
    try:
        ds = xr.open_dataset(nc_file, engine='netcdf4')
        
        # Find wind variables
        u10 = None
        v10 = None
        
        if 'u10' in ds.variables:
            u10 = ds['u10']
            v10 = ds['v10']
        elif 'u10n' in ds.variables:
            u10 = ds['u10n']
            v10 = ds['v10n']
        else:
            # Search for any u/v wind variables
            for var in ds.variables:
                if 'u' in var.lower() and '10' in var:
                    u10 = ds[var]
                elif 'v' in var.lower() and '10' in var:
                    v10 = ds[var]
        
        if u10 is None or v10 is None:
            print(f"  Warning: No wind variables found in {os.path.basename(nc_file)}")
            ds.close()
            return None, None, None
        
        # Extract at grid points
        u_interp = u10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        v_interp = v10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        
        # Get time values
        times = u_interp.time.values
        
        # Handle different dimensions
        if len(u_interp.shape) == 3:
            # Shape: (time, lat, lon)
            u_values = u_interp.isel(time=time_index).values
            v_values = v_interp.isel(time=time_index).values
            current_time = times[time_index] if time_index < len(times) else times[0]
        else:
            # Shape: (lat, lon) - no time dimension
            u_values = u_interp.values
            v_values = v_interp.values
            current_time = times[0] if len(times) > 0 else None
        
        # Apply debiasing factor
        u_values = u_values * DEBIAS_FACTOR
        v_values = v_values * DEBIAS_FACTOR
        
        # Calculate wind speed (m/s)
        speed_grid = np.sqrt(u_values**2 + v_values**2)
        
        # Calculate wind direction (meteorological convention)
        # Direction: where wind comes from, clockwise from North
        dir_rad = np.arctan2(v_values, u_values)
        dir_deg = 270 - dir_rad * 180 / np.pi
        dir_grid = dir_deg % 360
        
        ds.close()
        
        return speed_grid, dir_grid, current_time
        
    except Exception as e:
        print(f"  Error processing {os.path.basename(nc_file)}: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def create_swan_wind_file(speed_grid, dir_grid, time, output_file, metadata=None):
    """Create SWAN wind input file in SPEED + DIRECTION format"""
    
    NY, NX = speed_grid.shape
    
    with open(output_file, 'w') as f:
        f.write("! SWAN wind input file for Nyenje Bay\n")
        f.write(f"! Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if metadata:
            f.write(f"! Source: {metadata.get('file', 'Unknown')}\n")
            if time:
                f.write(f"! Time: {pd.to_datetime(time)}\n")
            f.write(f"! Debiasing factor: {DEBIAS_FACTOR}\n")
        f.write("! Format: wind_speed (m/s) wind_direction (degrees)\n")
        f.write("! Direction: Meteorological convention (where wind comes from, clockwise from North)\n")
        f.write(f"! Grid: {NX} columns (West→East) × {NY} rows (South→North)\n")
        f.write("! Reading order: IDLA=1 (left to right, top to bottom)\n\n")
        
        # Write data rows (South to North, West to East)
        for iy in range(NY):
            row_str = ""
            for ix in range(NX):
                spd = speed_grid[iy, ix]
                d = dir_grid[iy, ix]
                row_str += f" {spd:8.3f} {d:8.1f}"
            f.write(row_str + "\n")
    
    return output_file

def create_swan_input_file(wind_file, bathymetry_file, output_swn_file):
    """Create SWAN input file that uses the extracted wind file"""
    
    swan_content = f"""!===============================================================================
! SWAN INPUT FILE FOR NYENJE BAY
! Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
!===============================================================================

PROJECT 'Nyenje' 'ERA5' 'Wave simulation with ERA5 wind' ' ' ' '

MODE STATIONARY TWODIMENSIONAL

COORDINATES CARTESIAN

! Computational grid: 4 km × 3.5 km, 500m resolution
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

! Bathymetry
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 '{os.path.basename(bathymetry_file)}' 1 0 FREE

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
    
    with open(output_swn_file, 'w') as f:
        f.write(swan_content)
    
    return output_swn_file

def main():
    print("=" * 60)
    print("NYENJE BAY - ERA5 WIND EXTRACTION FOR SWAN")
    print("=" * 60)
    
    # Create grid
    grid = create_nyenje_grid()
    print(f"\nGrid: {grid['nx']} × {grid['ny']} = {grid['nx']*grid['ny']} points")
    print(f"Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km")
    
    # Output directory
    output_dir = "/home/chawas/deployed/charara_github/swan4151/bin/"
    os.makedirs(output_dir, exist_ok=True)
    
    # ERA5 data directory
    data_dir = "/home/chawas/deployed/charara_github/data/era5/debiased"
    
    if not os.path.exists(data_dir):
        print(f"\nERROR: Directory not found: {data_dir}")
        return
    
    # Find files
    print(f"\nSearching for ERA5 files in: {data_dir}")
    nc_files = find_era5_files(data_dir)
    
    if not nc_files:
        print("No NetCDF files found!")
        return
    
    print(f"Found {len(nc_files)} NetCDF files")
    
    # Process first file (you can loop through all files if needed)
    test_file = nc_files[0]
    print(f"\nProcessing: {os.path.basename(test_file)}")
    
    # Extract wind data (use time_index=0 for first time step)
    speed_grid, dir_grid, current_time = extract_wind_from_nc(test_file, grid['lon'], grid['lat'], time_index=0)
    
    if speed_grid is None:
        print("Failed to extract wind data")
        return
    
    # Verify shape
    print(f"\nGrid shape: {speed_grid.shape}")
    if len(speed_grid.shape) != 2:
        print(f"ERROR: Expected 2D grid, got shape {speed_grid.shape}")
        return
    
    # Calculate statistics
    print(f"\nWind Statistics for Nyenje Bay:")
    print(f"  Speed - Min: {np.min(speed_grid):.2f} m/s")
    print(f"  Speed - Max: {np.max(speed_grid):.2f} m/s")
    print(f"  Speed - Mean: {np.mean(speed_grid):.2f} m/s")
    print(f"  Speed - Std: {np.std(speed_grid):.2f} m/s")
    
    # Create wind file
    wind_file = os.path.join(output_dir, "nyenje_era5_wind.wnd")
    metadata = {'file': os.path.basename(test_file), 'time': current_time}
    create_swan_wind_file(speed_grid, dir_grid, current_time, wind_file, metadata)
    print(f"\n✅ Created wind file: {wind_file}")
    
    # Preview the wind file
    print("\n📄 Wind file preview (first 2 data rows):")
    with open(wind_file, 'r') as f:
        lines = f.readlines()
        data_lines = [l for l in lines if not l.startswith('!')]
        for line in data_lines[:2]:
            # Show first few values only
            values = line.strip().split()
            preview = " ".join(values[:6]) + " ..."
            print(f"  {preview}")
    
    # Create bathymetry file if it doesn't exist
    bathymetry_file = os.path.join(output_dir, "nyenje_bathymetry_8x7.bot")
    if not os.path.exists(bathymetry_file):
        print("\n📝 Creating default bathymetry file...")
        with open(bathymetry_file, 'w') as f:
            f.write("5.36 1.50 2.29 0.50 2.87 3.09 3.20 1.56 1.50\n")
            f.write("6.61 5.98 3.80 5.14 6.42 2.86 1.50 1.50 1.50\n")
            f.write("16.82 7.58 7.80 10.22 10.30 3.07 1.50 1.50 1.50\n")
            f.write("16.06 9.90 11.06 15.05 11.97 4.45 1.50 1.50 1.50\n")
            f.write("19.21 16.55 13.52 17.65 8.72 5.03 1.50 1.50 1.50\n")
            f.write("29.30 15.17 16.64 5.63 5.74 3.26 1.50 1.50 1.50\n")
            f.write("16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50\n")
            f.write("16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50\n")
    
    # Create SWAN input file
    swn_file = os.path.join(output_dir, "nyenje_era5_run.swn")
    create_swan_input_file(wind_file, bathymetry_file, swn_file)
    print(f"✅ Created SWAN input: {swn_file}")
    
    print("\n" + "=" * 60)
    print("✅ READY TO RUN SWAN!")
    print("=" * 60)
    print(f"\n  cd {output_dir}")
    print(f"  ./swan.exe nyenje_era5_run.swn")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
