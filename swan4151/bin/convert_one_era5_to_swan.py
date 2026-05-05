#!/usr/bin/env python3
"""
Convert ONE ERA5 debiased file to SWAN wind input for Nyenje Bay (9×8 grid)
"""

import numpy as np
import xarray as xr
import pandas as pd
import os

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

# Input ERA5 file - UPDATE THIS PATH
ERA5_FILE = "/home/chawas/deployed/charara_github/data/era5/debiased/era5_kariba_1971_01_corrected.nc"

# Output directory
OUTPUT_DIR = "/home/chawas/deployed/charara_github/swan4151/bin/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_nyenje_grid():
    """Create 9×8 grid of coordinates for Nyenje Bay"""
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    
    # Convert to geographic coordinates for ERA5 extraction
    lon = CENTER_LON + (X - DOMAIN_X/2) / 106000
    lat = CENTER_LAT + (Y - DOMAIN_Y/2) / 111000
    
    print(f"Grid: {NX}×{NY} = {NX*NY} points")
    print(f"Lon range: {lon.min():.4f}° to {lon.max():.4f}°")
    print(f"Lat range: {lat.min():.4f}° to {lat.max():.4f}°")
    
    return {'lon': lon, 'lat': lat, 'nx': NX, 'ny': NY}

def extract_uv_from_era5(nc_file, lon_grid, lat_grid, time_index=0):
    """Extract U and V components from ERA5 NetCDF file"""
    
    print(f"\nReading: {os.path.basename(nc_file)}")
    
    try:
        ds = xr.open_dataset(nc_file, engine='netcdf4')
        
        # Find wind variables
        u10 = None
        v10 = None
        
        if 'u10' in ds.variables:
            u10 = ds['u10']
            v10 = ds['v10']
            print("  Found variables: u10, v10")
        elif 'u10n' in ds.variables:
            u10 = ds['u10n']
            v10 = ds['v10n']
            print("  Found variables: u10n, v10n")
        else:
            # Search for wind variables
            for var in ds.variables:
                if 'u' in var.lower() and '10' in var:
                    u10 = ds[var]
                elif 'v' in var.lower() and '10' in var:
                    v10 = ds[var]
            if u10 and v10:
                print(f"  Found variables: {u10.name}, {v10.name}")
        
        if u10 is None or v10 is None:
            print(f"  ERROR: No wind variables found!")
            print(f"  Available: {list(ds.variables.keys())}")
            ds.close()
            return None, None, None
        
        # Interpolate to grid points
        print("  Interpolating to Nyenje grid...")
        u_interp = u10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        v_interp = v10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        
        # Get time
        times = u_interp.time.values
        print(f"  Time steps available: {len(times)}")
        
        # Extract at specified time index
        if len(u_interp.shape) == 3:
            u_values = u_interp.isel(time=time_index).values
            v_values = v_interp.isel(time=time_index).values
            current_time = times[time_index]
        else:
            u_values = u_interp.values
            v_values = v_interp.values
            current_time = times[0] if len(times) > 0 else None
        
        # Apply debiasing factor
        u_values = u_values * DEBIAS_FACTOR
        v_values = v_values * DEBIAS_FACTOR
        
        ds.close()
        
        print(f"  Time: {pd.to_datetime(current_time)}")
        print(f"  U shape: {u_values.shape}")
        print(f"  V shape: {v_values.shape}")
        
        return u_values, v_values, current_time
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return None, None, None

def write_swan_wind_file(u_grid, v_grid, output_file):
    """Write SWAN wind file (exactly 8 rows, 18 numbers each)"""
    
    NY, NX = u_grid.shape
    
    with open(output_file, 'w') as f:
        for iy in range(NY):
            row = ""
            for ix in range(NX):
                row += f" {u_grid[iy, ix]:8.3f} {v_grid[iy, ix]:8.3f}"
            f.write(row.strip() + "\n")
    
    print(f"\n✅ Created: {output_file}")
    print(f"   Rows: {NY}, Columns: {NX*2} numbers per row")

def create_test_swan_input(wind_file, output_swn_file):
    """Create SWAN input file for testing"""
    
    swan_content = f"""PROJECT 'Nyenje' 'TEST01' 'Test with ERA5 wind' ' ' ' '
MODE STATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_8x7.bot' 1 0 FREE
INPGRID WIND REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP WIND 1.0 '{os.path.basename(wind_file)}' 1 0 FREE
GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73
NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01
BLOCK 'COMPGRID' NOHEADER 'test_wave_output.txt' LAYOUT 4 HSIGN TM01 DIR
COMPUTE
STOP
"""
    with open(output_swn_file, 'w') as f:
        f.write(swan_content)
    
    print(f"✅ Created SWAN input: {output_swn_file}")

def main():
    print("=" * 60)
    print("CONVERT ONE ERA5 FILE TO SWAN WIND INPUT")
    print("=" * 60)
    
    # Check if ERA5 file exists
    if not os.path.exists(ERA5_FILE):
        print(f"\n❌ ERA5 file not found: {ERA5_FILE}")
        print("\nPlease update the ERA5_FILE path in the script.")
        print("Current search paths:")
        print("  /home/chawas/deployed/charara_github/data/era5/debiased/")
        return
    
    # Create grid
    print("\n📍 Creating Nyenje Bay grid...")
    grid = create_nyenje_grid()
    
    # Extract U/V from ERA5
    print("\n🔄 Extracting U/V from ERA5...")
    u_grid, v_grid, current_time = extract_uv_from_era5(ERA5_FILE, grid['lon'], grid['lat'], time_index=0)
    
    if u_grid is None:
        print("\n❌ Extraction failed!")
        return
    
    # Calculate wind speed for verification
    speed = np.sqrt(u_grid**2 + v_grid**2)
    print(f"\n📊 Wind Statistics for Nyenje Bay:")
    print(f"   Wind Speed - Min: {speed.min():.2f} m/s")
    print(f"   Wind Speed - Max: {speed.max():.2f} m/s")
    print(f"   Wind Speed - Mean: {speed.mean():.2f} m/s")
    print(f"   U component - Mean: {u_grid.mean():.2f} m/s")
    print(f"   V component - Mean: {v_grid.mean():.2f} m/s")
    
    # Write SWAN wind file
    wind_file = os.path.join(OUTPUT_DIR, "nyenje_test_wind.wnd")
    write_swan_wind_file(u_grid, v_grid, wind_file)
    
    # Preview the wind file
    print("\n📄 Wind file preview (first row):")
    with open(wind_file, 'r') as f:
        first_row = f.readline().strip()
        values = first_row.split()
        print(f"   {values[:6]}...")
    
    # Create SWAN input file
    swn_file = os.path.join(OUTPUT_DIR, "nyenje_test_run.swn")
    create_test_swan_input(wind_file, swn_file)
    
    print("\n" + "=" * 60)
    print("✅ READY TO TEST SWAN!")
    print("=" * 60)
    print(f"\n  cd {OUTPUT_DIR}")
    print(f"  ./swan.exe nyenje_test_run.swn")
    print("\n  Check output: cat test_wave_output.txt")
    print("=" * 60)

if __name__ == "__main__":
    main()
