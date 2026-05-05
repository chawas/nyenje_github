#!/usr/bin/env python3
"""
Extract first hour (2020-01-01 00:00) from ERA5 debiased data
Create SWAN wind file for Nyenje Bay (9×8 grid)
"""

import numpy as np
import xarray as xr
import pandas as pd
import os
from datetime import datetime

# Configuration
NX = 9   # points in X (West-East)
NY = 8   # points in Y (South-North)
DOMAIN_X = 4000.0
DOMAIN_Y = 3500.0
CENTER_LAT = -16.53
CENTER_LON = 28.83
DEBIAS_FACTOR = 0.718

# Input ERA5 file (adjust path as needed)
ERA5_FILE = "/home/chawas/deployed/charara_github/data/era5/debiased/era5_kariba_2020_01_corrected.nc"

# Output directory
OUTPUT_DIR = "nyenje_era5_debiased"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_grid():
    """Create 9×8 grid coordinates"""
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    
    lon = CENTER_LON + (X - DOMAIN_X/2) / 106000
    lat = CENTER_LAT + (Y - DOMAIN_Y/2) / 111000
    
    return lon, lat

def extract_wind_for_time(nc_file, lon_grid, lat_grid, time_index=0):
    """Extract U and V at specific time index"""
    try:
        ds = xr.open_dataset(nc_file, engine='netcdf4')
        
        # Find wind variables
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        
        if u10 is None or v10 is None:
            print(f"Wind variables not found in {nc_file}")
            return None, None, None
        
        # Interpolate to grid
        u_interp = u10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        v_interp = v10.interp(latitude=lat_grid[:,0], longitude=lon_grid[0,:], method='linear')
        
        # Get time
        times = u_interp.time.values
        
        # Extract at specified time
        if len(u_interp.shape) == 3:
            u_values = u_interp.isel(time=time_index).values * DEBIAS_FACTOR
            v_values = v_interp.isel(time=time_index).values * DEBIAS_FACTOR
            current_time = times[time_index]
        else:
            u_values = u_interp.values * DEBIAS_FACTOR
            v_values = v_interp.values * DEBIAS_FACTOR
            current_time = times[0] if len(times) > 0 else None
        
        ds.close()
        return u_values, v_values, current_time
        
    except Exception as e:
        print(f"Error: {e}")
        return None, None, None

def write_swan_wind_file(u_grid, v_grid, output_file):
    """Write wind file in SWAN format (8 rows, 18 numbers each)"""
    NY, NX = u_grid.shape
    
    with open(output_file, 'w') as f:
        for iy in range(NY):
            row = []
            for ix in range(NX):
                row.append(u_grid[iy, ix])
                row.append(v_grid[iy, ix])
            # Format with 3 decimal places
            line = ' '.join([f"{x:8.3f}" for x in row])
            f.write(line + '\n')
    
    return output_file

def main():
    print("=" * 60)
    print("Extracting ERA5 Debiased Wind for Nyenje Bay")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(ERA5_FILE):
        print(f"ERROR: File not found: {ERA5_FILE}")
        print("\nPlease update ERA5_FILE path to your debiased data")
        print("Looking for .nc files in common locations...")
        
        # Search for any ERA5 file
        import glob
        search_paths = [
            "/home/chawas/deployed/charara_github/data/era5/debiased/*.nc",
            "/home/chawas/deployed/era5_data/*.nc",
            "../data/era5/debiased/*.nc"
        ]
        for path in search_paths:
            files = glob.glob(path)
            if files:
                print(f"\nFound: {files[0]}")
                print(f"Use this file by updating ERA5_FILE variable")
                break
        return
    
    # Create grid
    lon_grid, lat_grid = create_grid()
    print(f"Grid: {NX}×{NY} = {NX*NY} points")
    
    # Extract wind
    print(f"\nReading: {os.path.basename(ERA5_FILE)}")
    u_grid, v_grid, current_time = extract_wind_for_time(ERA5_FILE, lon_grid, lat_grid, time_index=0)
    
    if u_grid is None:
        print("Failed to extract wind data")
        return
    
    print(f"Time: {pd.to_datetime(current_time)}")
    print(f"U shape: {u_grid.shape}")
    print(f"V shape: {v_grid.shape}")
    
    # Calculate statistics
    speed = np.sqrt(u_grid**2 + v_grid**2)
    print(f"\nWind Statistics:")
    print(f"  Speed - Min: {speed.min():.2f} m/s")
    print(f"  Speed - Max: {speed.max():.2f} m/s")
    print(f"  Speed - Mean: {speed.mean():.2f} m/s")
    
    # Create output filename with timestamp
    time_str = pd.to_datetime(current_time).strftime("%Y%m%d_%H%M")
    output_file = os.path.join(OUTPUT_DIR, f"nyenje_wind_{time_str}.wnd")
    
    # Write wind file
    write_swan_wind_file(u_grid, v_grid, output_file)
    print(f"\n✅ Created: {output_file}")
    
    # Preview first row
    print("\nFirst row preview:")
    with open(output_file, 'r') as f:
        first = f.readline().strip()
        print(f"  {first[:80]}...")
    
    return output_file

if __name__ == "__main__":
    result = main()
