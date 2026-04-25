#!/usr/bin/env python3
"""
Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Lake Kariba
Complete wind, wave, and SWAN wave modeling analysis

KEY CONCEPT:
- Bathymetry: CONSTANT (loaded once from nyenje_bathymetry_9x8.bot)
- Wind: VARIABLE (changes for each hour/timestep from ERA5 debiased data)
- SWAN runs: Each hour gets its own wind file, same bathymetry
"""

import streamlit as st

# Page Configuration - MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="Key Informatics - Nyenje Bay Wind/Waves Analysis Tool",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"  # This ensures sidebar is visible
)

# Import libraries after page config
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob
import warnings
import re
import json
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# Optional imports with fallbacks
try:
    import xarray as xr
    XARRAY_AVAILABLE = True
except ImportError:
    XARRAY_AVAILABLE = False

try:
    from scipy.interpolate import RegularGridInterpolator
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Custom CSS for bolder fonts and sidebar
st.markdown("""
<style>
    .stMetric label, .stMetric .metric-value, .stMetric .metric-delta {
        font-weight: bold !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-weight: bold !important;
    }
    /* Ensure sidebar is visible */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        min-width: 300px;
    }
    .stButton button {
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Constants
# ============================================================================

GUST_FACTORS = {
    '3sec': 1.45,
    '10sec': 1.35,
    '3min': 1.15,
    '10min': 1.00,
}

# Nyenje Bay Grid Parameters
NX = 9
NY = 8
DOMAIN_X = 4000.0
DOMAIN_Y = 3500.0

# Path to CONSTANT bathymetry file (same for all runs)
BASE_DIR = "/home/chawas/deployed/nyenje_github"
BATHYMETRY_FILE = os.path.join(BASE_DIR, "data/bathymetry/nyenje_bathymetry_9x8.bot")

# Directory Structure
RAW_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/raw")
DEBIASED_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/debiased")
CCMP_DIR = os.path.join(BASE_DIR, "data/ccmp")
VALIDATION_DIR = os.path.join(BASE_DIR, "data/validation")

# SWAN directories
SWAN_BASE_DIR = os.path.join(BASE_DIR, "swan")
SWAN_BIN_DIR = os.path.join(SWAN_BASE_DIR, "bin")
SWAN_EXE = os.path.join(SWAN_BIN_DIR, "swan.exe")
SWAN_INPUT_FILE = os.path.join(SWAN_BASE_DIR, "INPUT")

# Wind files for SWAN (output from extraction)
WIND_FILES_DIR = os.path.join(BASE_DIR, "data/wind_files/nyenje_era5_debiased")

# Output directories for SWAN results
SWAN_OUTPUTS_DIR = os.path.join(BASE_DIR, "swan/outputs")
SWAN_INPUTS_ARCHIVE = os.path.join(BASE_DIR, "swan/inputs_archive")

# Create all directories
os.makedirs(RAW_ERA5_DIR, exist_ok=True)
os.makedirs(DEBIASED_ERA5_DIR, exist_ok=True)
os.makedirs(CCMP_DIR, exist_ok=True)
os.makedirs(VALIDATION_DIR, exist_ok=True)
os.makedirs(WIND_FILES_DIR, exist_ok=True)
os.makedirs(SWAN_OUTPUTS_DIR, exist_ok=True)
os.makedirs(SWAN_INPUTS_ARCHIVE, exist_ok=True)

# Debiasing factor (ERA5 vs CCMP)
DEBIAS_FACTOR = 0.718

# Tropical cyclones
TROPICAL_CYCLONES = [
    {'name': 'Idai', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba - dissipated over Mozambique'},
    {'name': 'Kenneth', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba - remained in northern Mozambique'},
    {'name': 'Eloise', 'year': 2021, 'impact': 'Did NOT reach Lake Kariba - weakened over land'},
    {'name': 'Ana', 'year': 2022, 'impact': 'Did NOT reach Lake Kariba - heavy rains only'},
    {'name': 'Freddy', 'year': 2023, 'impact': 'Did NOT reach Lake Kariba - record-long but stayed east'},
    {'name': 'Cheneso', 'year': 2023, 'impact': 'Did NOT reach Lake Kariba - weakened before Zambia'},
]

# ============================================================================
# Load CONSTANT Bathymetry
# ============================================================================

def load_real_bathymetry():
    """Load the actual Nyenje Bay bathymetry from file (CONSTANT)"""
    try:
        if not os.path.exists(BATHYMETRY_FILE):
            return None
        with open(BATHYMETRY_FILE, 'r') as f:
            lines = f.readlines()
        
        depth_grid = []
        for line in lines:
            if line.strip() and not line.startswith('!'):
                values = [float(x) for x in line.strip().split()]
                if len(values) == NX:
                    depth_grid.append(values)
        
        if len(depth_grid) == NY:
            return np.array(depth_grid)
        return None
    except Exception as e:
        return None

# Load the real bathymetry ONCE at startup (CONSTANT)
REAL_BATHYMETRY = load_real_bathymetry()

# ============================================================================
# Helper Functions
# ============================================================================

def calculate_wind_direction(u10, v10):
    wind_dir = np.arctan2(u10, v10) * 180 / np.pi
    wind_dir = 270 - wind_dir
    return wind_dir % 360

def wind_direction_to_cardinal(degrees):
    directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = int((degrees + 11.25) / 22.5) % 16
    return directions[idx]

def calculate_circular_mean(directions):
    dir_rad = np.radians(directions)
    dir_rad = dir_rad[~np.isnan(dir_rad)]
    if len(dir_rad) == 0:
        return np.nan, 0
    sin_mean = np.mean(np.sin(dir_rad))
    cos_mean = np.mean(np.cos(dir_rad))
    mean_direction = np.degrees(np.arctan2(sin_mean, cos_mean)) % 360
    mean_strength = np.sqrt(sin_mean**2 + cos_mean**2)
    return mean_direction, mean_strength

def calculate_wind_averages(wind_speed_series, time_axis):
    ws_series = pd.Series(wind_speed_series, index=time_axis)
    wind_3min = ws_series.rolling(window=3, center=True, min_periods=1).mean()
    wind_10min = ws_series.rolling(window=10, center=True, min_periods=1).mean()
    gust_3sec = ws_series * GUST_FACTORS['3sec']
    gust_10sec = ws_series * GUST_FACTORS['10sec']
    return {
        'wind_3min': wind_3min.values,
        'wind_10min': wind_10min.values,
        'gust_3sec': gust_3sec.values,
        'gust_10sec': gust_10sec.values
    }

def create_wind_rose(speeds, directions, title):
    speed_bins = [0, 2, 4, 6, 8, 10, 15, 20]
    speed_labels = ['0-2', '2-4', '4-6', '6-8', '8-10', '10-15', '15-20']
    dir_bins = np.arange(0, 361, 22.5)
    dir_centers = (dir_bins[:-1] + dir_bins[1:]) / 2
    hist, _, _ = np.histogram2d(directions, speeds, bins=[dir_bins, speed_bins])
    hist = hist / hist.sum() * 100
    fig = go.Figure()
    colors = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61']
    for i, (label, color) in enumerate(zip(speed_labels, colors)):
        if i < hist.shape[1]:
            fig.add_trace(go.Barpolar(
                r=hist[:, i], theta=dir_centers, name=label,
                marker_color=color, marker_line_color='black',
                marker_line_width=0.5, opacity=0.8
            ))
    mean_speed = np.mean(speeds)
    calm_percent = np.sum(speeds < 1) / len(speeds) * 100
    fig.update_layout(
        title=f"{title}<br>Mean: {mean_speed:.2f} m/s | Calm: {calm_percent:.1f}%",
        polar=dict(
            angularaxis=dict(direction='clockwise', rotation=90,
                             tickvals=[0,45,90,135,180,225,270,315],
                             ticktext=['N','NE','E','SE','S','SW','W','NW']),
            radialaxis=dict(ticksuffix='%', angle=45)
        ),
        legend_title="Wind Speed (m/s)", height=600
    )
    return fig

def create_wind_parameters_plot(wind_df):
    if wind_df is None or len(wind_df) == 0:
        return None
    
    df_sample = wind_df.iloc[:500] if len(wind_df) > 500 else wind_df
    
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=('Wind Speed (Hourly)', '3-Minute Average',
                        '10-Minute Average', '3-Second Gust',
                        '10-Second Gust', 'Wind Direction'),
        vertical_spacing=0.12
    )
    
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_hourly'],
                             mode='lines', name='Hourly', line=dict(color='blue', width=1)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_3min'],
                             mode='lines', name='3-min', line=dict(color='green', width=1.5)),
                  row=1, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_10min'],
                             mode='lines', name='10-min', line=dict(color='orange', width=1.5)),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_3sec'],
                             mode='lines', name='3s Gust', line=dict(color='red', width=1.5)),
                  row=2, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_10sec'],
                             mode='lines', name='10s Gust', line=dict(color='purple', width=1.5)),
                  row=3, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_direction'],
                             mode='lines', name='Direction', line=dict(color='brown', width=1)),
                  row=3, col=2)
    
    fig.update_layout(height=900, title_text="Wind Parameters Analysis", showlegend=False)
    fig.update_xaxes(title_text="Time", row=3, col=1)
    fig.update_xaxes(title_text="Time", row=3, col=2)
    fig.update_yaxes(title_text="Wind Speed (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="Wind Speed (m/s)", row=1, col=2)
    fig.update_yaxes(title_text="Wind Speed (m/s)", row=2, col=1)
    fig.update_yaxes(title_text="Wind Speed (m/s)", row=2, col=2)
    fig.update_yaxes(title_text="Wind Speed (m/s)", row=3, col=1)
    fig.update_yaxes(title_text="Direction (°)", row=3, col=2)
    
    return fig

# ============================================================================
# JONSWAP Wave Calculation
# ============================================================================

def calculate_wave_height(wind_speed, fetch_km=4):
    g = 9.81
    fetch_m = fetch_km * 1000
    x_tilde = g * fetch_m / (wind_speed**2 + 0.1)
    hs = 0.0016 * (wind_speed**2 / g) * np.sqrt(x_tilde)
    tp = 0.286 * (wind_speed / g) * (x_tilde ** 0.33)
    return hs, tp

# ============================================================================
# SWAN Wave Distribution using CONSTANT Bathymetry
# ============================================================================

def generate_swan_wave_distribution(wind_speed, wind_direction):
    """Generate wave height distribution for Nyenje Bay 9x8 grid"""
    if REAL_BATHYMETRY is not None:
        depth = REAL_BATHYMETRY
    else:
        x = np.linspace(0, DOMAIN_X, NX)
        y = np.linspace(0, DOMAIN_Y, NY)
        X, Y = np.meshgrid(x, y)
        depth = 30 - (Y / DOMAIN_Y) * 28.5
        depth = np.maximum(depth, 1.5)
    
    x = np.linspace(0, DOMAIN_X, NX)
    y = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x, y)
    
    if 45 <= wind_direction <= 135:
        fetch = (DOMAIN_X - X) / 1000
    elif 135 < wind_direction <= 225:
        fetch = Y / 1000
    elif 225 < wind_direction <= 315:
        fetch = X / 1000
    else:
        fetch = (DOMAIN_Y - Y) / 1000
    
    fetch = np.maximum(fetch, 0.5)
    
    g = 9.81
    hs_base = 0.0016 * (wind_speed**2 / g) * np.sqrt(g * fetch * 1000 / (wind_speed**2 + 0.1))
    tp_base = 0.286 * (wind_speed / g) * (g * fetch * 1000 / (wind_speed**2 + 0.1)) ** 0.33
    
    gamma = 0.73
    max_wave_height = gamma * depth
    hs = np.minimum(hs_base, max_wave_height)
    tp = np.minimum(tp_base, 3.0 * np.sqrt(depth / g))
    
    return hs, tp, depth

# ============================================================================
# Data Processing Functions
# ============================================================================

def create_nyenje_grid():
    """Create the 9x8 grid coordinates for Nyenje Bay"""
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    lon = 28.83 + (X - DOMAIN_X/2) / 106000
    lat = -16.53 + (Y - DOMAIN_Y/2) / 111000
    return {'lon': lon, 'lat': lat, 'nx': NX, 'ny': NY, 'x': x_coords, 'y': y_coords}

def safe_open_dataset(file_path):
    """Safely open NetCDF/GRIB files"""
    if not XARRAY_AVAILABLE:
        return None
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext in ['.grib', '.grb', '.grib2']:
            ds = xr.open_dataset(file_path, engine='cfgrib', backend_kwargs={'errors': 'ignore'})
        else:
            ds = xr.open_dataset(file_path, engine='netcdf4')
        return ds
    except Exception:
        try:
            ds = xr.open_dataset(file_path)
            return ds
        except:
            return None

# ============================================================================
# DEBIASING FUNCTIONS
# ============================================================================

def debias_era5_file(input_file, output_dir, debias_factor=DEBIAS_FACTOR):
    """Apply debiasing factor to ERA5 file and save to debiased directory"""
    ds = safe_open_dataset(input_file)
    if ds is None:
        return False, None
    
    try:
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        
        if u10 is None or v10 is None:
            ds.close()
            return False, None
        
        # Apply debiasing
        u10_debiased = u10 * debias_factor
        v10_debiased = v10 * debias_factor
        
        # Create output filename
        basename = os.path.basename(input_file)
        name, ext = os.path.splitext(basename)
        output_file = os.path.join(output_dir, f"{name}_debiased{ext}")
        
        # Save to new file
        ds_debiased = xr.Dataset({
            'u10': u10_debiased,
            'v10': v10_debiased
        })
        
        # Copy coordinates and attributes
        ds_debiased = ds_debiased.assign_coords({
            'longitude': ds.longitude,
            'latitude': ds.latitude,
            'time': ds.time
        })
        
        ds_debiased.to_netcdf(output_file)
        ds.close()
        return True, output_file
        
    except Exception as e:
        st.error(f"Debiasing error: {e}")
        ds.close()
        return False, None

def batch_debias_era5(input_dir, output_dir, years=None, progress_callback=None):
    """Batch debias multiple ERA5 files"""
    all_files = glob.glob(os.path.join(input_dir, "*.nc")) + glob.glob(os.path.join(input_dir, "*.nc4"))
    
    if years:
        filtered_files = []
        for f in all_files:
            for year in years:
                if str(year) in f:
                    filtered_files.append(f)
                    break
        all_files = filtered_files
    
    if not all_files:
        return 0, []
    
    debiased_files = []
    for i, file_path in enumerate(all_files):
        if progress_callback:
            progress_callback(i+1, len(all_files), os.path.basename(file_path))
        success, output = debias_era5_file(file_path, output_dir)
        if success:
            debiased_files.append(output)
    
    return len(debiased_files), debiased_files

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_debiased_data(era5_file, ccmp_file, target_lat=-16.53, target_lon=28.83):
    """Compare ERA5 (original vs debiased) with CCMP data"""
    ds_era5 = safe_open_dataset(era5_file)
    ds_ccmp = safe_open_dataset(ccmp_file)
    
    if ds_era5 is None or ds_ccmp is None:
        return None
    
    try:
        u_era5 = ds_era5.get('u10', ds_era5.get('u10n', None))
        v_era5 = ds_era5.get('v10', ds_era5.get('v10n', None))
        
        u_ccmp = ds_ccmp.get('uwnd', ds_ccmp.get('u10', None))
        v_ccmp = ds_ccmp.get('vwnd', ds_ccmp.get('v10', None))
        
        if u_era5 is None or v_era5 is None or u_ccmp is None or v_ccmp is None:
            ds_era5.close()
            ds_ccmp.close()
            return None
        
        lat_coord_era5 = 'latitude' if 'latitude' in ds_era5.coords else 'lat'
        lon_coord_era5 = 'longitude' if 'longitude' in ds_era5.coords else 'lon'
        
        u_era5_point = u_era5.sel({lat_coord_era5: target_lat, lon_coord_era5: target_lon}, method='nearest')
        v_era5_point = v_era5.sel({lat_coord_era5: target_lat, lon_coord_era5: target_lon}, method='nearest')
        
        speed_era5 = np.sqrt(u_era5_point**2 + v_era5_point**2)
        speed_era5_debiased = speed_era5 * DEBIAS_FACTOR
        
        if 'time' in u_ccmp.dims:
            u_ccmp_mean = u_ccmp.mean(dim='time').values
            v_ccmp_mean = v_ccmp.mean(dim='time').values
            speed_ccmp = np.sqrt(u_ccmp_mean**2 + v_ccmp_mean**2)
        else:
            speed_ccmp = np.sqrt(u_ccmp.values**2 + v_ccmp.values**2)
        
        ds_era5.close()
        ds_ccmp.close()
        
        return {
            'era5_original': float(speed_era5.mean().values),
            'era5_debiased': float(speed_era5_debiased.mean().values),
            'ccmp': float(speed_ccmp) if isinstance(speed_ccmp, (int, float)) else float(speed_ccmp.mean()),
            'bias_original': float(speed_era5.mean().values - speed_ccmp.mean()) if hasattr(speed_ccmp, 'mean') else 0,
            'bias_debiased': float(speed_era5_debiased.mean().values - speed_ccmp.mean()) if hasattr(speed_ccmp, 'mean') else 0
        }
    except Exception as e:
        ds_era5.close()
        ds_ccmp.close()
        return None

# ============================================================================
# SWAN WIND FILE EXTRACTION FUNCTIONS
# ============================================================================

def extract_single_wind_file(era5_file, output_dir, timestamp=None, debias_factor=1.0):
    """Extract a single SWAN wind file from a specific ERA5 file and timestep"""
    if not SCIPY_AVAILABLE:
        st.error("scipy not available")
        return None
    
    ds = safe_open_dataset(era5_file)
    if ds is None:
        return None
    
    try:
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        
        if u10 is None or v10 is None:
            ds.close()
            return None
        
        grid = create_nyenje_grid()
        target_lons = grid['lon'][0, :]
        target_lats = grid['lat'][:, 0]
        
        lat_coord = 'latitude' if 'latitude' in u10.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in u10.coords else 'lon'
        
        lats = u10[lat_coord].values
        lons = u10[lon_coord].values
        
        if lons[0] > lons[-1]:
            lons = lons[::-1]
            u10 = u10.isel({lon_coord: slice(None, None, -1)})
            v10 = v10.isel({lon_coord: slice(None, None, -1)})
        
        if lats[0] > lats[-1]:
            lats = lats[::-1]
            u10 = u10.isel({lat_coord: slice(None, None, -1)})
            v10 = v10.isel({lat_coord: slice(None, None, -1)})
        
        target_points = []
        for ilat in range(len(target_lats)):
            for ilon in range(len(target_lons)):
                target_points.append([target_lats[ilat], target_lons[ilon]])
        target_points = np.array(target_points)
        
        time_dims = [d for d in u10.dims if 'time' in d.lower()]
        
        if len(time_dims) > 0 and timestamp is not None:
            times = u10[time_dims[0]].values
            time_idx = np.argmin(np.abs(pd.to_datetime(times) - pd.to_datetime(timestamp)))
            u_slice = u10.isel({time_dims[0]: time_idx}).values
            v_slice = v10.isel({time_dims[0]: time_idx}).values
            time_str = pd.to_datetime(times[time_idx]).strftime("%Y%m%d_%H%M")
        elif len(time_dims) > 0:
            u_slice = u10.isel({time_dims[0]: 0}).values
            v_slice = v10.isel({time_dims[0]: 0}).values
            time_str = "single"
        else:
            u_slice = u10.values
            v_slice = v10.values
            time_str = "single"
        
        u_interp = RegularGridInterpolator((lats, lons), u_slice, bounds_error=False, fill_value=None)
        v_interp = RegularGridInterpolator((lats, lons), v_slice, bounds_error=False, fill_value=None)
        
        u_vals = u_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
        v_vals = v_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
        
        os.makedirs(output_dir, exist_ok=True)
        wind_file = os.path.join(output_dir, f"nyenje_wind_{time_str}.wnd")
        
        with open(wind_file, 'w') as f:
            for iy in range(len(target_lats)):
                row = []
                for ix in range(len(target_lons)):
                    row.append(u_vals[iy, ix])
                    row.append(v_vals[iy, ix])
                f.write(' '.join([f"{x:8.3f}" for x in row]) + '\n')
        
        ds.close()
        return wind_file
        
    except Exception as e:
        st.error(f"Extraction error: {e}")
        ds.close()
        return None

def batch_extract_swan_files(input_dir, output_dir, year=None, debias_factor=1.0, progress_callback=None):
    """Batch extract SWAN wind files from multiple ERA5 files"""
    if year:
        files = glob.glob(os.path.join(input_dir, f"*{year}*.nc"))
        files.extend(glob.glob(os.path.join(input_dir, str(year), "*.nc")))
    else:
        files = glob.glob(os.path.join(input_dir, "*.nc")) + glob.glob(os.path.join(input_dir, "*.nc4"))
    
    if not files:
        return 0, []
    
    total_extracted = 0
    all_files = []
    
    for i, nc_file in enumerate(files):
        if progress_callback:
            progress_callback(i+1, len(files), os.path.basename(nc_file))
        
        ds = safe_open_dataset(nc_file)
        if ds is None:
            continue
        
        try:
            u10 = ds.get('u10', ds.get('u10n', None))
            if u10 is None:
                ds.close()
                continue
            
            time_dims = [d for d in u10.dims if 'time' in d.lower()]
            if len(time_dims) > 0:
                n_times = len(u10[time_dims[0]])
                for t_idx in range(n_times):
                    temp_file = extract_single_wind_file(nc_file, output_dir, None, debias_factor)
                    if temp_file:
                        all_files.append(temp_file)
                        total_extracted += 1
            else:
                temp_file = extract_single_wind_file(nc_file, output_dir, None, debias_factor)
                if temp_file:
                    all_files.append(temp_file)
                    total_extracted += 1
            
            ds.close()
        except Exception as e:
            ds.close()
            continue
    
    return total_extracted, all_files

def get_existing_wind_files(wind_dir):
    """Get list of already extracted wind files"""
    wind_files = []
    if os.path.exists(wind_dir):
        for root, dirs, files in os.walk(wind_dir):
            for file in files:
                if file.endswith('.wnd'):
                    wind_files.append(os.path.join(root, file))
    return wind_files

# ============================================================================
# Statistics Processing Functions (for PROCESS DATA tab)
# ============================================================================

def extract_wind_from_file(file_path, target_lat=-16.53, target_lon=28.83):
    """Extract wind data from a single file for statistics"""
    ds = safe_open_dataset(file_path)
    if ds is None:
        return None
    try:
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        
        if u10 is None or v10 is None:
            ds.close()
            return None
        
        lat_coord = None
        lon_coord = None
        for coord in ['latitude', 'lat', 'y']:
            if coord in ds.coords:
                lat_coord = coord
                break
        for coord in ['longitude', 'lon', 'x']:
            if coord in ds.coords:
                lon_coord = coord
                break
        if lat_coord is None or lon_coord is None:
            ds.close()
            return None
        
        try:
            u_at_point = u10.sel({lat_coord: target_lat, lon_coord: target_lon}, method='nearest')
            v_at_point = v10.sel({lat_coord: target_lat, lon_coord: target_lon}, method='nearest')
        except:
            u_at_point = u10.sel({lon_coord: target_lon, lat_coord: target_lat}, method='nearest')
            v_at_point = v10.sel({lon_coord: target_lon, lat_coord: target_lat}, method='nearest')
        
        time_dim = None
        for dim in u_at_point.dims:
            if 'time' in dim.lower():
                time_dim = dim
                break
        
        if time_dim:
            times = u_at_point[time_dim].values
            u_values = u_at_point.values
            v_values = v_at_point.values
        else:
            times = [datetime.now()]
            u_values = [float(u_at_point.values)] if np.isscalar(u_at_point.values) else u_at_point.values.flatten()
            v_values = [float(v_at_point.values)] if np.isscalar(v_at_point.values) else v_at_point.values.flatten()
        
        u_values = np.array(u_values).flatten()
        v_values = np.array(v_values).flatten()
        
        results = []
        for i in range(min(len(u_values), len(times))):
            u_val = float(u_values[i])
            v_val = float(v_values[i])
            speed = np.sqrt(u_val**2 + v_val**2)
            direction = calculate_wind_direction(u_val, v_val)
            results.append({
                'time': times[i] if i < len(times) else datetime.now(),
                'u': u_val,
                'v': v_val,
                'speed': speed,
                'direction': direction
            })
        ds.close()
        return results
    except Exception:
        ds.close()
        return None

def process_all_files(data_dir, target_lat=-16.53, target_lon=28.83, progress_callback=None):
    """Process all ERA5 files for wind statistics"""
    all_files = []
    for ext in ['*.nc', '*.nc4', '*.grib', '*.grb', '*.grib2']:
        all_files.extend(glob.glob(os.path.join(data_dir, ext)))
    if not all_files:
        return None
    
    all_results = []
    file_count = len(all_files)
    
    for i, file_path in enumerate(all_files):
        if progress_callback:
            progress_callback(i + 1, file_count, os.path.basename(file_path))
        results = extract_wind_from_file(file_path, target_lat, target_lon)
        if results:
            all_results.extend(results)
    
    if not all_results:
        return None
    
    df = pd.DataFrame(all_results)
    try:
        df['datetime'] = pd.to_datetime(df['time'])
        df['hour'] = df['datetime'].dt.hour
        df['year'] = df['datetime'].dt.year
        df['month'] = df['datetime'].dt.month
        df['day'] = df['datetime'].dt.day
    except:
        df['datetime'] = pd.date_range(start='1970-01-01', periods=len(df), freq='H')
        df['hour'] = df['datetime'].dt.hour
        df['year'] = df['datetime'].dt.year
        df['month'] = df['datetime'].dt.month
        df['day'] = df['datetime'].dt.day
    
    wind_avg = calculate_wind_averages(df['speed'].values, df['datetime'])
    df['wind_speed_3min'] = wind_avg['wind_3min']
    df['wind_speed_10min'] = wind_avg['wind_10min']
    df['gust_3sec'] = wind_avg['gust_3sec']
    df['gust_10sec'] = wind_avg['gust_10sec']
    df['wind_speed_hourly'] = df['speed']
    df['wind_direction'] = df['direction']
    
    diurnal_means = df.groupby('hour')['speed'].mean().reindex(range(24), fill_value=0).tolist()
    yearly_max = df.groupby('year')['speed'].max().to_dict()
    yearly_mean = df.groupby('year')['speed'].mean().to_dict()
    global_max_speed = df['speed'].max()
    global_max_year = df.loc[df['speed'].idxmax(), 'year'] if not df.empty else None
    
    return {
        'df': df,
        'all_speeds': df['speed'].values,
        'all_directions': df['direction'].values,
        'all_times': df['datetime'].values,
        'diurnal_means': diurnal_means,
        'yearly_max': yearly_max,
        'yearly_mean': yearly_mean,
        'global_max': {'speed': global_max_speed, 'year': global_max_year},
        'total_records': len(df),
        'years': sorted(df['year'].unique()),
        'files_processed': file_count,
        'files_total': file_count
    }

# ============================================================================
# Demo Data Function
# ============================================================================

def process_demo_data():
    np.random.seed(42)
    dates = pd.date_range(start='1971-01-01', end='2020-12-31 23:00', freq='H')
    all_speeds = np.random.gamma(2, 1.5, len(dates))
    all_directions = np.random.uniform(0, 360, len(dates))
    diurnal_means = [2.0 + 0.8 * np.sin(np.pi * (h - 6) / 12) for h in range(24)]
    
    wind_avg = calculate_wind_averages(all_speeds, dates)
    
    df = pd.DataFrame({
        'datetime': dates,
        'speed': all_speeds,
        'direction': all_directions,
        'wind_speed_3min': wind_avg['wind_3min'],
        'wind_speed_10min': wind_avg['wind_10min'],
        'gust_3sec': wind_avg['gust_3sec'],
        'gust_10sec': wind_avg['gust_10sec'],
        'wind_speed_hourly': all_speeds,
        'wind_direction': all_directions
    })
    yearly_max = df.groupby(df['datetime'].dt.year)['speed'].max().to_dict()
    
    return {
        'df': df,
        'all_speeds': all_speeds,
        'all_directions': all_directions,
        'all_times': dates,
        'diurnal_means': diurnal_means,
        'yearly_max': yearly_max,
        'yearly_mean': {y: np.mean(all_speeds) for y in range(1971, 2021)},
        'global_max': {'speed': 12.5, 'year': 1987},
        'total_records': len(dates),
        'years': list(range(1971, 2021)),
        'is_demo': True
    }

# ============================================================================
# Find Highest Wave Function
# ============================================================================

def find_highest_wave(data, fetch_km, use_debiased, data_source):
    """Find the highest wave in 50 years of data"""
    
    with st.spinner("🔍 Searching through 50 years of data (438,000+ hours)..."):
        df = data['df'].copy()
        wind_speeds = df['speed'].values
        
        if use_debiased and data_source != "Demo" and "Raw" in data_source:
            wind_speeds = wind_speeds * DEBIAS_FACTOR
        
        wave_heights, wave_periods = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
        df['wave_height'] = wave_heights
        df['wave_period'] = wave_periods
        
        max_idx = df['wave_height'].idxmax()
        max_wave = df.loc[max_idx]
        top10 = df.nlargest(10, 'wave_height')[['datetime', 'speed', 'wave_height', 'wave_period', 'direction']].copy()
    
    st.success(f"🏆 **HIGHEST WAVE IN 50 YEARS: {max_wave['wave_height']:.4f} m ({max_wave['wave_height']*100:.2f} cm)**")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📅 Date & Time", max_wave['datetime'].strftime('%Y-%m-%d %H:%M'))
    with col2:
        st.metric("💨 Wind Speed", f"{max_wave['speed']:.2f} m/s")
    with col3:
        st.metric("🌊 Wave Height", f"{max_wave['wave_height']:.3f} m")
    with col4:
        st.metric("⏱️ Wave Period", f"{max_wave['wave_period']:.2f} s")
    
    st.caption(f"🧭 Wind Direction: {max_wave['direction']:.1f}° ({wind_direction_to_cardinal(max_wave['direction'])})")
    
    st.subheader("📊 Wave Distribution at Peak Hour")
    
    wind_speed_max = max_wave['speed']
    wind_direction_max = max_wave['direction']
    
    if use_debiased and data_source != "Demo" and "Raw" in data_source:
        wind_speed_max = wind_speed_max * DEBIAS_FACTOR
    
    wave_heights_grid, wave_periods_grid, _ = generate_swan_wave_distribution(wind_speed_max, wind_direction_max)
    
    col1, col2 = st.columns(2)
    with col1:
        fig_hs = go.Figure(data=go.Heatmap(
            z=wave_heights_grid * 100, 
            x=[f"{i*500}m" for i in range(NX)], 
            y=[f"{i*500}m" for i in range(NY)],
            colorscale='RdYlGn',
            text=np.round(wave_heights_grid * 100, 1),
            texttemplate='<b>%{text} cm</b>',
            textfont={"size": 11},
            colorbar_title="<b>Wave Height (cm)</b>"
        ))
        fig_hs.update_layout(title=f"<b>Wave Height Distribution</b>", xaxis_title="<b>West → East</b>", yaxis_title="<b>North → South</b>", height=400)
        st.plotly_chart(fig_hs, use_container_width=True)
    
    with col2:
        fig_tp = go.Figure(data=go.Heatmap(
            z=wave_periods_grid, 
            x=[f"{i*500}m" for i in range(NX)], 
            y=[f"{i*500}m" for i in range(NY)],
            colorscale='Plasma',
            text=np.round(wave_periods_grid, 1),
            texttemplate='<b>%{text} s</b>',
            textfont={"size": 11},
            colorbar_title="<b>Wave Period (s)</b>"
        ))
        fig_tp.update_layout(title="<b>Wave Period Distribution</b>", xaxis_title="<b>West → East</b>", yaxis_title="<b>North → South</b>", height=400)
        st.plotly_chart(fig_tp, use_container_width=True)
    
    st.subheader("📊 Top 10 Highest Wave Events (1971-2020)")
    top10_display = top10.copy()
    top10_display['datetime'] = top10_display['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    top10_display['wave_height_cm'] = top10_display['wave_height'] * 100
    top10_display = top10_display[['datetime', 'speed', 'wave_height', 'wave_height_cm', 'wave_period', 'direction']]
    top10_display.columns = ['Date & Time', 'Wind Speed (m/s)', 'Wave Height (m)', 'Wave Height (cm)', 'Wave Period (s)', 'Direction (°)']
    st.dataframe(top10_display, use_container_width=True)
    
    csv = top10.to_csv(index=False)
    st.download_button("📥 Download Top 10 Highest Waves (CSV)", csv, "top10_highest_waves.csv", "text/csv")
    
    st.subheader("📈 Annual Maximum Wave Heights (1971-2020)")
    df['year'] = df['datetime'].dt.year
    yearly_max = df.groupby('year')['wave_height'].max().reset_index()
    max_year_row = yearly_max.loc[yearly_max['wave_height'].idxmax()]
    
    fig = go.Figure()
    colors = ['red' if y == max_year_row['year'] else 'steelblue' for y in yearly_max['year']]
    fig.add_trace(go.Bar(x=yearly_max['year'], y=yearly_max['wave_height'], marker_color=colors, 
                         text=yearly_max['wave_height'].round(3), textposition='outside', name='Annual Max Hₛ'))
    fig.add_annotation(x=max_year_row['year'], y=max_year_row['wave_height'], 
                      text=f"🏆 Max: {max_year_row['wave_height']:.3f}m", showarrow=True, 
                      arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="red", ax=0, ay=-40)
    fig.update_layout(title="Annual Maximum Wave Heights", xaxis_title="Year", yaxis_title="Wave Height (m)", height=450)
    st.plotly_chart(fig, use_container_width=True)
    
    return max_wave, top10

# ============================================================================
# Main App
# ============================================================================

def main():
    # Initialize session state
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
        st.session_state.processed = False
    if 'data_source' not in st.session_state:
        st.session_state.data_source = None
    if 'extracted_wind_files' not in st.session_state:
        st.session_state.extracted_wind_files = []
    if 'show_highest_wave' not in st.session_state:
        st.session_state.show_highest_wave = False

    st.title("🌊 Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Kariba")
    st.markdown("**Complete wind, wave, and SWAN wave modeling analysis**")
    st.info("💡 **Key Concept:** Bathymetry is **CONSTANT** (loaded once). Wind files are **VARIABLE** (one per hour from ERA5 debiased data)")

    # ========================================================================
    # LEFT PANEL (Sidebar) - Now visible
    # ========================================================================
    with st.sidebar:
        st.header("📊 Study Area")
        st.markdown("""
        | Parameter | Value |
        |-----------|-------|
        | **Location** | Nyenje Bay |
        | **Coordinates** | 16.53°S, 28.83°E |
        | **Domain** | 4.0 km × 3.5 km |
        | **Grid** | 9 × 8 points |
        | **Resolution** | 500 m |
        """)
        
        st.divider()
        
        st.header("🗺️ Bathymetry (CONSTANT)")
        if REAL_BATHYMETRY is not None:
            st.success("✅ Loaded: nyenje_bathymetry_9x8.bot")
            st.info(f"**Depth range:** {REAL_BATHYMETRY.min():.1f}m - {REAL_BATHYMETRY.max():.1f}m")
            st.caption("Same bathymetry for ALL SWAN runs")
        else:
            st.error("⚠️ Bathymetry file not found!")
            st.caption(f"Expected: {BATHYMETRY_FILE}")
        
        st.divider()
        
        st.header("🌀 Tropical Cyclones")
        st.info("✅ **No tropical cyclone has ever reached Lake Kariba**")
        with st.expander("View recent cyclones that missed Kariba"):
            for tc in TROPICAL_CYCLONES:
                st.write(f"**{tc['name']} ({tc['year']})**")
                st.caption(tc['impact'])
        
        st.divider()
        
        st.header("⚙️ Settings")
        fetch_km = st.slider("Fetch Length (km)", 1, 20, 4)
        use_debiased = st.checkbox("Apply CCMP Debiasing (×0.718)", value=True)
        
        st.divider()
        
        st.header("💨 Wind Averaging Periods")
        st.markdown(f"""
        | Period | Factor | Application |
        |--------|--------|-------------|
        | **10-min mean** | ×{GUST_FACTORS['10min']} | Reference wind speed |
        | **3-min mean** | ×{GUST_FACTORS['3min']} | Dynamic response |
        | **10-sec gust** | ×{GUST_FACTORS['10sec']} | Peak gust (10s) |
        | **3-sec gust** | ×{GUST_FACTORS['3sec']} | Ultimate loads |
        """)
        
        st.divider()
        
        st.header("🔍 Quick Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏆 Find Highest Wave", use_container_width=True):
                st.session_state.show_highest_wave = True
        with col2:
            if st.button("📊 Load Demo Data", use_container_width=True):
                with st.spinner("Loading demo data..."):
                    st.session_state.processed_data = process_demo_data()
                    st.session_state.processed = True
                    st.session_state.data_source = "Demo"
                    st.success("✅ Demo data loaded!")
                    st.rerun()
        
        st.divider()
        
        st.header("📂 Data Status")
        if st.session_state.processed:
            data = st.session_state.processed_data
            st.success(f"✅ Loaded: {data['total_records']:,} records")
            st.info(f"📅 Years: {data['years'][0]} - {data['years'][-1]}")
            st.info(f"📊 Source: {st.session_state.data_source}")
        else:
            st.warning("⚠️ No data loaded - go to Data tab and load data")

    # ========================================================================
    # MAIN TABS
    # ========================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Data Acquisition & Process", "💨 General Wind Statistics", 
        "🌊 Generic Wave Analysis (JONSWAP)", "🌊 SWAN Model"
    ])

    # ========================================================================
    # TAB 1: Data Acquisition & Processing (WITH ALL 5 SUB-TABS)
    # ========================================================================
    with tab1:
        st.header("📥 Data Acquisition & Processing")
        
        # Create 5 main sub-tabs (including PROCESS DATA)
        sub1, sub2, sub3, sub4, sub5 = st.tabs([
            "📡 ERA5 Download", "🔧 Debiasing", "✅ Validation", "⚙️ Process Data", "🌊 SWAN Extraction"
        ])
        
        # ================================================================
        # SUB-TAB 1: ERA5 Download
        # ================================================================
        with sub1:
            st.markdown("### 📡 ERA5 Data Download")
            st.info("Download ERA5 reanalysis data from Copernicus Climate Data Store")
            
            col1, col2 = st.columns(2)
            with col1:
                start_year = st.number_input("Start Year", 1940, 2023, 1990, key="era5_start")
                end_year = st.number_input("End Year", 1940, 2023, 2020, key="era5_end")
            with col2:
                st.markdown("**Region:** Lake Kariba")
                st.markdown("- Latitude: 18°S to 10°S")
                st.markdown("- Longitude: 26°E to 30°E")
            
            st.markdown("""
            **Download Options:**
            - NetCDF format recommended
            - Variables: 10m u-component and v-component of wind (u10, v10)
            - Area: North 10°S, West 26°E, South 18°S, East 30°E
            - Time: Hourly
            
            **After download:**
            1. Place raw files in: `data/era5/raw/`
            2. Go to **Debiasing** tab to apply CCMP correction
            3. Go to **Process Data** tab to load statistics
            4. Go to **SWAN Extraction** tab to create wind files for SWAN
            """)
            
            st.code("""
# Example CDS API query
import cdsapi
c = cdsapi.Client()
c.retrieve(
    'reanalysis-era5-single-levels',
    {
        'product_type': 'reanalysis',
        'variable': ['10m_u_component_of_wind', '10m_v_component_of_wind'],
        'year': ['1990', '1991', '1992'],
        'month': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'],
        'day': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12',
                 '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24',
                 '25', '26', '27', '28', '29', '30', '31'],
        'time': ['00:00', '01:00', '02:00', '03:00', '04:00', '05:00', '06:00', '07:00',
                 '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00',
                 '16:00', '17:00', '18:00', '19:00', '20:00', '21:00', '22:00', '23:00'],
        'area': [10, 26, 18, 30],
        'format': 'netcdf',
    },
    'era5_download.nc')
            """, language="python")
        
        # ================================================================
        # SUB-TAB 2: Debiasing
        # ================================================================
        with sub2:
            st.markdown("### 🔧 Debiasing ERA5 Data with CCMP")
            st.info("Apply CCMP-based debiasing factor (0.718) to ERA5 wind data")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Debiasing Factor:** `{DEBIAS_FACTOR}`")
                st.caption("ERA5 × 0.718 = CCMP-equivalent wind speed")
            with col2:
                st.markdown("**Directories:**")
                st.caption(f"Input (RAW): `{RAW_ERA5_DIR}`")
                st.caption(f"Output (Debiased): `{DEBIASED_ERA5_DIR}`")
            
            st.divider()
            
            st.subheader("📦 Batch Debiasing")
            
            col1, col2 = st.columns(2)
            with col1:
                debias_start_year = st.selectbox("Start Year", list(range(1971, 2021)), index=0, key="debias_start")
                debias_end_year = st.selectbox("End Year", list(range(1971, 2021)), index=49, key="debias_end")
            with col2:
                raw_files = glob.glob(os.path.join(RAW_ERA5_DIR, "*.nc")) + glob.glob(os.path.join(RAW_ERA5_DIR, "*.nc4"))
                st.caption(f"Found {len(raw_files)} NetCDF files in raw directory")
            
            years_to_process = list(range(debias_start_year, debias_end_year + 1))
            
            if st.button("🚀 Apply Debiasing to Selected Years", type="primary", use_container_width=True):
                if not XARRAY_AVAILABLE:
                    st.error("Install: pip install xarray netCDF4")
                else:
                    with st.spinner(f"Debiasing {len(years_to_process)} years..."):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(current, total, filename):
                            progress_bar.progress(current / total)
                            status_text.text(f"Processing: {filename} ({current}/{total})")
                        
                        count, files = batch_debias_era5(RAW_ERA5_DIR, DEBIASED_ERA5_DIR, years_to_process, update_progress)
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        st.success(f"✅ Debiased {count} files")
                        st.info(f"Output saved to: {DEBIASED_ERA5_DIR}")
                        
                        if files:
                            st.subheader("Sample of debiased files:")
                            for f in files[:5]:
                                st.code(f, language="bash")
                        
                        st.balloons()
        
        # ================================================================
        # SUB-TAB 3: Validation
        # ================================================================
        with sub3:
            st.markdown("### ✅ Validation: ERA5 vs CCMP Comparison")
            st.info("Compare raw ERA5, debiased ERA5, and CCMP satellite data")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Data Sources:**")
                st.caption(f"ERA5 Raw: `{RAW_ERA5_DIR}`")
                st.caption(f"ERA5 Debiased: `{DEBIASED_ERA5_DIR}`")
                st.caption(f"CCMP: `{CCMP_DIR}`")
            with col2:
                st.markdown("**Validation Metrics:**")
                st.caption("- Mean wind speed comparison")
                st.caption("- Bias calculation")
                st.caption("- Scatter plots")
            
            st.divider()
            
            era5_files = glob.glob(os.path.join(DEBIASED_ERA5_DIR, "*.nc")) + glob.glob(os.path.join(DEBIASED_ERA5_DIR, "*.nc4"))
            ccmp_files = glob.glob(os.path.join(CCMP_DIR, "*.nc")) + glob.glob(os.path.join(CCMP_DIR, "*.nc4"))
            
            st.subheader("📊 Validation Results")
            
            if st.button("Run Validation", use_container_width=True):
                if not era5_files or not ccmp_files:
                    st.warning(f"Missing files: ERA5 debiased: {len(era5_files)}, CCMP: {len(ccmp_files)}")
                else:
                    with st.spinner("Validating against CCMP data..."):
                        results = []
                        for era5_file in era5_files[:5]:
                            for ccmp_file in ccmp_files[:5]:
                                val = validate_debiased_data(era5_file, ccmp_file)
                                if val:
                                    results.append(val)
                        
                        if results:
                            df_val = pd.DataFrame(results)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("ERA5 Original Mean", f"{df_val['era5_original'].mean():.2f} m/s")
                            with col2:
                                st.metric("ERA5 Debiased Mean", f"{df_val['era5_debiased'].mean():.2f} m/s")
                            with col3:
                                st.metric("CCMP Mean", f"{df_val['ccmp'].mean():.2f} m/s")
                            
                            fig = go.Figure()
                            fig.add_trace(go.Bar(name='Original Bias', x=['Bias'], y=[df_val['bias_original'].mean()], marker_color='red'))
                            fig.add_trace(go.Bar(name='Debiased Bias', x=['Bias'], y=[df_val['bias_debiased'].mean()], marker_color='green'))
                            fig.update_layout(title="Bias Comparison (vs CCMP)", yaxis_title="Bias (m/s)", height=400)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            st.success("✅ Validation complete! Debiased data shows reduced bias against CCMP.")
                            
                            csv = df_val.to_csv(index=False)
                            st.download_button("📥 Download Validation Results", csv, "validation_results.csv", "text/csv")
                        else:
                            st.warning("No validation data could be processed")
        
        # ================================================================
        # SUB-TAB 4: PROCESS DATA (RESTORED)
        # ================================================================
        with sub4:
            st.markdown("### ⚙️ Process ERA5 Data for Wind Statistics")
            st.info("Process raw or debiased ERA5 files to generate wind statistics (wind roses, diurnal patterns, etc.)")
            
            data_dir = st.text_input(
                "Data Directory", 
                value=RAW_ERA5_DIR,
                key="process_data_dir",
                help="Directory containing ERA5 NetCDF files (raw or debiased)"
            )
            
            use_debiased_for_stats = st.checkbox("Use debiased data (×0.718 applied)", value=False, key="use_debiased_stats")
            
            if use_debiased_for_stats:
                data_dir = DEBIASED_ERA5_DIR
                st.info(f"Using debiased data from: {DEBIASED_ERA5_DIR}")
            
            target_lat = st.number_input("Target Latitude", value=-16.53, format="%.4f", key="target_lat_stats")
            target_lon = st.number_input("Target Longitude", value=28.83, format="%.4f", key="target_lon_stats")
            
            if os.path.exists(data_dir):
                nc_files = glob.glob(os.path.join(data_dir, "*.nc")) + glob.glob(os.path.join(data_dir, "*.nc4"))
                grib_files = glob.glob(os.path.join(data_dir, "*.grib")) + glob.glob(os.path.join(data_dir, "*.grb"))
                total_files = len(nc_files) + len(grib_files)
                st.success(f"✅ Found {total_files} files ({len(nc_files)} NetCDF, {len(grib_files)} GRIB)")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Load Demo Data", key="load_demo_process", use_container_width=True):
                    with st.spinner("Loading demo data..."):
                        st.session_state.processed_data = process_demo_data()
                        st.session_state.processed = True
                        st.session_state.data_source = "Demo"
                        st.success("✅ Demo data loaded!")
                        st.balloons()
            
            with col2:
                if st.button("📊 Process Files for Statistics", key="process_stats", use_container_width=True, type="primary"):
                    if not XARRAY_AVAILABLE:
                        st.error("Install: pip install xarray netCDF4 cfgrib")
                    elif not os.path.exists(data_dir):
                        st.error(f"Directory not found: {data_dir}")
                    else:
                        with st.spinner("Processing files..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            def update_progress(current, total, filename):
                                progress_bar.progress(current / total)
                                status_text.text(f"Processing {filename} ({current}/{total})")
                            
                            result = process_all_files(data_dir, target_lat, target_lon, update_progress)
                            progress_bar.empty()
                            status_text.empty()
                            
                            if result and result['total_records'] > 0:
                                st.session_state.processed_data = result
                                st.session_state.processed = True
                                if use_debiased_for_stats:
                                    st.session_state.data_source = "ERA5 (Debiased)"
                                else:
                                    st.session_state.data_source = "ERA5 (Raw)"
                                st.success(f"✅ Processed {result['total_records']:,} records")
                                st.info(f"🏆 Max wind: {result['global_max']['speed']:.2f} m/s ({result['global_max']['year']})")
                                st.balloons()
                            else:
                                st.error("No data could be processed")
            
            # Show statistics summary if data is loaded
            if st.session_state.processed and st.session_state.data_source != "Demo":
                st.divider()
                st.subheader("📊 Current Data Summary")
                data = st.session_state.processed_data
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", f"{data['total_records']:,}")
                with col2:
                    st.metric("Years Range", f"{data['years'][0]} - {data['years'][-1]}")
                with col3:
                    st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
        
        # ================================================================
        # SUB-TAB 5: SWAN Extraction (Single + Batch)
        # ================================================================
        with sub5:
            st.markdown("### 🌊 SWAN Wind File Extraction")
            st.info("Extract wind data for Nyenje Bay 9×8 grid from DEBIASED ERA5 files")
            st.warning("⚠️ **Important:** These files should already be debiased")
            st.caption("Creates ONE wind file per hour for VARIABLE SWAN input")
            
            extraction_mode = st.radio("Select Extraction Mode", ["📄 Single File Extraction", "📦 Batch Extraction (Multiple Years)"], horizontal=True)
            
            if extraction_mode == "📄 Single File Extraction":
                st.subheader("Single File Extraction")
                
                col1, col2 = st.columns(2)
                with col1:
                    single_file = st.text_input("ERA5 File Path", value=os.path.join(DEBIASED_ERA5_DIR, "era5_1990_debiased.nc"))
                    timestamp_str = st.text_input("Timestamp (optional, format: YYYY-MM-DD HH:00)", "")
                with col2:
                    single_output_dir = st.text_input("Output Directory", value=WIND_FILES_DIR)
                
                if st.button("🔍 Extract Single SWAN File", type="primary", use_container_width=True):
                    if not os.path.exists(single_file):
                        st.error(f"File not found: {single_file}")
                    else:
                        with st.spinner("Extracting..."):
                            timestamp = None
                            if timestamp_str:
                                try:
                                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:00")
                                except:
                                    st.warning("Invalid timestamp format, using first timestep")
                            
                            output = extract_single_wind_file(single_file, single_output_dir, timestamp, 1.0)
                            if output:
                                st.success(f"✅ Extracted to: {output}")
                                st.code(output, language="bash")
                            else:
                                st.error("Extraction failed")
            
            else:
                st.subheader("Batch Extraction (Multiple Years)")
                
                col1, col2 = st.columns(2)
                with col1:
                    batch_input_dir = st.text_input("Input Directory (Debiased ERA5)", value=DEBIASED_ERA5_DIR)
                    batch_start_year = st.selectbox("Start Year", list(range(1971, 2021)), index=0, key="batch_start")
                    batch_end_year = st.selectbox("End Year", list(range(1971, 2021)), index=49, key="batch_end")
                with col2:
                    batch_output_dir = st.text_input("Output Directory (SWAN Files)", value=WIND_FILES_DIR)
                    st.caption(f"Output structure: `{batch_output_dir}/YYYY/nyenje_wind_*.wnd`")
                
                years_to_extract = list(range(batch_start_year, batch_end_year + 1))
                st.info(f"Will extract {len(years_to_extract)} years: {years_to_extract[0]} - {years_to_extract[-1]}")
                
                existing = get_existing_wind_files(batch_output_dir)
                st.caption(f"📁 Existing SWAN wind files: {len(existing)} .wnd files")
                
                if st.button("🚀 Batch Extract SWAN Files", type="primary", use_container_width=True):
                    if not XARRAY_AVAILABLE:
                        st.error("Install: pip install xarray netCDF4")
                    elif not SCIPY_AVAILABLE:
                        st.error("Install: pip install scipy")
                    else:
                        total_extracted = 0
                        all_files = []
                        
                        for year in years_to_extract:
                            st.write(f"**Processing year {year}...**")
                            
                            year_files = glob.glob(os.path.join(batch_input_dir, f"*{year}*.nc"))
                            year_files.extend(glob.glob(os.path.join(batch_input_dir, str(year), "*.nc")))
                            
                            if not year_files:
                                st.warning(f"No files found for year {year}")
                                continue
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            def update_progress(current, total, filename):
                                progress_bar.progress(current / total)
                                status_text.text(f"Processing: {filename} ({current}/{total})")
                            
                            count, files = batch_extract_swan_files(batch_input_dir, batch_output_dir, year, 1.0, update_progress)
                            total_extracted += count
                            all_files.extend(files)
                            
                            progress_bar.empty()
                            status_text.empty()
                            st.write(f"  ✅ Extracted {count} files for {year}")
                        
                        st.success(f"✅ BATCH EXTRACTION COMPLETE!")
                        st.metric("Total Wind Files Created", f"{total_extracted}")
                        st.metric("Output Directory", batch_output_dir)
                        
                        if all_files:
                            st.subheader("📄 Sample of created SWAN wind files:")
                            for f in all_files[:5]:
                                st.code(f, language="bash")
                            if len(all_files) > 5:
                                st.caption(f"... and {len(all_files) - 5} more files")
                        
                        st.balloons()
            
            with st.expander("📁 View Output Directory Structure"):
                st.code(f"""
{WIND_FILES_DIR}/
├── 1971/
│   ├── nyenje_wind_19710101_0000.wnd
│   ├── nyenje_wind_19710101_0100.wnd
│   ├── ...
│   └── nyenje_wind_19711231_2300.wnd
├── 1972/
│   └── ...
└── 2020/
    └── ...
                """, language="bash")
    
    # ========================================================================
    # TAB 2: Wind Statistics
    # ========================================================================
    with tab2:
        st.header("💨 General Wind Statistics")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first (Data Acquisition & Process tab → Process Data)")
            st.stop()
        
        data = st.session_state.processed_data
        df = data['df'].copy()
        
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            df['wind_speed_hourly'] = df['speed'] * DEBIAS_FACTOR
            df['gust_3sec'] = df['gust_3sec'] * DEBIAS_FACTOR
            df['gust_10sec'] = df['gust_10sec'] * DEBIAS_FACTOR
            df['wind_speed_3min'] = df['wind_speed_3min'] * DEBIAS_FACTOR
            df['wind_speed_10min'] = df['wind_speed_10min'] * DEBIAS_FACTOR
        
        wind_sub1, wind_sub2, wind_sub3, wind_sub4, wind_sub5 = st.tabs([
            "📊 Wind Rose", "📈 Statistics", "🌅 Diurnal", "⏱️ Wind Averages & Gusts", "🔥 Extremes"
        ])
        
        with wind_sub1:
            if st.button("Generate Wind Rose"):
                fig = create_wind_rose(data['all_speeds'], data['all_directions'], f"Lake Kariba ({st.session_state.data_source})")
                st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub2:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mean Wind Speed", f"{np.mean(data['all_speeds']):.2f} m/s")
                st.metric("Median Wind Speed", f"{np.median(data['all_speeds']):.2f} m/s")
            with col2:
                st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
                st.metric("Year of Max", f"{data['global_max']['year']}")
            with col3:
                mean_dir, _ = calculate_circular_mean(data['all_directions'])
                st.metric("Mean Direction", f"{mean_dir:.1f}°")
                st.metric("Cardinal", wind_direction_to_cardinal(mean_dir))
        
        with wind_sub3:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(range(24)), y=data['diurnal_means'], mode='lines+markers'))
            fig.update_layout(title="Diurnal Wind Pattern", xaxis_title="Hour", yaxis_title="Wind Speed (m/s)", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub4:
            fig = create_wind_parameters_plot(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            stats_df = pd.DataFrame({
                'Parameter': ['Hourly Mean', '3-min Avg', '10-min Avg', '3-sec Gust', '10-sec Gust'],
                'Mean (m/s)': [
                    df['wind_speed_hourly'].mean(),
                    df['wind_speed_3min'].mean(),
                    df['wind_speed_10min'].mean(),
                    df['gust_3sec'].mean(),
                    df['gust_10sec'].mean()
                ],
                'Max (m/s)': [
                    df['wind_speed_hourly'].max(),
                    df['wind_speed_3min'].max(),
                    df['wind_speed_10min'].max(),
                    df['gust_3sec'].max(),
                    df['gust_10sec'].max()
                ]
            })
            st.dataframe(stats_df.round(2), use_container_width=True)
        
        with wind_sub5:
            st.subheader("Extreme Value Analysis")
            if 'yearly_max' in data and data['yearly_max']:
                years = sorted(data['yearly_max'].keys())
                values = [data['yearly_max'][y] for y in years]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=years, y=values, mode='lines+markers'))
                fig.update_layout(title="Annual Maximum Wind Speeds", xaxis_title="Year", yaxis_title="Wind Speed (m/s)", height=400)
                st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 3: Wave Analysis (JONSWAP)
    # ========================================================================
    with tab3:
        st.header("🌊 JONSWAP Generic Wave Parameter Analysis")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        
        data = st.session_state.processed_data
        
        wind_speeds = data['all_speeds'][:5000]
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            wind_speeds = wind_speeds * DEBIAS_FACTOR
        
        st.markdown(f"**Wave parameters using JONSWAP fetch-limited formula (fetch = {fetch_km} km)**")
        
        wave_heights, wave_periods = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Mean Wave Height", f"{np.mean(wave_heights):.3f} m")
        with col2:
            st.metric("Max Wave Height", f"{np.max(wave_heights):.3f} m")
        with col3:
            st.metric("Sig Wave (H₁/₃)", f"{np.percentile(wave_heights, 66.7):.3f} m")
        with col4:
            st.metric("Mean Wave Period", f"{np.mean(wave_periods):.2f} s")
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=wave_heights, nbinsx=30, marker_color='blue', opacity=0.7))
        fig.update_layout(title="Wave Height Distribution", xaxis_title="Wave Height (m)", height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 4: SWAN Model
    # ========================================================================
    with tab4:
        st.header("🌊 SWAN Wave Model Analysis")
        st.info("🔹 **CONSTANT:** Bathymetry (nyenje_bathymetry_9x8.bot)")
        st.info("🔸 **VARIABLE:** Wind files from debiased ERA5 data")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first (Data Acquisition & Process tab → Process Data)")
            st.stop()
        
        data = st.session_state.processed_data
        df = data['df']
        
        swan_sub1, swan_sub2, swan_sub3, swan_sub4, swan_sub5 = st.tabs([
            "🎯 Single Analysis", "📅 Monthly Maxima", "📈 Yearly Maxima", 
            "🏆 Extreme Value Analysis", "🔍 Find Highest Wave"
        ])
        
        # ================================================================
        # SUB-TAB 1: Single Analysis
        # ================================================================
        with swan_sub1:
            st.subheader("🎯 Single Time Step Wave Analysis")
            st.markdown("**CONSTANT Bathymetry** + **VARIABLE Wind** (select date/time below)")
            
            st.subheader("🗺️ **Nyenje Bay Bathymetry** (CONSTANT)")
            if REAL_BATHYMETRY is not None:
                fig_bathy = go.Figure(data=go.Heatmap(
                    z=REAL_BATHYMETRY, 
                    x=[f"{i*500}m" for i in range(NX)], 
                    y=[f"{i*500}m" for i in range(NY)],
                    colorscale='Viridis',
                    text=np.round(REAL_BATHYMETRY, 1),
                    texttemplate='<b>%{text} m</b>',
                    textfont={"size": 12},
                    colorbar_title="<b>Depth (m)</b>"
                ))
                fig_bathy.update_layout(
                    title="<b>Nyenje Bay Bathymetry</b><br><i>REAL Data - CONSTANT for all SWAN runs</i>",
                    xaxis_title="<b>West → East</b>",
                    yaxis_title="<b>North → South</b>",
                    height=450
                )
                st.plotly_chart(fig_bathy, use_container_width=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Minimum Depth", f"{REAL_BATHYMETRY.min():.1f} m")
                with col2:
                    st.metric("Maximum Depth", f"{REAL_BATHYMETRY.max():.1f} m")
                with col3:
                    st.metric("Mean Depth", f"{REAL_BATHYMETRY.mean():.1f} m")
            else:
                st.warning("Bathymetry file not found.")
            
            st.divider()
            
            st.subheader("⏰ Select Time Step (VARIABLE Wind)")
            available_years = sorted([y for y in df['year'].unique() if y is not None])
            
            if available_years:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    selected_year = st.selectbox("Year", available_years, index=len(available_years)-1)
                with col2:
                    selected_month = st.selectbox("Month", range(1, 13), index=0)
                with col3:
                    selected_day = st.selectbox("Day", range(1, 32), index=0)
                with col4:
                    selected_hour = st.selectbox("Hour", range(0, 24), index=0)
                
                if st.button("🌊 Run SWAN Analysis", type="primary"):
                    with st.spinner("Calculating wave distribution..."):
                        target_datetime = datetime(selected_year, selected_month, selected_day, selected_hour, 0, 0)
                        df['time_diff'] = abs(df['datetime'] - target_datetime)
                        closest_idx = df['time_diff'].idxmin()
                        closest_time = df.loc[closest_idx, 'datetime']
                        wind_speed = df.loc[closest_idx, 'speed']
                        wind_direction = df.loc[closest_idx, 'direction']
                        
                        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                            wind_speed = wind_speed * DEBIAS_FACTOR
        
                        st.info(f"Using wind data from: {closest_time}")
                        st.metric("Wind Speed", f"{wind_speed:.2f} m/s")
                        st.metric("Wind Direction", f"{wind_direction:.1f}° ({wind_direction_to_cardinal(wind_direction)})")
                        
                        wave_heights_grid, wave_periods_grid, _ = generate_swan_wave_distribution(wind_speed, wind_direction)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            fig_hs = go.Figure(data=go.Heatmap(
                                z=wave_heights_grid * 100, 
                                x=[f"{i*500}m" for i in range(NX)], 
                                y=[f"{i*500}m" for i in range(NY)],
                                colorscale='RdYlGn',
                                text=np.round(wave_heights_grid * 100, 1),
                                texttemplate='<b>%{text} cm</b>',
                                textfont={"size": 11},
                                colorbar_title="<b>Wave Height (cm)</b>"
                            ))
                            fig_hs.update_layout(
                                title=f"<b>Wave Height Distribution</b><br><i>Wind: {wind_speed:.2f} m/s @ {wind_direction:.0f}°</i>",
                                xaxis_title="<b>West → East</b>",
                                yaxis_title="<b>North → South</b>",
                                height=450
                            )
                            st.plotly_chart(fig_hs, use_container_width=True)
                        
                        with col2:
                            fig_tp = go.Figure(data=go.Heatmap(
                                z=wave_periods_grid, 
                                x=[f"{i*500}m" for i in range(NX)], 
                                y=[f"{i*500}m" for i in range(NY)],
                                colorscale='Plasma',
                                text=np.round(wave_periods_grid, 1),
                                texttemplate='<b>%{text} s</b>',
                                textfont={"size": 11},
                                colorbar_title="<b>Wave Period (s)</b>"
                            ))
                            fig_tp.update_layout(
                                title="<b>Wave Period Distribution</b>",
                                xaxis_title="<b>West → East</b>",
                                yaxis_title="<b>North → South</b>",
                                height=450
                            )
                            st.plotly_chart(fig_tp, use_container_width=True)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Max Wave Height", f"{np.max(wave_heights_grid):.3f} m")
                        with col2:
                            st.metric("Mean Wave Height", f"{np.mean(wave_heights_grid):.3f} m")
                        with col3:
                            st.metric("Max Wave Period", f"{np.max(wave_periods_grid):.2f} s")
                        with col4:
                            st.metric("Mean Wave Period", f"{np.mean(wave_periods_grid):.2f} s")
            else:
                st.warning("No valid years found in data")
        
        # ================================================================
        # SUB-TAB 2: Monthly Maxima
        # ================================================================
        with swan_sub2:
            st.subheader("📅 Monthly Maximum Wave Heights")
            if st.button("Calculate Monthly Maxima", key="calc_monthly"):
                with st.spinner("Calculating monthly maxima..."):
                    df_copy = data['df'].copy()
                    wind_speeds = df_copy['speed'].values
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speeds = wind_speeds * DEBIAS_FACTOR
                    df_copy['wave_height'], _ = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
                    df_copy['year_month'] = df_copy['datetime'].dt.strftime('%Y-%m')
                    monthly_max = df_copy.groupby('year_month')['wave_height'].max().reset_index()
                    df_copy['month'] = df_copy['datetime'].dt.month
                    monthly_stats = df_copy.groupby('month')['wave_height'].agg(['max', 'mean', 'std']).reset_index()
                    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    monthly_stats['month_name'] = monthly_stats['month'].apply(lambda x: month_names[x-1])
                    
                    fig1 = go.Figure()
                    fig1.add_trace(go.Scatter(x=monthly_max['year_month'], y=monthly_max['wave_height'], mode='lines+markers', name='Monthly Max Hₛ'))
                    fig1.update_layout(title="Monthly Maximum Wave Heights Over Time", xaxis_title="Year-Month", yaxis_title="Wave Height (m)", height=500, xaxis_tickangle=45)
                    st.plotly_chart(fig1, use_container_width=True)
                    
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(x=monthly_stats['month_name'], y=monthly_stats['max'], name='Maximum', marker_color='red'))
                    fig2.add_trace(go.Bar(x=monthly_stats['month_name'], y=monthly_stats['mean'], name='Mean', marker_color='blue'))
                    fig2.update_layout(title="Monthly Wave Height Statistics", xaxis_title="Month", yaxis_title="Wave Height (m)", barmode='group', height=400)
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    overall_max = monthly_max.loc[monthly_max['wave_height'].idxmax()]
                    st.success(f"🏆 Overall Monthly Maximum: **{overall_max['wave_height']:.3f} m** in {overall_max['year_month']}")
                    csv = monthly_max.to_csv(index=False)
                    st.download_button("📥 Download Monthly Maxima Data", csv, "monthly_max_waves.csv", "text/csv")
        
        # ================================================================
        # SUB-TAB 3: Yearly Maxima
        # ================================================================
        with swan_sub3:
            st.subheader("📈 Yearly Maximum Wave Heights")
            if st.button("Calculate Yearly Maxima", key="calc_yearly"):
                with st.spinner("Calculating yearly maxima..."):
                    df_copy = data['df'].copy()
                    wind_speeds = df_copy['speed'].values
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speeds = wind_speeds * DEBIAS_FACTOR
                    df_copy['wave_height'], _ = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
                    df_copy['year'] = df_copy['datetime'].dt.year
                    yearly_max = df_copy.groupby('year')['wave_height'].max().reset_index()
                    max_row = yearly_max.loc[yearly_max['wave_height'].idxmax()]
                    
                    fig = go.Figure()
                    colors = ['red' if y == max_row['year'] else 'steelblue' for y in yearly_max['year']]
                    fig.add_trace(go.Bar(x=yearly_max['year'], y=yearly_max['wave_height'], marker_color=colors, text=yearly_max['wave_height'].round(3), textposition='outside', name='Annual Max Hₛ'))
                    fig.add_annotation(x=max_row['year'], y=max_row['wave_height'], text=f"🏆 Max: {max_row['wave_height']:.3f}m", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="red", ax=0, ay=-40)
                    fig.update_layout(title="Yearly Maximum Wave Heights", xaxis_title="Year", yaxis_title="Wave Height (m)", height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Maximum Wave Height", f"{max_row['wave_height']:.3f} m")
                        st.caption(f"Year: {max_row['year']}")
                    with col2:
                        st.metric("Mean Annual Max", f"{yearly_max['wave_height'].mean():.3f} m")
                    with col3:
                        st.metric("95th Percentile", f"{yearly_max['wave_height'].quantile(0.95):.3f} m")
                    csv = yearly_max.to_csv(index=False)
                    st.download_button("📥 Download Yearly Maxima Data", csv, "yearly_max_waves.csv", "text/csv")
        
        # ================================================================
        # SUB-TAB 4: Extreme Value Analysis
        # ================================================================
        with swan_sub4:
            st.subheader("🏆 Extreme Value Analysis (50-100 Year Return Period)")
            if st.button("Run Extreme Value Analysis", key="calc_extreme"):
                with st.spinner("Performing extreme value analysis..."):
                    if not SCIPY_AVAILABLE:
                        st.error("scipy not installed. Run: pip install scipy")
                        st.stop()
                    
                    df_copy = data['df'].copy()
                    wind_speeds = df_copy['speed'].values
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speeds = wind_speeds * DEBIAS_FACTOR
                    df_copy['wave_height'], _ = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
                    df_copy['year'] = df_copy['datetime'].dt.year
                    yearly_max = df_copy.groupby('year')['wave_height'].max().reset_index()
                    heights = yearly_max['wave_height'].values
                    
                    if len(heights) >= 5:
                        params = stats.gumbel_r.fit(heights)
                        return_periods = [2, 5, 10, 20, 25, 50, 100]
                        return_heights = {}
                        for rp in return_periods:
                            prob = 1 - 1/rp
                            return_heights[rp] = stats.gumbel_r.ppf(prob, *params)
                        max_idx = np.argmax(heights)
                        max_event = {'year': int(yearly_max.iloc[max_idx]['year']), 'height': float(heights[max_idx])}
                        
                        return_df = pd.DataFrame([{'Return Period (years)': rp, 'Wave Height (m)': round(h, 3)} for rp, h in return_heights.items()])
                        st.dataframe(return_df, use_container_width=True)
                        
                        fig1 = go.Figure()
                        fig1.add_trace(go.Scatter(x=list(return_heights.keys()), y=list(return_heights.values()), mode='lines+markers', name='Gumbel Fit', line=dict(color='red', width=2), marker=dict(size=10, color='red')))
                        fig1.update_layout(title="Return Period Wave Heights", xaxis_title="Return Period (years)", yaxis_title="Wave Height (m)", xaxis_type="log", height=450)
                        st.plotly_chart(fig1, use_container_width=True)
                        
                        hs_50 = return_heights[50]
                        hs_100 = return_heights[100]
                        st.markdown(f"""
                        | Design Parameter | Value | Application |
                        |-----------------|-------|-------------|
                        | **50-Year Return Period Wave** | **{hs_50:.3f} m** | Ultimate Limit State (ULS) |
                        | **100-Year Return Period Wave** | **{hs_100:.3f} m** | Accidental Limit State (ALS) |
                        | **Historical Maximum** | **{max_event['height']:.3f} m** | Recorded extreme |
                        | **Recommended Design Wave** | **{hs_50 * 1.15:.3f} m** | ULS + 15% safety factor |
                        """)
                        results = {'return_periods': return_heights, 'historical_max': max_event, 'gumbel_params': {'loc': params[0], 'scale': params[1]}}
                        st.download_button("📥 Download Extreme Value Results", json.dumps(results, indent=2), "extreme_value_results.json", "application/json")
                    else:
                        st.warning(f"Insufficient data for extreme value analysis (need at least 5 years, have {len(heights)})")
        
        # ================================================================
        # SUB-TAB 5: Find Highest Wave
        # ================================================================
        with swan_sub5:
            st.subheader("🔍 Find the Highest Wave in 50 Years")
            st.markdown("This tool searches through all 50 years of data to find the exact hour when the highest wave occurred at Nyenje Bay.")
            
            if st.button("🔍 Find Highest Wave Event", type="primary", key="find_highest"):
                find_highest_wave(data, fetch_km, use_debiased, st.session_state.data_source)
    
    # Check for sidebar trigger
    if st.session_state.show_highest_wave and st.session_state.processed:
        st.session_state.show_highest_wave = False
        st.subheader("🏆 Highest Wave Analysis")
        find_highest_wave(st.session_state.processed_data, fetch_km, use_debiased, st.session_state.data_source)

if __name__ == "__main__":
    main()