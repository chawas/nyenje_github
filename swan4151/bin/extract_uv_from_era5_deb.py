#!/usr/bin/env python3
"""
Extract U and V wind components directly from ERA5 debiased NetCDF files
Create SWAN wind input file for Nyenje Bay (9×8 grid)

This is the CORRECT approach because SWAN expects U/V components directly.
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
    
    # Convert to geographic coordinates for ERA5 extraction
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

def extract_uv_from_nc(nc_file, lon_grid, lat_grid, time_index=0):
    """
    Extract U and V components directly from NetCDF file
    
    Returns:
        u_grid: 2D array (NY, NX) of u components (m/s)
        v_grid: 2D array (NY, NX) of v components (m/s)
        time: timestamp
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
                if 'u' in var.lower() and '10' in var and 'wind' in var.lower():
                    u10 = ds[var]
                elif 'v' in var.lower() and '10' in var and 'wind' in var.lower():
                    v10 = ds[var]
        
        if u10 is None or v10 is None:
            print(f"  Warning: No wind variables found in {os.path.basename(nc_file)}")
            print(f"  Available variables: {list(ds.variables.keys())}")
            ds.close()
            return None, None, None
        
        # Interpolate to grid points
        u_interp = u10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        v_interp = v10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        
        # Get time values
        times = u_interp.time.values
        
        # Extract at specified time index
        if len(u_interp.shape) == 3:
            u_values = u_interp.isel(time=time_index).values
            v_values = v_interp.isel(time=time_index).values
            current_time = times[time_index] if time_index < len(times) else times[0]
        else:
            u_values = u_interp.values
            v_values = v_interp.values
            current_time = times[0] if len(times) > 0 else None
        
        # Apply debiasing factor
        u_values = u_values * DEBIAS_FACTOR
        v_values = v_values * DEBIAS_FACTOR
        
        ds.close()
        
        return u_values, v_values, current_time
        
    except Exception as e:
        print(f"  Error processing {os.path.basename(nc_file)}: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def create_swan_wind_file(u_grid, v_grid, time, output_file, metadata=None):
    """
    Create SWAN wind input file with U and V components
    
    SWAN expects: u10 (m/s) v10 (m/s) for each grid point
    Format: u v pairs, space separated
    Grid order: South to North, West to East (IDLA=1)
    """
    
    NY, NX = u_grid.shape
    
    with open(output_file, 'w') as f:
        f.write("! SWAN wind input file for Nyenje Bay - U/V COMPONENTS\n")
        f.write(f"! Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if metadata:
            f.write(f"! Source: {metadata.get('file', 'Unknown')}\n")
            if time:
                f.write(f"! Time: {pd.to_datetime(time)}\n")
            f.write(f"! Debiasing factor: {DEBIAS_FACTOR}\n")
        f.write("! Format: u10 (m/s) v10 (m/s) for each grid point\n")
        f.write("! Grid: 9 columns (West→East) × 8 rows (South→North)\n")
        f.write("! Reading order: IDLA=1 (left to right, top to bottom)\n\n")
        
        # Write data rows (South to North, West to East)
        for iy in range(NY):
            row_str = ""
            for ix in range(NX):
                u_val = u_grid[iy, ix]
                v_val = v_grid[iy, ix]
                row_str += f" {u_val:8.3f} {v_val:8.3f}"
            f.write(row_str.strip() + "\n")
    
    return output_file

def create_swan_input_file(wind_file, bathymetry_file, output_swn_file):
    """Create SWAN input file"""
    
    swan_content = f"""!===============================================================================
! SWAN INPUT FILE FOR NYENJE BAY - WITH ERA5 U/V WIND
! Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
!===============================================================================

PROJECT 'Nyenje' 'ERA5' 'Wave simulation with ERA5 wind (U/V components)' ' ' ' '

MODE STATIONARY TWODIMENSIONAL

COORDINATES CARTESIAN

! Computational grid: 4 km × 3.5 km, 500m resolution
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

! Bathymetry
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 '{os.path.basename(bathymetry_file)}' 1 0 FREE

! Wind from ERA5 - U/V components
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
    print("=" * 70)
    print("NYENJE BAY - EXTRACT U/V FROM ERA5 DEBIASED WIND")
    print("=" * 70)
    
    # Create grid
    grid = create_nyenje_grid()
    print(f"\n📍 Grid: {grid['nx']} × {grid['ny']} = {grid['nx']*grid['ny']} points")
    print(f"   Domain: {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km")
    
    # Output directory
    output_dir = "/home/chawas/deployed/charara_github/swan4151/bin/"
    os.makedirs(output_dir, exist_ok=True)
    
    # ERA5 data directory
    data_dir = "/home/chawas/deployed/charara_github/data/era5/debiased"
    
    if not os.path.exists(data_dir):
        print(f"\n❌ Directory not found: {data_dir}")
        print("   Please update the data_dir path")
        return
    
    # Find files
    print(f"\n🔍 Searching for ERA5 files in: {data_dir}")
    nc_files = find_era5_files(data_dir)
    
    if not nc_files:
        print("❌ No NetCDF files found!")
        return
    
    print(f"✅ Found {len(nc_files)} NetCDF files")
    
    # Process first file (for demonstration)
    test_file = nc_files[0]
    print(f"\n📁 Processing: {os.path.basename(test_file)}")
    
    # Extract U and V directly
    u_grid, v_grid, current_time = extract_uv_from_nc(test_file, grid['lon'], grid['lat'], time_index=0)
    
    if u_grid is None:
        print("❌ Failed to extract U/V data")
        return
    
    # Verify shape
    print(f"\n✅ Extracted U/V data")
    print(f"   U grid shape: {u_grid.shape}")
    print(f"   V grid shape: {v_grid.shape}")
    print(f"   Time: {pd.to_datetime(current_time)}")
    
    # Calculate statistics
    print(f"\n📊 Wind Statistics for Nyenje Bay (9×8 grid):")
    print(f"   U component - Min: {np.min(u_grid):.3f} m/s")
    print(f"   U component - Max: {np.max(u_grid):.3f} m/s")
    print(f"   U component - Mean: {np.mean(u_grid):.3f} m/s")
    print(f"   V component - Min: {np.min(v_grid):.3f} m/s")
    print(f"   V component - Max: {np.max(v_grid):.3f} m/s")
    print(f"   V component - Mean: {np.mean(v_grid):.3f} m/s")
    
    # Calculate wind speed for info
    speed = np.sqrt(u_grid**2 + v_grid**2)
    print(f"\n   Wind Speed - Min: {np.min(speed):.3f} m/s")
    print(f"   Wind Speed - Max: {np.max(speed):.3f} m/s")
    print(f"   Wind Speed - Mean: {np.mean(speed):.3f} m/s")
    
    # Create SWAN wind file
    wind_file = os.path.join(output_dir, "nyenje_era5_uv.wnd")
    metadata = {'file': os.path.basename(test_file), 'time': current_time}
    create_swan_wind_file(u_grid, v_grid, current_time, wind_file, metadata)
    print(f"\n✅ Created wind file: {wind_file}")
    
    # Preview the wind file
    print("\n📄 Wind file preview (first 2 data rows):")
    with open(wind_file, 'r') as f:
        lines = f.readlines()
        data_lines = [l for l in lines if not l.startswith('!') and l.strip()]
        for line in data_lines[:2]:
            values = line.strip().split()
            preview = " ".join(values[:6]) + " ..."
            print(f"   {preview}")
    
    # Create bathymetry if needed
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
    swn_file = os.path.join(output_dir, "nyenje_era5_uv_run.swn")
    create_swan_input_file(wind_file, bathymetry_file, swn_file)
    print(f"✅ Created SWAN input: {swn_file}")
    
    print("\n" + "=" * 70)
    print("✅ READY TO RUN SWAN!")
    print("=" * 70)
    print(f"\n  cd {output_dir}")
    print(f"  ./swan.exe nyenje_era5_uv_run.swn")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
