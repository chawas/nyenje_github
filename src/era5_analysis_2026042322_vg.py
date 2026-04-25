#!/usr/bin/env python3
"""
Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Lake Kariba
Complete wind, wave, and SWAN wave modeling analysis
"""

import streamlit as st

# Page Configuration - MUST BE FIRST Streamlit command
st.set_page_config(
    page_title="Key Informatics - Nyenje Bay Wind/Waves Analysis Tool",
    #page_icon="🌊",
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
    /* Ensure sidebar is visible */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
        min-width: 320px;
        display: block !important;
        visibility: visible !important;
    }
    [data-testid="stSidebarNav"] {
        font-weight: bold !important;
    }
    .title-gradient {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .domain-card {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .info-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .explanation-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #1e3c72;
    }
</style>
""", unsafe_allow_html=True)

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

# Conversion factors
METERS_PER_DEGREE_LAT = 111000.0
METERS_PER_DEGREE_LON = 106000.0

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
VALIDATION_DIR = os.path.join(BASE_DIR, "data/validation")
WIND_FILES_DIR = os.path.join(BASE_DIR, "data/wind_files/nyenje_era5_debiased")
SWAN_OUTPUTS_DIR = os.path.join(BASE_DIR, "swan/outputs")
SWAN_INPUTS_ARCHIVE = os.path.join(BASE_DIR, "swan/inputs_archive")

for d in [RAW_ERA5_DIR, DEBIASED_ERA5_DIR, CCMP_DIR, VALIDATION_DIR, WIND_FILES_DIR, SWAN_OUTPUTS_DIR, SWAN_INPUTS_ARCHIVE]:
    os.makedirs(d, exist_ok=True)

DEBIAS_FACTOR = 0.718

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

def create_wind_parameters_plot(wind_df):
    if wind_df is None or len(wind_df) == 0:
        return None
    df_sample = wind_df.iloc[:1000] if len(wind_df) > 1000 else wind_df
    fig = make_subplots(rows=3, cols=2,
        subplot_titles=('Wind Speed (Hourly)', '3-Minute Average',
                        '10-Minute Average', '3-Second Gust',
                        '10-Second Gust', 'Wind Direction'),
        vertical_spacing=0.12)
    
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_hourly'], mode='lines', name='Hourly', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_3min'], mode='lines', name='3-min', line=dict(color='green', width=1.5)), row=1, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_10min'], mode='lines', name='10-min', line=dict(color='orange', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_3sec'], mode='lines', name='3s Gust', line=dict(color='red', width=1.5)), row=2, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_10sec'], mode='lines', name='10s Gust', line=dict(color='purple', width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_direction'], mode='lines', name='Direction', line=dict(color='brown', width=1)), row=3, col=2)
    
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
    lon = NYENJE_CENTER_LON + (X - DOMAIN_X/2) / METERS_PER_DEGREE_LON
    lat = NYENJE_CENTER_LAT + (Y - DOMAIN_Y/2) / METERS_PER_DEGREE_LAT
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
# DEBIASING FUNCTIONS
# ============================================================================

def debias_era5_file(input_file, output_dir, debias_factor=DEBIAS_FACTOR):
    ds = safe_open_dataset(input_file)
    if ds is None:
        return False, None
    try:
        u10 = ds.get('u10', ds.get('u10n', None))
        v10 = ds.get('v10', ds.get('v10n', None))
        if u10 is None or v10 is None:
            ds.close()
            return False, None
        u10_debiased = u10 * debias_factor
        v10_debiased = v10 * debias_factor
        basename = os.path.basename(input_file)
        name, ext = os.path.splitext(basename)
        output_file = os.path.join(output_dir, f"{name}_debiased{ext}")
        ds_debiased = xr.Dataset({'u10': u10_debiased, 'v10': v10_debiased})
        if 'longitude' in ds.coords:
            ds_debiased = ds_debiased.assign_coords({'longitude': ds.longitude, 'latitude': ds.latitude, 'time': ds.time})
        else:
            ds_debiased = ds_debiased.assign_coords({'lon': ds.lon, 'lat': ds.lat, 'time': ds.time})
        ds_debiased.to_netcdf(output_file)
        ds.close()
        return True, output_file
    except Exception as e:
        ds.close()
        return False, None

def batch_debias_era5(input_dir, output_dir, years=None, progress_callback=None):
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

def validate_debiased_data(era5_file, ccmp_file):
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
        target_lat, target_lon = NYENJE_CENTER_LAT, NYENJE_CENTER_LON
        lat_coord = 'latitude' if 'latitude' in ds_era5.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in ds_era5.coords else 'lon'
        u_era5_point = u_era5.sel({lat_coord: target_lat, lon_coord: target_lon}, method='nearest')
        v_era5_point = v_era5.sel({lat_coord: target_lat, lon_coord: target_lon}, method='nearest')
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
    except Exception:
        ds_era5.close()
        ds_ccmp.close()
        return None

# ============================================================================
# Data Processing Functions (WITH PROGRESS BAR)
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
# SWAN Extraction Functions
# ============================================================================

def extract_swan_wind_from_debiased_era5(nc_file, output_dir, debias_factor=1.0):
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
    wind_files = []
    if os.path.exists(wind_dir):
        for root, dirs, files in os.walk(wind_dir):
            for file in files:
                if file.endswith('.wnd'):
                    wind_files.append(os.path.join(root, file))
    return wind_files

# ============================================================================
# SWAN Model Analysis Functions
# ============================================================================

def calculate_monthly_maxima(df, fetch_km, use_debiased, data_source):
    df_copy = df.copy()
    wind_speeds = df_copy['speed'].values
    if use_debiased and data_source != "Demo" and "Raw" in data_source:
        wind_speeds = wind_speeds * DEBIAS_FACTOR
    df_copy['wave_height'], _ = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
    df_copy['year_month'] = df_copy['datetime'].dt.strftime('%Y-%m')
    monthly_max = df_copy.groupby('year_month')['wave_height'].max().reset_index()
    df_copy['month'] = df_copy['datetime'].dt.month
    monthly_stats = df_copy.groupby('month')['wave_height'].agg(['max', 'mean', 'std']).reset_index()
    return monthly_max, monthly_stats

def calculate_yearly_maxima(df, fetch_km, use_debiased, data_source):
    df_copy = df.copy()
    wind_speeds = df_copy['speed'].values
    if use_debiased and data_source != "Demo" and "Raw" in data_source:
        wind_speeds = wind_speeds * DEBIAS_FACTOR
    df_copy['wave_height'], _ = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
    df_copy['year'] = df_copy['datetime'].dt.year
    yearly_max = df_copy.groupby('year')['wave_height'].max().reset_index()
    return yearly_max

def extreme_value_analysis(df, fetch_km, use_debiased, data_source):
    df_copy = df.copy()
    wind_speeds = df_copy['speed'].values
    if use_debiased and data_source != "Demo" and "Raw" in data_source:
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
        return return_heights, max_event, params
    else:
        return None, None, None

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
# Find Highest Wave Function
# ============================================================================

def find_highest_wave(data, fetch_km, use_debiased, data_source):
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
    
    st.subheader("📊 Wave Distribution at Peak Hour")
    wind_speed_max = max_wave['speed']
    wind_direction_max = max_wave['direction']
    if use_debiased and data_source != "Demo" and "Raw" in data_source:
        wind_speed_max = wind_speed_max * DEBIAS_FACTOR
    wave_heights_grid, wave_periods_grid, _ = generate_swan_wave_distribution(wind_speed_max, wind_direction_max)
    
    col1, col2 = st.columns(2)
    with col1:
        fig_hs = go.Figure(data=go.Heatmap(z=wave_heights_grid * 100, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)], colorscale='RdYlGn', text=np.round(wave_heights_grid * 100, 1), texttemplate='<b>%{text} cm</b>', colorbar_title="Wave Height (cm)"))
        fig_hs.update_layout(title="Wave Height Distribution", height=500, width=600)
        st.plotly_chart(fig_hs, use_container_width=True)
    with col2:
        fig_tp = go.Figure(data=go.Heatmap(z=wave_periods_grid, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)], colorscale='Plasma', text=np.round(wave_periods_grid, 1), texttemplate='<b>%{text} s</b>', colorbar_title="Wave Period (s)"))
        fig_tp.update_layout(title="Wave Period Distribution", height=500, width=600)
        st.plotly_chart(fig_tp, use_container_width=True)
    
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
# Main App
# ============================================================================

def main():
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
        st.session_state.processed = False
    if 'data_source' not in st.session_state:
        st.session_state.data_source = None
    if 'show_highest_wave' not in st.session_state:
        st.session_state.show_highest_wave = False

    # Title with gradient background
    st.markdown("""
    <div class="title-gradient">
        <h1> Key Informatics Wind/Waves Analysis Tool</h1>
        <p>Nyenje Bay, Lake Kariba | Complete wind, wave, and SWAN wave modeling analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 **Key Concept:** Bathymetry is **CONSTANT** (loaded once). Wind files are **VARIABLE** (one per hour from ERA5 debiased data)")

    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## 📊 Study Area")
        st.markdown(f"""
        | Parameter | Value |
        |-----------|-------|
        | **Location** | Nyenje Bay |
        | **Center** | {abs(NYENJE_CENTER_LAT)}°S, {NYENJE_CENTER_LON}°E |
        | **Domain** | {DOMAIN_X/1000:.1f} km × {DOMAIN_Y/1000:.1f} km |
        | **Grid** | {NX} × {NY} points |
        | **Resolution** | {CELL_SIZE_X:.0f} m |
        """)
        st.markdown("---")
        
        st.markdown("## 🗺️ Bathymetry (CONSTANT)")
        if REAL_BATHYMETRY is not None:
            st.success("✅ Loaded: nyenje_bathymetry_9x8.bot")
            st.info(f"**Depth range:** {REAL_BATHYMETRY.min():.1f}m - {REAL_BATHYMETRY.max():.1f}m")
        else:
            st.error("⚠️ Bathymetry file not found!")
        st.markdown("---")
        
        st.markdown("## 🌀 Tropical Cyclones")
        st.info("✅ **No tropical cyclone has ever reached Lake Kariba**")
        with st.expander("View recent cyclones"):
            for tc in TROPICAL_CYCLONES:
                st.write(f"**{tc['name']} ({tc['year']})** - {tc['impact']}")
        st.markdown("---")
        
        st.markdown("## ⚙️ Settings")
        fetch_km = st.slider("Fetch Length (km)", 1, 20, 4)
        use_debiased = st.checkbox("Apply CCMP Debiasing (×0.718)", value=True)
        st.markdown("---")
        
        st.markdown("## 💨 Wind Averaging Periods")
        st.markdown(f"""
        | Period | Factor | Application |
        |--------|--------|-------------|
        | **10-min mean** | ×{GUST_FACTORS['10min']} | Reference |
        | **3-min mean** | ×{GUST_FACTORS['3min']} | Dynamic |
        | **10-sec gust** | ×{GUST_FACTORS['10sec']} | Peak gust |
        | **3-sec gust** | ×{GUST_FACTORS['3sec']} | Ultimate |
        """)
        st.markdown("---")
        
        st.markdown("## 📂 Data Status")
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
        st.markdown("---")
        
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
        sub1, sub2, sub3, sub4, sub5 = st.tabs([
            "📡 ERA5 Download", "🔧 Debiasing", "✅ Validation", "⚙️ Process Data", "🌊 SWAN Extract"
        ])
        
        with sub1:
            st.markdown("### 📡 ERA5 Data Download")
            st.info("Download ERA5 reanalysis data from Copernicus Climate Data Store")
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Start Year", 1940, 2023, 1990, key="era5_start")
                st.number_input("End Year", 1940, 2023, 2020, key="era5_end")
            with col2:
                st.markdown("**Region:** Lake Kariba")
                st.markdown("- Latitude: 18°S to 10°S")
                st.markdown("- Longitude: 26°E to 30°E")
            st.markdown("**After download:** Place files in `data/era5/raw/`")
        
        with sub2:
            st.markdown("### 🔧 Debiasing ERA5 Data")
            st.info(f"Apply CCMP debiasing factor ({DEBIAS_FACTOR})")
            col1, col2 = st.columns(2)
            with col1:
                debias_start = st.selectbox("Start Year", list(range(1971, 2021)), index=0)
                debias_end = st.selectbox("End Year", list(range(1971, 2021)), index=49)
            with col2:
                st.markdown(f"**Input:** `{RAW_ERA5_DIR}`")
                st.markdown(f"**Output:** `{DEBIASED_ERA5_DIR}`")
            if st.button("🚀 Apply Debiasing", type="primary", use_container_width=True):
                if not XARRAY_AVAILABLE:
                    st.error("Install: pip install xarray netCDF4")
                else:
                    years = list(range(debias_start, debias_end + 1))
                    with st.spinner(f"Debiasing {len(years)} years..."):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        def update_progress(current, total, filename):
                            progress_bar.progress(current / total)
                            status_text.text(f"Processing: {filename} ({current}/{total})")
                        count, files = batch_debias_era5(RAW_ERA5_DIR, DEBIASED_ERA5_DIR, years, update_progress)
                        progress_bar.empty()
                        status_text.empty()
                        st.success(f"✅ Debiased {count} files")
                        st.balloons()
        
        with sub3:
            st.markdown("### ✅ Validation")
            st.info("Compare ERA5 with CCMP satellite data")
            era5_files = glob.glob(os.path.join(DEBIASED_ERA5_DIR, "*.nc"))
            ccmp_files = glob.glob(os.path.join(CCMP_DIR, "*.nc"))
            st.caption(f"Found {len(era5_files)} debiased ERA5 files, {len(ccmp_files)} CCMP files")
            if st.button("Run Validation", type="primary", use_container_width=True):
                if not era5_files:
                    st.warning("No debiased ERA5 files found. Run debiasing first.")
                elif not ccmp_files:
                    st.warning("No CCMP files found in `data/ccmp/raw/`")
                else:
                    with st.spinner("Validating..."):
                        results = []
                        for ef in era5_files[:3]:
                            for cf in ccmp_files[:3]:
                                val = validate_debiased_data(ef, cf)
                                if val:
                                    results.append(val)
                        if results:
                            df_val = pd.DataFrame(results)
                            col1, col2, col3 = st.columns(3)
                            with col1: st.metric("ERA5 Original", f"{df_val['era5_original'].mean():.2f} m/s")
                            with col2: st.metric("ERA5 Debiased", f"{df_val['era5_debiased'].mean():.2f} m/s")
                            with col3: st.metric("CCMP", f"{df_val['ccmp'].mean():.2f} m/s")
                            fig = go.Figure()
                            fig.add_trace(go.Bar(name='Original Bias', x=['Bias'], y=[df_val['bias_original'].mean()], marker_color='red'))
                            fig.add_trace(go.Bar(name='Debiased Bias', x=['Bias'], y=[df_val['bias_debiased'].mean()], marker_color='green'))
                            fig.update_layout(title="Bias vs CCMP", height=400)
                            st.plotly_chart(fig, use_container_width=True)
                            st.success("Validation complete!")
                        else:
                            st.warning("No validation data. Check file formats.")
        
        with sub4:
            st.markdown("### ⚙️ Process Data")
            data_dir = st.radio("Select source:", ["Raw ERA5", "Debiased ERA5"], horizontal=True)
            use_dir = RAW_ERA5_DIR if data_dir == "Raw ERA5" else DEBIASED_ERA5_DIR
            files = glob.glob(os.path.join(use_dir, "*.nc"))
            st.info(f"Found {len(files)} files in {use_dir}")
            
            if st.button("📊 Process Files", type="primary", use_container_width=True):
                if not XARRAY_AVAILABLE:
                    st.error("Install: pip install xarray")
                else:
                    # Progress bar for processing
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    def update_progress(current, total, filename):
                        progress_bar.progress(current / total)
                        status_text.text(f"📁 Processing file {current}/{total}: {filename}")
                    result = process_all_files(use_dir, NYENJE_CENTER_LAT, NYENJE_CENTER_LON, update_progress)
                    progress_bar.empty()
                    status_text.empty()
                    if result:
                        st.session_state.processed_data = result
                        st.session_state.processed = True
                        st.session_state.data_source = data_dir
                        st.success(f"✅ Processed {result['total_records']:,} records")
                        st.balloons()
                    else:
                        st.error("No data processed")
        
        with sub5:
            st.markdown("### 🌊 Extract SWAN Wind Files")
            swan_year = st.selectbox("Select Year", list(range(1971, 2021)), index=49)
            existing = get_existing_wind_files(WIND_FILES_DIR)
            st.caption(f"Existing .wnd files: {len(existing)}")
            if st.button("🚀 Extract SWAN Files", type="primary", use_container_width=True):
                if not SCIPY_AVAILABLE:
                    st.error("Install: pip install scipy")
                else:
                    with st.spinner(f"Extracting {swan_year}..."):
                        year_files = glob.glob(os.path.join(DEBIASED_ERA5_DIR, f"*{swan_year}*.nc"))
                        if not year_files:
                            st.warning(f"No files for {swan_year}")
                        else:
                            total = 0
                            for f in year_files:
                                count, _ = extract_swan_wind_from_debiased_era5(f, WIND_FILES_DIR, 1.0)
                                total += count
                            st.success(f"✅ Extracted {total} wind files")
                            st.balloons()

    # ========================================================================
    # TAB 2: Wind Statistics
    # ========================================================================
    with tab2:
        st.header("💨 Wind Statistics")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        data = st.session_state.processed_data
        df = data['df'].copy()
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            df['wind_speed_hourly'] = df['speed'] * DEBIAS_FACTOR
            df['gust_3sec'] = df['gust_3sec'] * DEBIAS_FACTOR
            df['gust_10sec'] = df['gust_10sec'] * DEBIAS_FACTOR
            df['wind_speed_3min'] = df['wind_speed_3min'] * DEBIAS_FACTOR
            df['wind_speed_10min'] = df['wind_speed_10min'] * DEBIAS_FACTOR
        
        wsub1, wsub2, wsub3, wsub4, wsub5 = st.tabs([
            "📈 Summary", "📊 Averages Comparison", "🌅 Wind Rose", "⏱️ Time Series", "🔥 Extremes"
        ])
        
        with wsub1:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mean Wind Speed", f"{np.mean(data['all_speeds']):.2f} m/s")
                st.metric("Median", f"{np.median(data['all_speeds']):.2f} m/s")
            with col2:
                st.metric("Max Wind Speed", f"{data['global_max']['speed']:.2f} m/s")
                st.metric("Year", f"{data['global_max']['year']}")
            with col3:
                mean_dir, _ = calculate_circular_mean(data['all_directions'])
                st.metric("Mean Direction", f"{mean_dir:.1f}°")
                st.metric("Prevailing", wind_direction_to_cardinal(mean_dir))
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=data['all_speeds'], nbinsx=30, marker_color='steelblue'))
            fig.update_layout(title="Wind Speed Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # ================================================================
        # WIND AVERAGES COMPARISON WITH CLEAR EXPLANATIONS
        # ================================================================
        with wsub2:
            st.subheader("📊 Wind Averages Comparison")
            
            # Explanation box
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-left: 4px solid #1e3c72;">
                <h4>📖 Understanding Wind Averaging Periods & Gust Factors</h4>
                <p><strong>Why different averaging periods?</strong> Wind speed varies significantly over time. 
                Short-term gusts can be much higher than the average wind speed, which is important for:</p>
                <ul>
                    <li><strong>Structural design</strong> - Buildings and structures must withstand peak gusts</li>
                    <li><strong>Wave modeling</strong> - Waves respond to wind over different time scales</li>
                    <li><strong>Emergency planning</strong> - Gusts can cause sudden hazards</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Create comparison dataframe with explanations
            comparison_data = {
                'Parameter': [
                    'Hourly Mean', '3-Minute Average', '10-Minute Average',
                    '3-Second Gust', '10-Second Gust'
                ],
                'Time Period': [
                    '60 minutes', '3 minutes', '10 minutes',
                    '3 seconds', '10 seconds'
                ],
                'Gust Factor': [
                    '1.00 (reference)', 
                    f'{GUST_FACTORS["3min"]:.2f}', 
                    f'{GUST_FACTORS["10min"]:.2f}',
                    f'{GUST_FACTORS["3sec"]:.2f}', 
                    f'{GUST_FACTORS["10sec"]:.2f}'
                ],
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
            }
            
            comparison_df = pd.DataFrame(comparison_data)
            
            # Display table with styling
            st.dataframe(
                comparison_df.style.format({
                    'Mean (m/s)': '{:.2f}',
                    'Max (m/s)': '{:.2f}'
                }).background_gradient(cmap='YlOrRd', subset=['Mean (m/s)', 'Max (m/s)']),
                use_container_width=True
            )
            
            # Detailed explanations in expander
            with st.expander("🔍 Click here for detailed explanation of each averaging period & gust factor"):
                st.markdown("""
                ### 📊 Wind Averaging Periods Explained
                
                | Period | Description | Application |
                |--------|-------------|-------------|
                | **Hourly Mean** | Average wind speed over 60 minutes. Standard meteorological measurement. | Reference wind speed, climate studies, daily averages |
                | **3-Minute Average** | Average wind speed over 3 minutes. Smooths short-term fluctuations. | Dynamic response of structures, ship maneuvering |
                | **10-Minute Average** | Average wind speed over 10 minutes. Common in maritime forecasts. | Standard for wave forecasting, marine operations |
                | **3-Second Gust** | Peak wind speed over 3 seconds. Highest instantaneous wind speed. | Ultimate structural loads, extreme events |
                | **10-Second Gust** | Peak wind speed over 10 seconds. Sustained gust conditions. | Building codes, bridge design, emergency response |
                
                ### 🔢 Gust Factors Explained
                
                **Gust factor** = (Peak gust speed) / (Mean wind speed)
                
                - **Gust factor for 3-second gust: 1.45**
                  - The 3-second gust is typically 45% higher than the mean wind speed
                  - Example: If mean wind is 10 m/s, 3-sec gust ≈ 14.5 m/s
                  - Used for: Ultimate limit state design, extreme load cases
                
                - **Gust factor for 10-second gust: 1.35**
                  - The 10-second gust is typically 35% higher than the mean wind speed
                  - Example: If mean wind is 10 m/s, 10-sec gust ≈ 13.5 m/s
                  - Used for: Serviceability limit states, operational limits
                
                - **3-Minute average factor: 1.15**
                  - 3-minute average is typically 15% higher than hourly average
                  - Captures medium-term wind variability
                
                - **10-Minute average factor: 1.00**
                  - Reference period for maritime forecasts
                  - Same as hourly mean for practical purposes
                
                ### 💡 Practical Example
                
                If the **hourly mean wind speed** is **10 m/s**:
                
                | Period | Calculated Speed | Physical Meaning |
                |--------|-----------------|------------------|
                | 3-Minute Average | 11.5 m/s | Average over 3 minutes |
                | 10-Minute Average | 10.0 m/s | Standard marine forecast |
                | 3-Second Gust | 14.5 m/s | Peak instantaneous gust |
                | 10-Second Gust | 13.5 m/s | Sustained gust over 10 seconds |
                
                ### 🌊 Why This Matters for Wave Modeling
                
                - **Short-period waves** (wind sea) respond to gusty winds (3-sec to 10-sec)
                - **Long-period waves** (swell) respond to longer averages (3-min to 10-min)
                - **Wave breaking** is influenced by peak gusts
                - **Structural loading** on offshore platforms depends on gust factors
                """)
            
            # Bar chart comparison
            st.subheader("📊 Visual Comparison of Wind Speeds")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=comparison_df['Parameter'], y=comparison_df['Mean (m/s)'], 
                                name='Mean', marker_color='steelblue', text=comparison_df['Mean (m/s)'].round(2),
                                textposition='outside'))
            fig.add_trace(go.Bar(x=comparison_df['Parameter'], y=comparison_df['Max (m/s)'], 
                                name='Maximum', marker_color='coral', text=comparison_df['Max (m/s)'].round(2),
                                textposition='outside'))
            fig.update_layout(title="Wind Speed Comparison by Averaging Period", 
                             xaxis_title="Averaging Period", yaxis_title="Wind Speed (m/s)",
                             barmode='group', height=500,
                             xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Explanation of the chart
            st.info("""
            **💡 Understanding the Chart:**
            - **Blue bars (Mean):** Average wind speed for each averaging period
            - **Red bars (Maximum):** Highest recorded wind speed for each period
            - The difference between blue and red bars shows the variability
            - Larger difference = more gusty conditions
            """)
            
            # Download button
            csv = comparison_df.to_csv(index=False)
            st.download_button("📥 Download Averages Comparison (CSV)", csv, "wind_averages_comparison.csv", "text/csv")
        
        with wsub3:
            if st.button("Generate Wind Rose"):
                fig = create_wind_rose(data['all_speeds'], data['all_directions'], f"Lake Kariba")
                st.plotly_chart(fig, use_container_width=True)
        
        with wsub4:
            sample = df.iloc[:1000] if len(df) > 1000 else df
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sample['datetime'], y=sample['wind_speed_hourly'], name='Hourly', line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=sample['datetime'], y=sample['wind_speed_3min'], name='3-min', line=dict(color='green')))
            fig.add_trace(go.Scatter(x=sample['datetime'], y=sample['wind_speed_10min'], name='10-min', line=dict(color='orange')))
            fig.update_layout(title="Wind Speed Time Series", height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        with wsub5:
            if 'yearly_max' in data:
                years = sorted(data['yearly_max'].keys())
                values = [data['yearly_max'][y] for y in years]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=years, y=values, mode='lines+markers', line=dict(color='red')))
                fig.update_layout(title="Annual Maximum Wind Speeds", height=400)
                st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 3: Wave Analysis
    # ========================================================================
    with tab3:
        st.header("🌊 JONSWAP Wave Analysis")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        data = st.session_state.processed_data
        wind_speeds = data['all_speeds'][:5000]
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            wind_speeds = wind_speeds * DEBIAS_FACTOR
        wave_heights, wave_periods = zip(*[calculate_wave_height(ws, fetch_km) for ws in wind_speeds])
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Mean Wave Height", f"{np.mean(wave_heights):.3f} m")
        with col2: st.metric("Max Wave Height", f"{np.max(wave_heights):.3f} m")
        with col3: st.metric("Sig Wave (H₁/₃)", f"{np.percentile(wave_heights, 66.7):.3f} m")
        with col4: st.metric("Mean Period", f"{np.mean(wave_periods):.2f} s")
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=wave_heights, nbinsx=30, marker_color='steelblue'))
        fig.update_layout(title="Wave Height Distribution", height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 4: SWAN Model
    # ========================================================================
    with tab4:
        st.header(" SWAN Wave Model")
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        data = st.session_state.processed_data
        df = data['df']
        
        swan_sub1, swan_sub2, swan_sub3, swan_sub4 = st.tabs([
            "🎯 Single Analysis", "📅 Monthly Maxima", "📈 Yearly Maxima", "🏆 Extreme Value Analysis"
        ])
        
        with swan_sub1:
            st.subheader("🎯 Single Time Step Wave Analysis")
            
            # DOMAIN EXTENT CARD
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 15px; border-radius: 10px; color: white; margin: 10px 0;">
                <h4>📍 Nyenje Bay Domain Extent</h4>
                <table style="width: 100%; color: white;">
                    <tr><td><b>Center:</b></td><td>16.53°S, 28.83°E</td><td><b>Size:</b></td><td>4.0 km × 3.5 km</td></tr>
                    <tr><td><b>West:</b></td><td>28.81113°E</td><td><b>East:</b></td><td>28.84887°E</td></tr>
                    <tr><td><b>South:</b></td><td>16.54577°S</td><td><b>North:</b></td><td>16.51423°S</td></tr>
                    <tr><td><b>Grid:</b></td><td>9 × 8 points</td><td><b>Resolution:</b></td><td>500 m</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
            # Bathymetry map
            if REAL_BATHYMETRY is not None:
                st.subheader("🗺️ Nyenje Bay Bathymetry (CONSTANT)")
                fig_bathy = go.Figure(data=go.Heatmap(
                    z=REAL_BATHYMETRY, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)],
                    colorscale='Viridis', text=np.round(REAL_BATHYMETRY, 1),
                    texttemplate='<b>%{text} m</b>', colorbar_title="Depth (m)"
                ))
                fig_bathy.update_layout(height=450, width=800)
                st.plotly_chart(fig_bathy, use_container_width=True)
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("Min Depth", f"{REAL_BATHYMETRY.min():.1f} m")
                with c2: st.metric("Max Depth", f"{REAL_BATHYMETRY.max():.1f} m")
                with c3: st.metric("Mean Depth", f"{REAL_BATHYMETRY.mean():.1f} m")
            
            st.divider()
            st.subheader("⏰ Select Time Step")
            available_years = sorted([y for y in df['year'].unique() if y is not None])
            if available_years:
                col1, col2, col3, col4 = st.columns(4)
                with col1: selected_year = st.selectbox("Year", available_years, index=len(available_years)-1)
                with col2: selected_month = st.selectbox("Month", range(1, 13), index=0)
                with col3: selected_day = st.selectbox("Day", range(1, 32), index=0)
                with col4: selected_hour = st.selectbox("Hour", range(0, 24), index=0)
                if st.button("🌊 Run SWAN Analysis", type="primary"):
                    target = datetime(selected_year, selected_month, selected_day, selected_hour)
                    df['time_diff'] = abs(df['datetime'] - target)
                    closest = df.loc[df['time_diff'].idxmin()]
                    wind_speed = closest['speed']
                    wind_dir = closest['direction']
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speed = wind_speed * DEBIAS_FACTOR
                    st.info(f"**Wind:** {wind_speed:.2f} m/s from {wind_dir:.0f}° ({wind_direction_to_cardinal(wind_dir)})")
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
                            colorbar_title="Wave Height (cm)",
                            zmin=0, zmax=np.max(wave_h * 100)
                        ))
                        fig_hs.update_layout(
                            title="<b>Wave Height Distribution</b>", 
                            height=550, 
                            width=650,
                            xaxis_title="West → East (m)",
                            yaxis_title="North → South (m)",
                            font=dict(size=14)
                        )
                        st.plotly_chart(fig_hs, use_container_width=True)
                    
                    with col2:
                        st.metric("🌊 Max Wave Height", f"{np.max(wave_h):.3f} m ({np.max(wave_h)*100:.1f} cm)")
                        st.metric("📊 Mean Wave Height", f"{np.mean(wave_h):.3f} m ({np.mean(wave_h)*100:.1f} cm)")
                        st.metric("⏱️ Max Wave Period", f"{np.max(wave_t):.2f} s")
                        st.metric("📈 Mean Wave Period", f"{np.mean(wave_t):.2f} s")
                        
                        fig_tp_small = go.Figure(data=go.Heatmap(
                            z=wave_t, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)],
                            colorscale='Plasma', text=np.round(wave_t, 1), texttemplate='<b>%{text} s</b>',
                            colorbar_title="Period (s)"
                        ))
                        fig_tp_small.update_layout(title="Wave Period Distribution", height=350)
                        st.plotly_chart(fig_tp_small, use_container_width=True)
            else:
                st.warning("No valid years found")
        
        with swan_sub2:
            st.subheader("📅 Monthly Maximum Wave Heights")
            if st.button("Calculate Monthly Maxima", type="primary"):
                with st.spinner("Calculating..."):
                    monthly_max, monthly_stats = calculate_monthly_maxima(df, fetch_km, use_debiased, st.session_state.data_source)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=monthly_max['year_month'], y=monthly_max['wave_height'], mode='lines+markers'))
                    fig.update_layout(title="Monthly Maxima", height=500, xaxis_tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
                    csv = monthly_max.to_csv(index=False)
                    st.download_button("📥 Download", csv, "monthly_max_waves.csv")
        
        with swan_sub3:
            st.subheader("📈 Yearly Maximum Wave Heights")
            if st.button("Calculate Yearly Maxima", type="primary"):
                with st.spinner("Calculating..."):
                    yearly_max = calculate_yearly_maxima(df, fetch_km, use_debiased, st.session_state.data_source)
                    max_row = yearly_max.loc[yearly_max['wave_height'].idxmax()]
                    
                    fig = go.Figure()
                    colors = ['red' if y == max_row['year'] else 'steelblue' for y in yearly_max['year']]
                    fig.add_trace(go.Bar(x=yearly_max['year'], y=yearly_max['wave_height'], 
                                        marker_color=colors, text=yearly_max['wave_height'].round(3),
                                        textposition='outside', name='Annual Max Hₛ'))
                    fig.add_annotation(x=max_row['year'], y=max_row['wave_height'], 
                                      text=f"🏆 Max: {max_row['wave_height']:.3f}m", 
                                      showarrow=True, arrowhead=2, arrowcolor="red", ax=0, ay=-40,
                                      font=dict(size=14, color="red"))
                    fig.update_layout(title="Yearly Maximum Wave Heights", xaxis_title="Year", 
                                     yaxis_title="Wave Height (m)", height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    st.success(f"🏆 Year {max_row['year']} had the highest wave: {max_row['wave_height']:.3f} m")
                    csv = yearly_max.to_csv(index=False)
                    st.download_button("📥 Download Yearly Maxima Data", csv, "yearly_max_waves.csv", "text/csv")
        
        with swan_sub4:
            st.subheader("🏆 Extreme Value Analysis")
            if st.button("Run Extreme Value Analysis", type="primary"):
                if not SCIPY_AVAILABLE:
                    st.error("Install scipy")
                else:
                    with st.spinner("Analyzing..."):
                        return_heights, max_event, _ = extreme_value_analysis(df, fetch_km, use_debiased, st.session_state.data_source)
                        if return_heights:
                            df_ret = pd.DataFrame([{'Return Period (years)': rp, 'Wave Height (m)': round(h, 3)} for rp, h in return_heights.items()])
                            st.dataframe(df_ret)
                            hs_50 = return_heights[50]
                            hs_100 = return_heights[100]
                            st.info(f"**50-year wave:** {hs_50:.3f} m | **100-year wave:** {hs_100:.3f} m")
                        else:
                            st.warning("Insufficient data (need at least 5 years)")
    
    # Handle sidebar trigger
    if st.session_state.show_highest_wave and st.session_state.processed:
        st.session_state.show_highest_wave = False
        st.subheader("🏆 Highest Wave Analysis")
        find_highest_wave(st.session_state.processed_data, fetch_km, use_debiased, st.session_state.data_source)

if __name__ == "__main__":
    main()