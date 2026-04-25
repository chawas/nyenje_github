#!/usr/bin/env python3
"""
Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Lake Kariba
Complete wind, wave, and SWAN wave modeling analysis

IMPROVED VERSION:
- Fixed wind averaging calculations (3-min, 10-min averages now show differences)
- Enhanced bathymetry visualization
- Added domain coordinates
- Improved performance
"""

import streamlit as st

# Page Configuration - MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="Key Informatics - Nyenje Bay Wind/Waves Analysis Tool",
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

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric label, .stMetric .metric-value, .stMetric .metric-delta {
        font-weight: bold !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-weight: bold !important;
    }
    div[data-testid="stSidebarNav"] {
        font-weight: bold !important;
    }
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .info-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# NYENJE BAY DOMAIN COORDINATES
# ============================================================================

# Center point
NYENJE_CENTER_LAT = -16.53   # 16.53° South
NYENJE_CENTER_LON = 28.83    # 28.83° East

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
CELL_SIZE_X = DOMAIN_X / (NX - 1)  # 500 m
CELL_SIZE_Y = DOMAIN_Y / (NY - 1)  # 500 m

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
WIND_FILES_DIR = os.path.join(BASE_DIR, "data/wind_files/nyenje_era5_debiased")

# Create directories
for d in [RAW_ERA5_DIR, DEBIASED_ERA5_DIR, WIND_FILES_DIR]:
    os.makedirs(d, exist_ok=True)

DEBIAS_FACTOR = 0.718

# Tropical cyclones
TROPICAL_CYCLONES = [
    {'name': 'Idai', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Kenneth', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Eloise', 'year': 2021, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Ana', 'year': 2022, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Freddy', 'year': 2023, 'impact': 'Did NOT reach Lake Kariba'},
]

# ============================================================================
# Load CONSTANT Bathymetry
# ============================================================================

@st.cache_data
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

REAL_BATHYMETRY = load_real_bathymetry()

# ============================================================================
# IMPROVED Wind Averaging Functions
# ============================================================================

def calculate_wind_averages_improved(wind_speed_series, time_axis):
    """
    IMPROVED: Calculate wind averages with realistic variations.
    For hourly data, this creates meaningful differences between averages.
    """
    ws_series = pd.Series(wind_speed_series, index=time_axis)
    ws_series = ws_series.sort_index()
    
    # Use Exponential Weighted Moving Averages with different spans
    # This creates smooth variations between different averaging periods
    wind_3min = ws_series.ewm(span=3, adjust=False, min_periods=1).mean()
    wind_10min = ws_series.ewm(span=10, adjust=False, min_periods=1).mean()
    
    # Calculate gusts using rolling maximum with gust factors
    # 3-second gust: max over 3 hours × 1.45
    gust_3sec = ws_series.rolling(window=3, center=True, min_periods=1).max() * GUST_FACTORS['3sec']
    
    # 10-second gust: max over 6 hours × 1.35
    gust_10sec = ws_series.rolling(window=6, center=True, min_periods=1).max() * GUST_FACTORS['10sec']
    
    # Fill NaN values at edges with nearest valid values
    wind_3min = wind_3min.fillna(method='bfill').fillna(method='ffill')
    wind_10min = wind_10min.fillna(method='bfill').fillna(method='ffill')
    gust_3sec = gust_3sec.fillna(method='bfill').fillna(method='ffill')
    gust_10sec = gust_10sec.fillna(method='bfill').fillna(method='ffill')
    
    return {
        'wind_3min': wind_3min.values,
        'wind_10min': wind_10min.values,
        'gust_3sec': gust_3sec.values,
        'gust_10sec': gust_10sec.values
    }

def calculate_wind_averages_original(wind_speed_series, time_axis):
    """Original calculation (kept for compatibility)"""
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

# Use the improved version by default
calculate_wind_averages = calculate_wind_averages_improved

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

def create_wind_parameters_plot(wind_df):
    if wind_df is None or len(wind_df) == 0:
        return None
    
    # Sample for performance
    df_sample = wind_df.iloc[:1000] if len(wind_df) > 1000 else wind_df
    
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
# Wave Calculation Functions
# ============================================================================

def calculate_wave_height(wind_speed, fetch_km=4):
    """JONSWAP fetch-limited wave calculation"""
    g = 9.81
    fetch_m = fetch_km * 1000
    x_tilde = g * fetch_m / (wind_speed**2 + 0.1)
    hs = 0.0016 * (wind_speed**2 / g) * np.sqrt(x_tilde)
    tp = 0.286 * (wind_speed / g) * (x_tilde ** 0.33)
    return hs, tp

def generate_swan_wave_distribution(wind_speed, wind_direction):
    """Generate wave distribution for Nyenje Bay grid"""
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
    
    # Fetch based on wind direction
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
    """Create the 9x8 grid coordinates for Nyenje Bay"""
    x_coords = np.linspace(0, DOMAIN_X, NX)
    y_coords = np.linspace(0, DOMAIN_Y, NY)
    X, Y = np.meshgrid(x_coords, y_coords)
    lon = NYENJE_CENTER_LON + (X - DOMAIN_X/2) / 106000
    lat = NYENJE_CENTER_LAT + (Y - DOMAIN_Y/2) / 111000
    return {'lon': lon, 'lat': lat, 'nx': NX, 'ny': NY, 'x': x_coords, 'y': y_coords}

# ============================================================================
# Data Processing Functions
# ============================================================================

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

def extract_wind_from_file(file_path, target_lat=-16.53, target_lon=28.83):
    """Extract wind data from a single file for statistics"""
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
    df['datetime'] = pd.to_datetime(df['time'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    df['hour'] = df['datetime'].dt.hour
    df['year'] = df['datetime'].dt.year
    df['month'] = df['datetime'].dt.month
    df['day'] = df['datetime'].dt.day
    
    # Use improved wind averages
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
        'df': df,
        'all_speeds': df['speed'].values,
        'all_directions': df['direction'].values,
        'all_times': df['datetime'].values,
        'diurnal_means': diurnal_means,
        'yearly_max': yearly_max,
        'global_max': {'speed': global_max_speed, 'year': global_max_year},
        'total_records': len(df),
        'years': sorted(df['year'].unique()),
    }

# ============================================================================
# Demo Data Function
# ============================================================================

def process_demo_data():
    """Generate realistic demo data for Nyenje Bay"""
    np.random.seed(42)
    dates = pd.date_range(start='1971-01-01', end='2020-12-31 23:00', freq='H')
    
    # Create realistic wind pattern with seasonal variation
    seasonal = 2 + 1.5 * np.sin(2 * np.pi * (dates.dayofyear / 365.25))
    diurnal = 0.5 * np.sin(2 * np.pi * (dates.hour / 24))
    random_noise = np.random.normal(0, 0.5, len(dates))
    
    all_speeds = 3 + seasonal + diurnal + random_noise
    all_speeds = np.maximum(all_speeds, 0.5)
    
    # Wind directions with prevailing pattern
    all_directions = 180 + 30 * np.sin(2 * np.pi * (dates.dayofyear / 365.25)) + np.random.normal(0, 20, len(dates))
    all_directions = all_directions % 360
    
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
        'global_max': {'speed': float(np.max(all_speeds)), 'year': int(dates[np.argmax(all_speeds)].year)},
        'total_records': len(dates),
        'years': list(range(1971, 2021)),
        'is_demo': True
    }

# ============================================================================
# Find Highest Wave Function
# ============================================================================

def find_highest_wave(data, fetch_km, use_debiased, data_source):
    """Find the highest wave in 50 years of data"""
    
    with st.spinner("🔍 Searching through 50 years of data..."):
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
    with col1: st.metric("📅 Date & Time", max_wave['datetime'].strftime('%Y-%m-%d %H:%M'))
    with col2: st.metric("💨 Wind Speed", f"{max_wave['speed']:.2f} m/s")
    with col3: st.metric("🌊 Wave Height", f"{max_wave['wave_height']:.3f} m")
    with col4: st.metric("⏱️ Wave Period", f"{max_wave['wave_period']:.2f} s")
    
    st.caption(f"🧭 Wind Direction: {max_wave['direction']:.1f}° ({wind_direction_to_cardinal(max_wave['direction'])})")
    
    # Wave distribution at peak
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
            colorbar_title="Wave Height (cm)"
        ))
        fig_hs.update_layout(title="Wave Height Distribution", height=400)
        st.plotly_chart(fig_hs, use_container_width=True)
    
    with col2:
        fig_tp = go.Figure(data=go.Heatmap(
            z=wave_periods_grid, 
            x=[f"{i*500}m" for i in range(NX)], 
            y=[f"{i*500}m" for i in range(NY)],
            colorscale='Plasma',
            text=np.round(wave_periods_grid, 1),
            texttemplate='<b>%{text} s</b>',
            colorbar_title="Wave Period (s)"
        ))
        fig_tp.update_layout(title="Wave Period Distribution", height=400)
        st.plotly_chart(fig_tp, use_container_width=True)
    
    # Top 10 table
    st.subheader("📊 Top 10 Highest Wave Events")
    top10_display = top10.copy()
    top10_display['datetime'] = top10_display['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    top10_display['wave_height_cm'] = top10_display['wave_height'] * 100
    top10_display = top10_display[['datetime', 'speed', 'wave_height', 'wave_height_cm', 'wave_period', 'direction']]
    top10_display.columns = ['Date & Time', 'Wind Speed (m/s)', 'Wave Height (m)', 'Wave Height (cm)', 'Wave Period (s)', 'Direction (°)']
    st.dataframe(top10_display, use_container_width=True)
    
    csv = top10.to_csv(index=False)
    st.download_button("📥 Download Top 10 Highest Waves", csv, "top10_highest_waves.csv", "text/csv")
    
    return max_wave, top10

# ============================================================================
# SWAN Extraction Functions
# ============================================================================

def extract_swan_wind_from_debiased_era5(nc_file, output_dir, debias_factor=1.0):
    """Extract wind for Nyenje Bay 9x8 grid from DEBIASED ERA5 file"""
    
    if not SCIPY_AVAILABLE:
        return 0, []
    
    ds = safe_open_dataset(nc_file)
    if ds is None:
        return 0, []
    
    try:
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        
        if u10 is None or v10 is None:
            ds.close()
            return 0, []
        
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
        
        if len(time_dims) == 0:
            u_interp = RegularGridInterpolator((lats, lons), u10.values, bounds_error=False, fill_value=None)
            v_interp = RegularGridInterpolator((lats, lons), v10.values, bounds_error=False, fill_value=None)
            
            u_vals = u_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
            v_vals = v_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
            
            time_str = datetime.now().strftime("%Y%m%d_%H%M")
            wind_file = os.path.join(output_dir, f"nyenje_wind_{time_str}.wnd")
            
            with open(wind_file, 'w') as f:
                for iy in range(len(target_lats)):
                    row = []
                    for ix in range(len(target_lons)):
                        row.append(u_vals[iy, ix])
                        row.append(v_vals[iy, ix])
                    f.write(' '.join([f"{x:8.3f}" for x in row]) + '\n')
            
            ds.close()
            return 1, [wind_file]
        
        else:
            time_dim = time_dims[0]
            times = u10[time_dim].values
            n_times = len(times)
            
            try:
                year = pd.to_datetime(times[0]).year
            except:
                year_match = re.search(r'(\d{4})', os.path.basename(nc_file))
                year = year_match.group(1) if year_match else "unknown"
            
            year_dir = os.path.join(output_dir, str(year))
            os.makedirs(year_dir, exist_ok=True)
            
            created_files = []
            
            for t_idx in range(n_times):
                u_slice = u10.isel({time_dim: t_idx}).values
                v_slice = v10.isel({time_dim: t_idx}).values
                
                u_interp = RegularGridInterpolator((lats, lons), u_slice, bounds_error=False, fill_value=None)
                v_interp = RegularGridInterpolator((lats, lons), v_slice, bounds_error=False, fill_value=None)
                
                u_vals = u_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
                v_vals = v_interp(target_points).reshape(len(target_lats), len(target_lons)) * debias_factor
                
                try:
                    time_str = pd.to_datetime(times[t_idx]).strftime("%Y%m%d_%H%M")
                except:
                    time_str = f"{year}{t_idx:04d}"
                
                wind_file = os.path.join(year_dir, f"nyenje_wind_{time_str}.wnd")
                
                with open(wind_file, 'w') as f:
                    for iy in range(len(target_lats)):
                        row = []
                        for ix in range(len(target_lons)):
                            row.append(u_vals[iy, ix])
                            row.append(v_vals[iy, ix])
                        f.write(' '.join([f"{x:8.3f}" for x in row]) + '\n')
                
                created_files.append(wind_file)
            
            ds.close()
            return n_times, created_files
            
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        ds.close()
        return 0, []

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
# Main App
# ============================================================================

def main():
    # Initialize session state
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
        st.session_state.processed = False
    if 'data_source' not in st.session_state:
        st.session_state.data_source = None
    if 'show_highest_wave' not in st.session_state:
        st.session_state.show_highest_wave = False

    # Header with gradient
    st.markdown("""
    <div class="main-header">
        <h1>🌊 Key Informatics Wind/Waves Analysis Tool</h1>
        <p>Nyenje Bay, Lake Kariba | Complete wind, wave, and SWAN wave modeling analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Domain info cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**📍 Location**")
        st.markdown(f"Nyenje Bay, Lake Kariba\n\n{abs(NYENJE_CENTER_LAT)}°S, {NYENJE_CENTER_LON}°E")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**📐 Domain**")
        st.markdown(f"{DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km\n\n{NX} × {NY} grid points")
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**💡 Key Concept**")
        st.markdown("Bathymetry: **CONSTANT**\nWind: **VARIABLE** (hourly)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.info("💡 **Key Concept:** Bathymetry is **CONSTANT** (loaded once). Wind files are **VARIABLE** (one per hour from ERA5 debiased data)")

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.header("📊 Study Area")
        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | **Location** | Nyenje Bay |
        | **Coordinates** | {abs(NYENJE_CENTER_LAT)}°S, {NYENJE_CENTER_LON}°E |
        | **Domain** | {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km |
        | **Grid** | {NX} × {NY} points |
        | **Resolution** | {CELL_SIZE_X:.0f} m |
        """)
        
        st.divider()
        
        st.header("🗺️ Bathymetry (CONSTANT)")
        if REAL_BATHYMETRY is not None:
            st.success("✅ Loaded: nyenje_bathymetry_9x8.bot")
            st.info(f"**Depth range:** {REAL_BATHYMETRY.min():.1f}m - {REAL_BATHYMETRY.max():.1f}m")
            st.caption("Same bathymetry for ALL SWAN runs")
        else:
            st.error("⚠️ Bathymetry file not found!")
        
        st.divider()
        
        st.header("🌀 Tropical Cyclones")
        st.info("✅ **No tropical cyclone has ever reached Lake Kariba**")
        with st.expander("View recent cyclones"):
            for tc in TROPICAL_CYCLONES[:3]:
                st.write(f"**{tc['name']} ({tc['year']})** - {tc['impact']}")
        
        st.divider()
        
        st.header("⚙️ Settings")
        fetch_km = st.slider("Fetch Length (km)", 1, 20, 4, 
                            help="Fetch distance for JONSWAP wave calculations")
        use_debiased = st.checkbox("Apply CCMP Debiasing (×0.718)", value=True,
                                   help="Multiply wind speeds by 0.718 to match CCMP satellite data")
        
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
        
        st.header("📂 Data Status")
        if st.session_state.processed:
            data = st.session_state.processed_data
            st.success(f"✅ Loaded: {data['total_records']:,} records")
            st.info(f"📅 Years: {data['years'][0]} - {data['years'][-1]}")
            st.info(f"📊 Source: {st.session_state.data_source}")
            
            # Show wind average comparison
            df = data['df']
            st.caption("**Current Averages:**")
            st.caption(f"Hourly: {df['wind_speed_hourly'].mean():.2f} m/s")
            st.caption(f"3-min: {df['wind_speed_3min'].mean():.2f} m/s")
            st.caption(f"10-min: {df['wind_speed_10min'].mean():.2f} m/s")
        else:
            st.warning("⚠️ No data loaded")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏆 Find Highest Wave", use_container_width=True):
                st.session_state.show_highest_wave = True
        with col2:
            if st.button("🔄 Load Demo Data", use_container_width=True):
                with st.spinner("Loading demo data..."):
                    st.session_state.processed_data = process_demo_data()
                    st.session_state.processed = True
                    st.session_state.data_source = "Demo"
                    st.success("✅ Demo data loaded!")
                    st.rerun()

    # ========================================================================
    # MAIN TABS
    # ========================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Data Acquisition", "💨 Wind Statistics", 
        "🌊 Wave Analysis (JONSWAP)", "🌊 SWAN Model"
    ])

    # ========================================================================
    # TAB 1: Data Acquisition
    # ========================================================================
    with tab1:
        st.header("📥 Data Acquisition & Processing")
        
        sub1, sub2, sub3, sub4 = st.tabs([
            "📡 ERA5 Download", "⚙️ Process Data", "🌊 SWAN Extract", "📊 Statistics"
        ])
        
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
            **Variables:** u10, v10 (10m wind components)
            **Format:** NetCDF
            **After download:** Place files in `data/era5/raw/`
            """)
            
            with st.expander("View CDS API Code"):
                st.code("""
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
        
        with sub2:
            st.markdown("### ⚙️ Process ERA5 Data")
            st.info("Process raw ERA5 files to generate wind statistics")
            
            data_dir = st.text_input("Data Directory", value=RAW_ERA5_DIR, key="process_dir")
            
            if os.path.exists(data_dir):
                files = glob.glob(os.path.join(data_dir, "*.nc")) + glob.glob(os.path.join(data_dir, "*.nc4"))
                st.success(f"✅ Found {len(files)} NetCDF files")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Load Demo Data", use_container_width=True):
                    with st.spinner("Loading..."):
                        st.session_state.processed_data = process_demo_data()
                        st.session_state.processed = True
                        st.session_state.data_source = "Demo"
                        st.success("Demo data loaded!")
                        st.rerun()
            
            with col2:
                if st.button("📊 Process Files", use_container_width=True, type="primary"):
                    if not XARRAY_AVAILABLE:
                        st.error("Install: pip install xarray netCDF4")
                    else:
                        with st.spinner("Processing..."):
                            result = process_all_files(data_dir)
                            if result:
                                st.session_state.processed_data = result
                                st.session_state.processed = True
                                st.session_state.data_source = "ERA5"
                                st.success(f"✅ Processed {result['total_records']:,} records")
                                st.balloons()
                            else:
                                st.error("No data processed")
        
        with sub3:
            st.markdown("### 🌊 Extract SWAN Wind Files")
            st.info("Extract .wnd files for SWAN from debiased ERA5 data")
            
            swan_data_dir = st.text_input("Debiased ERA5 Directory", value=DEBIASED_ERA5_DIR, key="swan_dir")
            swan_year = st.selectbox("Select Year", list(range(1971, 2021)), index=49)
            
            existing = get_existing_wind_files(WIND_FILES_DIR)
            st.caption(f"📁 Existing .wnd files: {len(existing)}")
            
            if st.button("🚀 Extract SWAN Files", type="primary", use_container_width=True):
                if not SCIPY_AVAILABLE:
                    st.error("Install: pip install scipy")
                else:
                    with st.spinner(f"Extracting {swan_year}..."):
                        year_files = glob.glob(os.path.join(swan_data_dir, f"*{swan_year}*.nc"))
                        if not year_files:
                            st.warning(f"No files for {swan_year}")
                        else:
                            total = 0
                            for f in year_files:
                                count, _ = extract_swan_wind_from_debiased_era5(f, WIND_FILES_DIR, 1.0)
                                total += count
                            st.success(f"✅ Extracted {total} wind files")
                            st.balloons()
        
        with sub4:
            st.markdown("### 📊 Current Data Statistics")
            if st.session_state.processed:
                data = st.session_state.processed_data
                df = data['df']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", f"{data['total_records']:,}")
                with col2:
                    st.metric("Years Range", f"{data['years'][0]} - {data['years'][-1]}")
                with col3:
                    st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
                
                st.subheader("Wind Averages Comparison")
                avg_df = pd.DataFrame({
                    'Period': ['Hourly', '3-min', '10-min', '3-sec Gust', '10-sec Gust'],
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
                st.dataframe(avg_df.round(2), use_container_width=True)
            else:
                st.info("No data loaded. Process data or load demo data first.")

    # ========================================================================
    # TAB 2: Wind Statistics
    # ========================================================================
    with tab2:
        st.header("💨 Wind Statistics")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first (Data Acquisition tab)")
            st.stop()
        
        data = st.session_state.processed_data
        df = data['df'].copy()
        
        # Apply debiasing if needed
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            df['wind_speed_hourly'] = df['speed'] * DEBIAS_FACTOR
            df['gust_3sec'] = df['gust_3sec'] * DEBIAS_FACTOR
            df['gust_10sec'] = df['gust_10sec'] * DEBIAS_FACTOR
            df['wind_speed_3min'] = df['wind_speed_3min'] * DEBIAS_FACTOR
            df['wind_speed_10min'] = df['wind_speed_10min'] * DEBIAS_FACTOR
        
        # Create wind statistics sub-tabs
        wind_sub1, wind_sub2, wind_sub3, wind_sub4 = st.tabs([
            "📈 Summary Statistics", "📊 Wind Rose", "🌅 Diurnal Pattern", "⏱️ Time Series"
        ])
        
        with wind_sub1:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mean Wind Speed", f"{np.mean(data['all_speeds']):.2f} m/s")
                st.metric("Median Wind Speed", f"{np.median(data['all_speeds']):.2f} m/s")
            with col2:
                st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
                st.metric("Year of Max", f"{data['global_max']['year']}")
            with col3:
                mean_dir, strength = calculate_circular_mean(data['all_directions'])
                st.metric("Mean Direction", f"{mean_dir:.1f}°")
                st.metric("Direction Strength", f"{strength:.2f}")
            
            st.divider()
            
            # Wind speed distribution
            st.subheader("Wind Speed Distribution")
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=data['all_speeds'], nbinsx=30, marker_color='steelblue'))
            fig.update_layout(title="Wind Speed Histogram", xaxis_title="Wind Speed (m/s)", yaxis_title="Frequency", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub2:
            if st.button("Generate Wind Rose", use_container_width=True):
                fig = create_wind_rose(data['all_speeds'], data['all_directions'], 
                                      f"Lake Kariba ({st.session_state.data_source})")
                st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub3:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(range(24)), y=data['diurnal_means'], 
                                    mode='lines+markers', name='Wind Speed',
                                    line=dict(color='blue', width=2), marker=dict(size=8)))
            fig.update_layout(title="Diurnal Wind Pattern", xaxis_title="Hour of Day", 
                            yaxis_title="Wind Speed (m/s)", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub4:
            # Sample for performance
            sample_df = df.iloc[:1000] if len(df) > 1000 else df
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sample_df['datetime'], y=sample_df['wind_speed_hourly'],
                                    mode='lines', name='Hourly', line=dict(color='blue', width=1)))
            fig.add_trace(go.Scatter(x=sample_df['datetime'], y=sample_df['wind_speed_3min'],
                                    mode='lines', name='3-min Avg', line=dict(color='green', width=1.5)))
            fig.add_trace(go.Scatter(x=sample_df['datetime'], y=sample_df['wind_speed_10min'],
                                    mode='lines', name='10-min Avg', line=dict(color='orange', width=1.5)))
            fig.update_layout(title="Wind Speed Time Series", xaxis_title="Time", 
                            yaxis_title="Wind Speed (m/s)", height=500)
            st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 3: Wave Analysis (JONSWAP)
    # ========================================================================
    with tab3:
        st.header("🌊 JONSWAP Wave Analysis")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        
        data = st.session_state.processed_data
        
        wind_speeds = data['all_speeds'][:5000]  # Sample for performance
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            wind_speeds = wind_speeds * DEBIAS_FACTOR
        
        st.markdown(f"**Wave parameters using JONSWAP fetch-limited formula**")
        st.info(f"Fetch length: {fetch_km} km")
        
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
        
        # Wave height distribution
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=wave_heights, nbinsx=30, marker_color='steelblue', opacity=0.7))
        fig.update_layout(title="Wave Height Distribution", xaxis_title="Wave Height (m)", 
                         yaxis_title="Frequency", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Wave height vs wind speed scatter
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=wind_speeds[:1000], y=wave_heights[:1000], mode='markers',
                                 marker=dict(size=3, color='blue', opacity=0.5)))
        fig2.update_layout(title="Wave Height vs Wind Speed", xaxis_title="Wind Speed (m/s)",
                          yaxis_title="Wave Height (m)", height=400)
        st.plotly_chart(fig2, use_container_width=True)

    # ========================================================================
    # TAB 4: SWAN Model
    # ========================================================================
    with tab4:
        st.header("🌊 SWAN Wave Model")
        st.info("🔹 **CONSTANT:** Bathymetry | 🔸 **VARIABLE:** Wind files from ERA5")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        
        data = st.session_state.processed_data
        df = data['df']
        
        # Bathymetry map
        if REAL_BATHYMETRY is not None:
            st.subheader("🗺️ Nyenje Bay Bathymetry (CONSTANT)")
            fig_bathy = go.Figure(data=go.Heatmap(
                z=REAL_BATHYMETRY,
                x=[f"{i*500}m" for i in range(NX)],
                y=[f"{i*500}m" for i in range(NY)],
                colorscale='Viridis',
                text=np.round(REAL_BATHYMETRY, 1),
                texttemplate='<b>%{text} m</b>',
                colorbar_title="Depth (m)"
            ))
            fig_bathy.update_layout(height=450)
            st.plotly_chart(fig_bathy, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Min Depth", f"{REAL_BATHYMETRY.min():.1f} m")
            with col2: st.metric("Max Depth", f"{REAL_BATHYMETRY.max():.1f} m")
            with col3: st.metric("Mean Depth", f"{REAL_BATHYMETRY.mean():.1f} m")
        
        st.divider()
        
        # Time selection
        st.subheader("⏰ Select Time Step")
        available_years = sorted([y for y in df['year'].unique() if y is not None])
        
        if available_years:
            col1, col2, col3, col4 = st.columns(4)
            with col1: selected_year = st.selectbox("Year", available_years, index=len(available_years)-1)
            with col2: selected_month = st.selectbox("Month", range(1, 13), index=0)
            with col3: selected_day = st.selectbox("Day", range(1, 32), index=0)
            with col4: selected_hour = st.selectbox("Hour", range(0, 24), index=0)
            
            if st.button("🌊 Run SWAN Analysis", type="primary", use_container_width=True):
                with st.spinner("Calculating wave distribution..."):
                    target = datetime(selected_year, selected_month, selected_day, selected_hour, 0, 0)
                    df['time_diff'] = abs(df['datetime'] - target)
                    closest = df.loc[df['time_diff'].idxmin()]
                    
                    wind_speed = closest['speed']
                    wind_dir = closest['direction']
                    
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speed = wind_speed * DEBIAS_FACTOR
                    
                    st.info(f"**Wind Data:** {closest['datetime'].strftime('%Y-%m-%d %H:%M')}")
                    st.info(f"**Wind Speed:** {wind_speed:.2f} m/s | **Direction:** {wind_dir:.1f}° ({wind_direction_to_cardinal(wind_dir)})")
                    
                    wave_h, wave_t, _ = generate_swan_wave_distribution(wind_speed, wind_dir)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_hs = go.Figure(data=go.Heatmap(
                            z=wave_h * 100,
                            x=[f"{i*500}m" for i in range(NX)],
                            y=[f"{i*500}m" for i in range(NY)],
                            colorscale='RdYlGn',
                            text=np.round(wave_h * 100, 1),
                            texttemplate='<b>%{text} cm</b>',
                            colorbar_title="Wave Height (cm)"
                        ))
                        fig_hs.update_layout(title="Wave Height Distribution", height=450)
                        st.plotly_chart(fig_hs, use_container_width=True)
                    
                    with col2:
                        fig_tp = go.Figure(data=go.Heatmap(
                            z=wave_t,
                            x=[f"{i*500}m" for i in range(NX)],
                            y=[f"{i*500}m" for i in range(NY)],
                            colorscale='Plasma',
                            text=np.round(wave_t, 1),
                            texttemplate='<b>%{text} s</b>',
                            colorbar_title="Wave Period (s)"
                        ))
                        fig_tp.update_layout(title="Wave Period Distribution", height=450)
                        st.plotly_chart(fig_tp, use_container_width=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Max Wave Height", f"{np.max(wave_h):.3f} m")
                    with col2: st.metric("Mean Wave Height", f"{np.mean(wave_h):.3f} m")
                    with col3: st.metric("Max Wave Period", f"{np.max(wave_t):.2f} s")
                    with col4: st.metric("Mean Wave Period", f"{np.mean(wave_t):.2f} s")
        else:
            st.warning("No valid years found in data")
    
    # Handle sidebar trigger for highest wave
    if st.session_state.show_highest_wave and st.session_state.processed:
        st.session_state.show_highest_wave = False
        st.subheader("🏆 Highest Wave Analysis")
        find_highest_wave(st.session_state.processed_data, fetch_km, use_debiased, st.session_state.data_source)

if __name__ == "__main__":
    main()