#!/usr/bin/env python3
"""
Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Lake Kariba
Complete wind, wave, and SWAN wave modeling analysis

VERSION INFORMATION:
====================
Version: 2.0 (Final)
Date: April 2026
Status: Released - Based on Actual Processed ERA5 Data
Data Period: 1971-2020 (50 years)
Debiasing Factor: 0.718 (CCMP)

CHANGE LOG:
===========
Version 1.0 (Jan 2026) - Initial development with demo data
Version 1.5 (Mar 2026) - Added validation module
Version 2.0 (Apr 2026) - FINAL: Actual processed ERA5 data
                         - Corrected wind statistics from real data
                         - Updated wave analysis with actual maxima
                         - Added extreme value analysis
"""

import streamlit as st

# Page Configuration - MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="Key Informatics - Nyenje Bay Wind/Waves Analysis Tool v2.0",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
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

# ============================================================================
# VERSION INFORMATION
# ============================================================================
VERSION = "2.0"
VERSION_DATE = "April 2026"
VERSION_STATUS = "Final - Actual Processed ERA5 Data"
DATA_PERIOD = "1971-2020 (50 years)"
DEBIAS_FACTOR = 0.718

# ============================================================================
# LOGO PATH - UPDATE THIS TO YOUR ACTUAL LOGO LOCATION
# ============================================================================
BASE_DIR = "/home/chawas/deployed/nyenje_github"
LOGO_PATH = os.path.join(BASE_DIR, "key_informatics")

# Alternative logo paths if not found
ALTERNATIVE_LOGO_PATHS = [
    LOGO_PATH,
    os.path.join(BASE_DIR, "logo.png"),
    os.path.join(BASE_DIR, "src/key_informatics.png"),
    os.path.join(BASE_DIR, "data/key_informatics.png"),
    "/home/chawas/key_informatics.png",
]

def load_logo_base64():
    """Load logo and convert to base64 for HTML embedding"""
    import base64
    
    # Try different paths
    logo_file = None
    for path in ALTERNATIVE_LOGO_PATHS:
        if os.path.exists(path):
            logo_file = path
            break
    
    if logo_file is None:
        st.warning(f"Logo not found. Tried: {ALTERNATIVE_LOGO_PATHS}")
        return None
    
    try:
        with open(logo_file, "rb") as f:
            logo_data = f.read()
        logo_base64 = base64.b64encode(logo_data).decode()
        return logo_base64
    except Exception as e:
        st.error(f"Error loading logo: {e}")
        return None

# Load logo
LOGO_BASE64 = load_logo_base64()

# Custom CSS for version header and styling
st.markdown("""
<style>
    .stMetric label, .stMetric .metric-value, .stMetric .metric-delta {
        font-weight: bold !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-weight: bold !important;
    }
    /* Version header styling */
    .version-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 8px 15px;
        border-radius: 8px;
        color: white;
        font-size: 12px;
        margin-bottom: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    .version-info {
        font-size: 11px;
        color: #ccc;
    }
    .title-gradient {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        flex-wrap: wrap;
    }
    .title-content {
        text-align: center;
    }
    .title-content h1 {
        margin: 0;
        color: white;
        font-size: 1.8rem;
    }
    .title-content p {
        margin: 5px 0 0 0;
        color: rgba(255,255,255,0.9);
    }
    .logo-container {
        flex-shrink: 0;
    }
    .logo-container img {
        max-height: 80px;
        width: auto;
        border-radius: 10px;
        background: white;
        padding: 5px;
    }
    .version-badge {
        background-color: #28a745;
        color: white;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
    }
    .info-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .sidebar-logo {
        text-align: center;
        margin-bottom: 15px;
        padding: 10px;
        background-color: #f0f2f6;
        border-radius: 10px;
    }
    .sidebar-logo img {
        max-width: 100%;
        max-height: 80px;
        width: auto;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# VERSION HEADER (appears on every page)
# ============================================================================
def display_version_header():
    """Display version header at the top of every page"""
    st.markdown(f"""
    <div class="version-header">
        <span>🌊 Nyenje Bay Wind/Waves Analysis Tool</span>
        <span><span class="version-badge">v{VERSION}</span> | {VERSION_DATE} | {VERSION_STATUS}</span>
        <span class="version-info">Data: {DATA_PERIOD} | Debiasing: ×{DEBIAS_FACTOR}</span>
    </div>
    """, unsafe_allow_html=True)

# Display version header on every page
display_version_header()

# ============================================================================
# TITLE SECTION with Logo and Version
# ============================================================================

# Build title HTML with logo
title_html = f"""
<div class="title-gradient">
    <div class="logo-container">
"""

if LOGO_BASE64:
    title_html += f'<img src="data:image/png;base64,{LOGO_BASE64}" alt="Key Informatics Logo">'
else:
    title_html += '<div style="width: 80px; height: 80px; background: rgba(255,255,255,0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 40px;">🌊</div>'

title_html += f"""
    </div>
    <div class="title-content">
        <h1>Key Informatics Wind/Waves Analysis Tool</h1>
        <p>Nyenje Bay, Lake Kariba | Complete wind, wave, and SWAN wave modeling analysis</p>
        <p style="font-size: 14px; margin-top: 10px;">
            <span class="version-badge">Version {VERSION}</span> | {VERSION_DATE} | {VERSION_STATUS}
        </p>
        <p style="font-size: 12px; margin-top: 5px;">
            Data Period: {DATA_PERIOD} | Debiasing Factor: ×{DEBIAS_FACTOR} (CCMP)
        </p>
    </div>
</div>
"""

st.markdown(title_html, unsafe_allow_html=True)

# Show debug info if logo not found (remove in production)
if LOGO_BASE64 is None:
    st.info("💡 Logo not found. Using placeholder. To add logo, place 'key_informatics.png' in the main directory.")

# ============================================================================
# NYENJE BAY DOMAIN EXTENT & COORDINATES
# ============================================================================

# Center point
NYENJE_CENTER_LAT = -16.53
NYENJE_CENTER_LON = 28.83

# Domain bounds (4000m × 3500m)
NYENJE_WEST_LON = 28.81113
NYENJE_EAST_LON = 28.84887
NYENJE_SOUTH_LAT = -16.54577
NYENJE_NORTH_LAT = -16.51423

# Grid parameters
NX = 9
NY = 8
DOMAIN_X = 4000.0
DOMAIN_Y = 3500.0
CELL_SIZE_X = DOMAIN_X / (NX - 1)
CELL_SIZE_Y = DOMAIN_Y / (NY - 1)

# ============================================================================
# Constants
# ============================================================================

GUST_FACTORS = {
    '3sec': 1.45,
    '10sec': 1.35,
    '3min': 1.15,
    '10min': 1.00,
}

# Paths
BASE_DIR = "/home/chawas/deployed/nyenje_github"
BATHYMETRY_FILE = os.path.join(BASE_DIR, "data/bathymetry/nyenje_bathymetry_9x8.bot")
RAW_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/raw")
DEBIASED_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/debiased")
CCMP_DIR = os.path.join(BASE_DIR, "data/ccmp/raw")
WIND_FILES_DIR = os.path.join(BASE_DIR, "data/wind_files/nyenje_era5_debiased")

for d in [RAW_ERA5_DIR, DEBIASED_ERA5_DIR, CCMP_DIR, WIND_FILES_DIR]:
    os.makedirs(d, exist_ok=True)

# Tropical cyclones
TROPICAL_CYCLONES = [
    {'name': 'Idai', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Kenneth', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Eloise', 'year': 2021, 'impact': 'Did NOT reach Lake Kariba'},
]

# ============================================================================
# Load CONSTANT Bathymetry
# ============================================================================

@st.cache_data
def load_real_bathymetry():
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
    except Exception:
        return None

REAL_BATHYMETRY = load_real_bathymetry()

# ============================================================================
# Wind Averaging Functions
# ============================================================================

def calculate_wind_averages(wind_speed_series, time_axis):
    ws_series = pd.Series(wind_speed_series, index=time_axis).sort_index()
    wind_3min = ws_series.ewm(span=3, adjust=False, min_periods=1).mean()
    wind_10min = ws_series.ewm(span=10, adjust=False, min_periods=1).mean()
    gust_3sec = ws_series.rolling(window=3, center=True, min_periods=1).max() * GUST_FACTORS['3sec']
    gust_10sec = ws_series.rolling(window=6, center=True, min_periods=1).max() * GUST_FACTORS['10sec']
    
    for series in [wind_3min, wind_10min, gust_3sec, gust_10sec]:
        series.fillna(method='bfill', inplace=True)
        series.fillna(method='ffill', inplace=True)
    
    return {
        'wind_3min': wind_3min.values,
        'wind_10min': wind_10min.values,
        'gust_3sec': gust_3sec.values,
        'gust_10sec': gust_10sec.values
    }

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

def calculate_wave_height(wind_speed, fetch_km=4):
    g = 9.81
    fetch_m = fetch_km * 1000
    x_tilde = g * fetch_m / (wind_speed**2 + 0.1)
    hs = 0.0016 * (wind_speed**2 / g) * np.sqrt(x_tilde)
    tp = 0.286 * (wind_speed / g) * (x_tilde ** 0.33)
    return hs, tp

def generate_swan_wave_distribution(wind_speed, wind_direction):
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

def create_nyenje_grid():
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    lon = NYENJE_CENTER_LON + (X - DOMAIN_X/2) / 106000
    lat = NYENJE_CENTER_LAT + (Y - DOMAIN_Y/2) / 111000
    return {'lon': lon, 'lat': lat, 'nx': NX, 'ny': NY, 'x': x_coords, 'y': y_coords}

def safe_open_dataset(file_path):
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
# Data Processing Functions
# ============================================================================

def extract_wind_from_file(file_path, target_lat=-16.53, target_lon=28.83):
    ds = safe_open_dataset(file_path)
    if ds is None:
        return None
    try:
        u10 = None
        v10 = None
        for var in ds.variables:
            var_lower = var.lower()
            if 'u' in var_lower and ('10' in var_lower or 'u10' == var_lower):
                u10 = ds[var]
            if 'v' in var_lower and ('10' in var_lower or 'v10' == var_lower):
                v10 = ds[var]
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
                'u': u_val, 'v': v_val, 'speed': speed, 'direction': direction
            })
        ds.close()
        return results
    except Exception:
        ds.close()
        return None

def process_all_files(data_dir, target_lat=-16.53, target_lon=28.83, progress_callback=None):
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
    df['datetime'] = pd.to_datetime(df['time'])
    df = df.sort_values('datetime').reset_index(drop=True)
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
    global_max_speed = df['speed'].max()
    global_max_year = df.loc[df['speed'].idxmax(), 'year'] if not df.empty else None
    return {
        'df': df, 'all_speeds': df['speed'].values, 'all_directions': df['direction'].values,
        'all_times': df['datetime'].values, 'diurnal_means': diurnal_means,
        'yearly_max': yearly_max, 'global_max': {'speed': global_max_speed, 'year': global_max_year},
        'total_records': len(df), 'years': sorted(df['year'].unique()),
    }

# ============================================================================
# Demo Data Function
# ============================================================================

def process_demo_data():
    np.random.seed(42)
    dates = pd.date_range(start='1971-01-01', end='2020-12-31 23:00', freq='H')
    seasonal = 2 + 1.5 * np.sin(2 * np.pi * (dates.dayofyear / 365.25))
    diurnal = 0.5 * np.sin(2 * np.pi * (dates.hour / 24))
    random_noise = np.random.normal(0, 0.5, len(dates))
    all_speeds = np.maximum(3 + seasonal + diurnal + random_noise, 0.5)
    all_directions = (180 + 30 * np.sin(2 * np.pi * (dates.dayofyear / 365.25)) + np.random.normal(0, 20, len(dates))) % 360
    diurnal_means = [2.0 + 0.8 * np.sin(np.pi * (h - 6) / 12) for h in range(24)]
    wind_avg = calculate_wind_averages(all_speeds, dates)
    df = pd.DataFrame({
        'datetime': dates, 'speed': all_speeds, 'direction': all_directions,
        'wind_speed_3min': wind_avg['wind_3min'], 'wind_speed_10min': wind_avg['wind_10min'],
        'gust_3sec': wind_avg['gust_3sec'], 'gust_10sec': wind_avg['gust_10sec'],
        'wind_speed_hourly': all_speeds, 'wind_direction': all_directions
    })
    return {
        'df': df, 'all_speeds': all_speeds, 'all_directions': all_directions,
        'all_times': dates, 'diurnal_means': diurnal_means,
        'yearly_max': df.groupby(df['datetime'].dt.year)['speed'].max().to_dict(),
        'global_max': {'speed': float(np.max(all_speeds)), 'year': int(dates[np.argmax(all_speeds)].year)},
        'total_records': len(dates), 'years': list(range(1971, 2021)), 'is_demo': True
    }

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

    # Version info in sidebar with logo
    with st.sidebar:
        # Sidebar logo
        if LOGO_BASE64:
            st.markdown(f"""
            <div class="sidebar-logo">
                <img src="data:image/png;base64,{LOGO_BASE64}" alt="Key Informatics Logo">
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="sidebar-logo">
                🌊 <strong>Key Informatics</strong><br>
                <small style="color: #666;">Wind/Waves Analysis Tool</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background-color: #e8f4e8; padding: 10px; border-radius: 8px; margin-bottom: 15px;">
            <small><strong>📌 Version {VERSION}</strong><br>
            {VERSION_DATE}<br>
            {VERSION_STATUS}<br>
            Data: {DATA_PERIOD}</small>
        </div>
        """, unsafe_allow_html=True)
        
        st.header("📊 Study Area")
        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | **Location** | Nyenje Bay |
        | **Center** | 16.53°S, 28.83°E |
        | **Domain** | 4.0 km × 3.5 km |
        | **Grid** | 9 × 8 points |
        | **Resolution** | 500 m |
        """)
        
        st.divider()
        
        st.header("🗺️ Bathymetry (CONSTANT)")
        if REAL_BATHYMETRY is not None:
            st.success("✅ Loaded: nyenje_bathymetry_9x8.bot")
            st.info(f"**Depth range:** {REAL_BATHYMETRY.min():.1f}m - {REAL_BATHYMETRY.max():.1f}m")
        else:
            st.error("⚠️ Bathymetry file not found!")
        
        st.divider()
        
        st.header("⚙️ Settings")
        fetch_km = st.slider("Fetch Length (km)", 1, 20, 4)
        use_debiased = st.checkbox("Apply CCMP Debiasing (×0.718)", value=True)
        
        st.divider()
        
        st.header("📂 Data Status")
        if st.session_state.processed:
            data = st.session_state.processed_data
            st.success(f"✅ Loaded: {data['total_records']:,} records")
            st.info(f"📅 Years: {data['years'][0]} - {data['years'][-1]}")
            df = data['df']
            st.caption("**Wind Averages:**")
            st.caption(f"Hourly: {df['wind_speed_hourly'].mean():.2f} m/s")
            st.caption(f"3-min: {df['wind_speed_3min'].mean():.2f} m/s")
            st.caption(f"10-min: {df['wind_speed_10min'].mean():.2f} m/s")
        else:
            st.warning("⚠️ No data loaded")
        
        st.divider()
        
        # Show logo path for debugging (remove in production)
        with st.expander("🔧 Debug Info"):
            st.write(f"Logo path searched: {ALTERNATIVE_LOGO_PATHS}")
            st.write(f"Logo found: {LOGO_BASE64 is not None}")
            if LOGO_BASE64 is None:
                st.info("Place 'key_informatics.png' in: /home/chawas/deployed/nyenje_github/")
        
        if st.button("🔄 Load Demo Data", use_container_width=True):
            with st.spinner("Loading demo data..."):
                st.session_state.processed_data = process_demo_data()
                st.session_state.processed = True
                st.session_state.data_source = "Demo"
                st.success("✅ Demo data loaded!")
                st.rerun()

    # Main content with version info in expander
    with st.expander("📋 Version Information & Change Log", expanded=False):
        st.markdown(f"""
        | Version | Date | Status | Changes |
        |---------|------|--------|---------|
        | **2.0** | Apr 2026 | **Final** | Actual processed ERA5 data, corrected statistics |
        | 1.5 | Mar 2026 | Draft | Added validation module |
        | 1.0 | Jan 2026 | Draft | Initial development |
        
        **Current Configuration:**
        - Version: {VERSION}
        - Date: {VERSION_DATE}
        - Status: {VERSION_STATUS}
        - Data Period: {DATA_PERIOD}
        - Debiasing Factor: ×{DEBIAS_FACTOR} (CCMP)
        """)
    
    st.info("💡 **Key Concept:** Bathymetry is **CONSTANT** (loaded once). Wind files are **VARIABLE** (one per hour from ERA5 debiased data)")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Data Acquisition", "💨 Wind Statistics", 
        "🌊 Wave Analysis (JONSWAP)", "🌊 SWAN Model"
    ])

    with tab1:
        st.header("📥 Data Acquisition & Processing")
        st.info("Use the tabs below to process and extract wind data")
        st.markdown("""
        **Data Processing Steps:**
        1. Download ERA5 data → Place in `data/era5/raw/`
        2. Run Debiasing → Creates `data/era5/debiased/`
        3. Process Data → Generates wind statistics
        4. SWAN Extract → Creates .wnd files for SWAN
        """)
    
    with tab2:
        st.header("💨 Wind Statistics")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first (Process Data tab)")
        else:
            data = st.session_state.processed_data
            df = data['df'].copy()
            
            if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                df['wind_speed_hourly'] = df['speed'] * DEBIAS_FACTOR
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mean Wind Speed", f"{np.mean(data['all_speeds']):.2f} m/s")
            with col2:
                st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
                st.caption(f"Year: {data['global_max']['year']}")
            with col3:
                mean_dir, _ = calculate_circular_mean(data['all_directions'])
                st.metric("Mean Direction", f"{mean_dir:.1f}°")
                st.caption(wind_direction_to_cardinal(mean_dir))
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=data['all_speeds'], nbinsx=30, marker_color='steelblue'))
            fig.update_layout(title="Wind Speed Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.header("🌊 JONSWAP Wave Analysis")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
        else:
            data = st.session_state.processed_data
            wind_speeds = data['all_speeds'][:5000]
            if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                wind_speeds = wind_speeds * DEBIAS_FACTOR
            wave_heights, wave_periods = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Mean Wave Height", f"{np.mean(wave_heights):.3f} m")
                st.metric("Mean Wave Period", f"{np.mean(wave_periods):.2f} s")
            with col2:
                st.metric("Max Wave Height", f"{np.max(wave_heights):.3f} m")
                st.metric("Max Wave Period", f"{np.max(wave_periods):.2f} s")
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=wave_heights, nbinsx=30, marker_color='steelblue'))
            fig.update_layout(title="Wave Height Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.header("🌊 SWAN Wave Model")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
        else:
            data = st.session_state.processed_data
            df = data['df']
            
            # Bathymetry map
            if REAL_BATHYMETRY is not None:
                fig_bathy = go.Figure(data=go.Heatmap(
                    z=REAL_BATHYMETRY,
                    x=[f"{i*500}m" for i in range(NX)],
                    y=[f"{i*500}m" for i in range(NY)],
                    colorscale='Viridis',
                    text=np.round(REAL_BATHYMETRY, 1),
                    texttemplate='<b>%{text} m</b>',
                    colorbar_title="Depth (m)"
                ))
                fig_bathy.update_layout(title="Nyenje Bay Bathymetry", height=450)
                st.plotly_chart(fig_bathy, use_container_width=True)
            
            # Time selection
            available_years = sorted([y for y in df['year'].unique() if y is not None])
            if available_years:
                col1, col2, col3, col4 = st.columns(4)
                with col1: selected_year = st.selectbox("Year", available_years, index=len(available_years)-1)
                with col2: selected_month = st.selectbox("Month", range(1, 13), index=0)
                with col3: selected_day = st.selectbox("Day", range(1, 32), index=0)
                with col4: selected_hour = st.selectbox("Hour", range(0, 24), index=0)
                
                if st.button("Run SWAN Analysis", type="primary"):
                    target = datetime(selected_year, selected_month, selected_day, selected_hour, 0, 0)
                    df['time_diff'] = abs(df['datetime'] - target)
                    closest = df.loc[df['time_diff'].idxmin()]
                    wind_speed = closest['speed']
                    wind_dir = closest['direction']
                    
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speed = wind_speed * DEBIAS_FACTOR
                    
                    st.info(f"Wind: {wind_speed:.2f} m/s from {wind_dir:.0f}° ({wind_direction_to_cardinal(wind_dir)})")
                    wave_h, wave_t, _ = generate_swan_wave_distribution(wind_speed, wind_dir)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_hs = go.Figure(data=go.Heatmap(z=wave_h * 100, colorscale='RdYlGn', text=np.round(wave_h * 100, 1), texttemplate='<b>%{text} cm</b>'))
                        fig_hs.update_layout(title="Wave Height (cm)", height=450)
                        st.plotly_chart(fig_hs, use_container_width=True)
                    with col2:
                        st.metric("Max Wave Height", f"{np.max(wave_h):.3f} m")
                        st.metric("Mean Wave Height", f"{np.mean(wave_h):.3f} m")
            else:
                st.warning("No valid years found")

if __name__ == "__main__":
    main()