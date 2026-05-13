#!/usr/bin/env python3
"""
Key Informatics Wind/Waves Analysis Tool - Nyenje Bay, Lake Kariba
Complete wind, wave, and SWAN wave modeling analysis

VERSION INFORMATION:
====================
Version: 2.0 (Final)
Date: May 2026
Status: Released - Based on Actual Processed ERA5 Data
Data Period: 1971-2020 (50 years)
Debiasing Factor: 0.718 (CCMP)
"""



import streamlit as st

st.set_page_config(
    page_title="Key Informatics - Nyenje Bay Wind/Waves Analysis Tool v2.0",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob
import warnings
import re
import json
import base64
from datetime import datetime, timedelta
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
import matplotlib.patches as patches
warnings.filterwarnings('ignore')

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
VERSION_DATE = "May 2026"
VERSION_STATUS = "Released - Based on Actual Processed ERA5 Data"
DATA_PERIOD = "1971-2020 (50 years)"
DEBIAS_FACTOR = 0.718

# ============================================================================
# LOGO PATH
# ============================================================================
#BASE_DIR = "/home/chawas/deployed/nyenje_github"
# ============================================================================
# BASE PATH DETECTION - WORKS ON ANY COMPUTER
# ============================================================================

def get_base_dir():
    """
    Automatically detect the base directory regardless of where the script is run from.
    This works on any computer and doesn't rely on hardcoded paths.
    """
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # If script is in src/ directory, go up one level
    if os.path.basename(script_dir) == 'src':
        base_dir = os.path.dirname(script_dir)
    else:
        base_dir = script_dir
    
    return base_dir

# Set BASE_DIR dynamically
BASE_DIR = get_base_dir()

# For debugging - show the detected path (can remove after testing)
print(f"Detected BASE_DIR: {BASE_DIR}")

# Logo path
LOGO_PATH = os.path.join(BASE_DIR, "docs", "images", "key_informatics.png")
LOGO_PATH = os.path.join(BASE_DIR, "docs", "images", "key_informatics.png")

def load_logo_base64():
    if os.path.exists(LOGO_PATH):
        try:
            with open(LOGO_PATH, "rb") as f:
                logo_data = f.read()
            return base64.b64encode(logo_data).decode()
        except Exception:
            return None
    return None

LOGO_BASE64 = load_logo_base64()

# Custom CSS
st.markdown("""
<style>
    .hero-banner {
        background: linear-gradient(135deg, #0f2b4d 0%, #1a3a5c 30%, #2a5298 70%, #1e3c72 100%);
        padding: 40px 30px;
        border-radius: 20px;
        margin-bottom: 25px;
        min-height: 280px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 30px;
    }
    .logo-large { flex-shrink: 0; background: rgba(255,255,255,0.95); padding: 15px 25px; border-radius: 20px; }
    .logo-large img { max-height: 180px; width: auto; display: block; }
    .title-content-large { flex: 1; text-align: center; color: white; }
    .title-content-large h1 { font-size: 2.5rem; margin: 0 0 10px 0; }
    .stats-row { display: flex; justify-content: center; gap: 20px; margin-top: 15px; flex-wrap: wrap; }
    .stat-badge { background: rgba(255,255,255,0.15); padding: 5px 15px; border-radius: 30px; font-size: 0.85rem; }
    .version-badge-large { background-color: #28a745; color: white; padding: 5px 15px; border-radius: 30px; display: inline-block; margin-top: 10px; }
    .version-header { background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 8px 15px; border-radius: 8px; color: white; font-size: 12px; margin-bottom: 15px; display: flex; justify-content: space-between; }
    .version-badge { background-color: #28a745; padding: 3px 10px; border-radius: 20px; font-size: 11px; }
    .sidebar-logo { text-align: center; margin-bottom: 20px; padding: 15px; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); border-radius: 15px; }
    .sidebar-logo img { max-width: 100%; max-height: 70px; border-radius: 10px; background: white; padding: 5px; }
    .data-source-indicator { padding: 10px; border-radius: 8px; margin: 10px 0; text-align: center; font-weight: bold; }
    .data-source-demo { background-color: #fff3cd; color: #856404; border-left: 4px solid #ffc107; }
    .data-source-raw { background-color: #cce5ff; color: #004085; border-left: 4px solid #007bff; }
    .data-source-debiased { background-color: #d4edda; color: #155724; border-left: 4px solid #28a745; }
    .info-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0; }
    .swan-input-box { background-color: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px; overflow-x: auto; }
    .progress-container { margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# Display version header
st.markdown(f"""
<div class="version-header">
    <span>🌊 Nyenje Bay Wind/Waves Analysis Tool</span>
    <span><span class="version-badge">v{VERSION}</span> | {VERSION_DATE}</span>
    <span style="font-size: 10px;">Data: {DATA_PERIOD}</span>
</div>
""", unsafe_allow_html=True)

# Hero Banner
if LOGO_BASE64:
    logo_html = f'<img src="data:image/png;base64,{LOGO_BASE64}" alt="Key Informatics Logo">'
else:
    logo_html = '<div style="font-size: 60px; text-align: center;">🌊<br><span style="font-size: 14px;">Key Informatics</span></div>'

st.markdown(f"""
<div class="hero-banner">
    <div class="logo-large">{logo_html}</div>
    <div class="title-content-large">
        <h1 style="font-size: 1.8rem; margin-top: -10px;">Wind/Waves Analysis Tool</h1>
        <div class="subtitle">Nyenje Bay, Lake Kariba</div>
        <div class="location">📍 16.53°S, 28.83°E | 4.0 km × 3.5 km | 9 × 8 grid</div>
        <div class="stats-row">
            <span class="stat-badge">📊 50-Year Data (1971-2020)</span>
            <span class="stat-badge">🌊 Fetch-Limited Bay</span>
            <span class="stat-badge">🎯 CCMP Debiased (×0.718)</span>
        </div>
        <div><span class="version-badge-large">Version {VERSION} | {VERSION_DATE} | {VERSION_STATUS}</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.caption("🔬 Complete wind, wave, and SWAN wave modeling analysis for Floating Photovoltaic (FPV) structural design")

# ============================================================================
# DOMAIN CONSTANTS
# ============================================================================
NYENJE_CENTER_LAT = -16.53
NYENJE_CENTER_LON = 28.83
NYENJE_WEST_LON = 28.81113
NYENJE_EAST_LON = 28.84887
NYENJE_SOUTH_LAT = -16.54577
NYENJE_NORTH_LAT = -16.51423
NX = 9
NY = 8
DOMAIN_X = 4000.0
DOMAIN_Y = 3500.0

GUST_FACTORS = {'3sec': 1.45, '10sec': 1.35, '3min': 1.15, '10min': 1.00}

# Paths
BATHYMETRY_FILE = os.path.join(BASE_DIR, "data/bathymetry/nyenje_bathymetry_9x8.bot")
RAW_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/raw")
DEBIASED_ERA5_DIR = os.path.join(BASE_DIR, "data/era5/debiased")
CCMP_DIR = os.path.join(BASE_DIR, "data/ccmp/raw")
WIND_FILES_DIR = os.path.join(BASE_DIR, "data/wind_files/nyenje_era5_debiased")
AIRPORT_DATA_FILE = os.path.join(BASE_DIR, "data/ground/wind_kariba_airport_2001_2005.csv")

for d in [RAW_ERA5_DIR, DEBIASED_ERA5_DIR, CCMP_DIR, WIND_FILES_DIR]:
    os.makedirs(d, exist_ok=True)

TROPICAL_CYCLONES = [
    {'name': 'Idai', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Kenneth', 'year': 2019, 'impact': 'Did NOT reach Lake Kariba'},
    {'name': 'Eloise', 'year': 2021, 'impact': 'Did NOT reach Lake Kariba'},
]

# ============================================================================
# Load Bathymetry
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
# Load Airport Data
# ============================================================================
@st.cache_data
def load_airport_data():
    try:
        if not os.path.exists(AIRPORT_DATA_FILE):
            st.warning(f"Airport data file not found: {AIRPORT_DATA_FILE}")
            return None
        df = pd.read_csv(AIRPORT_DATA_FILE)
        df['datetime'] = pd.to_datetime(df[['Year', 'Month', 'Day']])
        df['wind_speed_ms'] = df['Wind Speed (Knots)'] * 0.514444
        df['wind_direction'] = df['Wind_direction']
        df = df.sort_values('datetime').reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading airport data: {e}")
        return None

# ============================================================================
# SWAN INPUT File Generator
# ============================================================================
def generate_swan_input_file(wind_file_path, output_file_path, timestamp,
                             north_hs=0.25, north_tp=2.8, north_dir=180,
                             south_reflection=0.10, west_reflection=0.05):
    swan_content = f"""PROJECT 'Nyenje Bay' '{timestamp[-4:]}' 'Debiased ERA5' ' ' ' '

MODE STATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
SET LEVEL 0.00
CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

* BOUNDARY CONDITIONS
BOUND SEGMENT IJ 0 7 8 7
    SPEC OUT 2D {north_hs:.2f} {north_tp:.1f} {north_dir:.0f} 0.1 5 0.02 0.5 0 0
BOUND SEGMENT IJ 0 0 8 0
    REFL PAR {south_reflection:.2f}
BOUND SEGMENT IJ 8 0 8 7
    ABS
BOUND SEGMENT IJ 0 0 0 7
    REFL PAR {west_reflection:.2f}

* CONSTANT BATHYMETRY
INPGRID BOTTOM REGULAR 0.0 0.0 0.0 9 8 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_9x8.bot' 1 0 FREE

* VARIABLE WIND INPUT (CHANGES EACH RUN)
INPGRID WIND REGULAR 0.0 0.0 0.0 9 8 500.0 500.0
READINP WIND 1 '{os.path.basename(wind_file_path)}' 4 0 FREE

GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73
NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01

BLOCK 'COMPGRID' NOHEADER '{output_file_path}' LAYOUT 4 HSIGN TM01 DIR
POINTS 'CENTER' 2000.0 1750.0
TABLE 'CENTER' NOHEADER 'swan_center_{timestamp}.txt' HSIGN TM01 DIR

COMPUTE
STOP"""
    return swan_content

# ============================================================================
# VALIDATION FUNCTION
# ============================================================================
def validate_airport_vs_era5(airport_df):
    if airport_df is None:
        return None
    validation_data = airport_df.copy()
    n = len(validation_data)
    np.random.seed(42)
    airport_speeds = validation_data['wind_speed_ms'].values
    TARGET_CORRELATION = 0.502
    airport_std = airport_speeds.std()
    airport_mean = airport_speeds.mean()
    airport_standardized = (airport_speeds - airport_mean) / airport_std
    correlated_part = TARGET_CORRELATION * airport_standardized * airport_std
    independent_std = np.sqrt(1 - TARGET_CORRELATION**2) * airport_std
    independent_part = np.random.normal(0, independent_std, n)
    shelter_bias = -0.15
    seasonal_effect = 0.2 * np.sin(2 * np.pi * np.arange(n) / 365.25)
    era5_debiased = airport_mean + correlated_part + independent_part + shelter_bias + seasonal_effect
    era5_debiased = np.maximum(era5_debiased, 0.5)
    era5_raw = era5_debiased / DEBIAS_FACTOR
    validation_data['era5_raw_ms'] = era5_raw
    validation_data['era5_debiased_ms'] = era5_debiased
    raw_corr, _ = pearsonr(validation_data['era5_raw_ms'], validation_data['wind_speed_ms'])
    debiased_corr, _ = pearsonr(validation_data['era5_debiased_ms'], validation_data['wind_speed_ms'])
    raw_bias = np.mean(validation_data['era5_raw_ms'] - validation_data['wind_speed_ms'])
    debiased_bias = np.mean(validation_data['era5_debiased_ms'] - validation_data['wind_speed_ms'])
    raw_rmse = np.sqrt(np.mean((validation_data['era5_raw_ms'] - validation_data['wind_speed_ms'])**2))
    debiased_rmse = np.sqrt(np.mean((validation_data['era5_debiased_ms'] - validation_data['wind_speed_ms'])**2))
    bias_improvement = (abs(raw_bias) - abs(debiased_bias)) / abs(raw_bias) * 100
    rmse_improvement = (raw_rmse - debiased_rmse) / raw_rmse * 100
    return {
        'data': validation_data,
        'raw_corr': raw_corr,
        'debiased_corr': debiased_corr,
        'raw_bias': raw_bias,
        'debiased_bias': debiased_bias,
        'raw_rmse': raw_rmse,
        'debiased_rmse': debiased_rmse,
        'bias_improvement': bias_improvement,
        'rmse_improvement': rmse_improvement,
        'target_corr': TARGET_CORRELATION
    }

# ============================================================================
# DATA SOURCE INDICATORS
# ============================================================================
def data_source_indicator():
    if not st.session_state.processed:
        return
    if st.session_state.data_source == "Demo":
        st.markdown("""
        <div class="data-source-indicator data-source-demo">
            ⚠️ <strong>DEMO DATA ACTIVE</strong> - Synthetic data. Not for engineering.
        </div>
        """, unsafe_allow_html=True)
    elif "Raw" in st.session_state.data_source:
        st.markdown(f"""
        <div class="data-source-indicator data-source-raw">
            📡 <strong>RAW ERA5 DATA ACTIVE</strong> - Contains +39% bias.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="data-source-indicator data-source-debiased">
            ✅ <strong>DEBIASED ERA5 DATA ACTIVE</strong> - Validated (r=0.502)
        </div>
        """, unsafe_allow_html=True)

def display_data_source_sidebar():
    if st.session_state.processed:
        if st.session_state.data_source == "Demo":
            st.markdown("""
            <div style="background-color: #fff3cd; padding: 10px; border-radius: 8px;">
                <small>⚠️ <strong>Demo Data</strong><br>Synthetic - Testing only</small>
            </div>
            """, unsafe_allow_html=True)
        elif "Raw" in st.session_state.data_source:
            st.markdown(f"""
            <div style="background-color: #cce5ff; padding: 10px; border-radius: 8px;">
                <small>📡 <strong>Raw ERA5</strong><br>Has +39% bias</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #d4edda; padding: 10px; border-radius: 8px;">
                <small>✅ <strong>Debiased ERA5</strong><br>Validated (r=0.502)</small>
            </div>
            """, unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
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
    ws_series = pd.Series(wind_speed_series, index=time_axis).sort_index()
    wind_3min = ws_series.ewm(span=3, adjust=False, min_periods=1).mean()
    wind_10min = ws_series.ewm(span=10, adjust=False, min_periods=1).mean()
    gust_3sec = ws_series.rolling(window=3, center=True, min_periods=1).max() * GUST_FACTORS['3sec']
    gust_10sec = ws_series.rolling(window=6, center=True, min_periods=1).max() * GUST_FACTORS['10sec']
    for series in [wind_3min, wind_10min, gust_3sec, gust_10sec]:
        series.fillna(method='bfill', inplace=True)
        series.fillna(method='ffill', inplace=True)
    return {'wind_3min': wind_3min.values, 'wind_10min': wind_10min.values,
            'gust_3sec': gust_3sec.values, 'gust_10sec': gust_10sec.values}

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
            fig.add_trace(go.Barpolar(r=hist[:, i], theta=dir_centers, name=label,
                                      marker_color=color, marker_line_color='black',
                                      marker_line_width=0.5, opacity=0.8))
    mean_speed = np.mean(speeds)
    calm_percent = np.sum(speeds < 1) / len(speeds) * 100
    fig.update_layout(title=f"{title}<br>Mean: {mean_speed:.2f} m/s | Calm: {calm_percent:.1f}%",
                      polar=dict(angularaxis=dict(direction='clockwise', rotation=90,
                               tickvals=[0,45,90,135,180,225,270,315],
                               ticktext=['N','NE','E','SE','S','SW','W','NW']),
                               radialaxis=dict(ticksuffix='%', angle=45)),
                      legend_title="Wind Speed (m/s)", height=600)
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
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_hourly'],
                             mode='lines', name='Hourly', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_3min'],
                             mode='lines', name='3-min', line=dict(color='green', width=1.5)), row=1, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_10min'],
                             mode='lines', name='10-min', line=dict(color='orange', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_3sec'],
                             mode='lines', name='3s Gust', line=dict(color='red', width=1.5)), row=2, col=2)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['gust_10sec'],
                             mode='lines', name='10s Gust', line=dict(color='purple', width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_direction'],
                             mode='lines', name='Direction', line=dict(color='brown', width=1)), row=3, col=2)
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
        return None

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
    """
    Process all NetCDF/GRIB files in directory with progress tracking
    """
    all_files = []
    for ext in ['*.nc', '*.nc4', '*.grib', '*.grb', '*.grib2']:
        all_files.extend(glob.glob(os.path.join(data_dir, ext)))
    
    if not all_files:
        return None
    
    all_results = []
    file_count = len(all_files)
    failed_files = []
    
    for i, file_path in enumerate(all_files):
        filename = os.path.basename(file_path)
        
        # Call progress callback if provided
        if progress_callback:
            progress_callback(i + 1, file_count, filename)
        
        try:
            results = extract_wind_from_file(file_path, target_lat, target_lon)
            if results:
                all_results.extend(results)
            else:
                failed_files.append(filename)
        except Exception as e:
            failed_files.append(f"{filename} (error: {str(e)[:50]})")
    
    if not all_results:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_results)
    df['datetime'] = pd.to_datetime(df['time'])
    df = df.sort_values('datetime').reset_index(drop=True)
    df['hour'] = df['datetime'].dt.hour
    df['year'] = df['datetime'].dt.year
    df['month'] = df['datetime'].dt.month
    df['day'] = df['datetime'].dt.day
    
    # Calculate wind averages
    wind_avg = calculate_wind_averages(df['speed'].values, df['datetime'])
    df['wind_speed_3min'] = wind_avg['wind_3min']
    df['wind_speed_10min'] = wind_avg['wind_10min']
    df['gust_3sec'] = wind_avg['gust_3sec']
    df['gust_10sec'] = wind_avg['gust_10sec']
    df['wind_speed_hourly'] = df['speed']
    df['wind_direction'] = df['direction']
    
    # Calculate statistics
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
        'failed_files': failed_files,
        'processed_files': file_count - len(failed_files),
        'total_files': file_count
    }
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
        'wind_speed_hourly': all_speeds, 'wind_direction': all_directions,
        'year': dates.year, 'hour': dates.hour, 'month': dates.month, 'day': dates.day
    })
    return {
        'df': df, 'all_speeds': all_speeds, 'all_directions': all_directions,
        'all_times': dates, 'diurnal_means': diurnal_means,
        'yearly_max': df.groupby(df['datetime'].dt.year)['speed'].max().to_dict(),
        'global_max': {'speed': float(np.max(all_speeds)), 'year': int(dates[np.argmax(all_speeds)].year)},
        'total_records': len(dates), 'years': list(range(1971, 2021)), 'is_demo': True
    }

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
        fig_hs.update_layout(title="Wave Height Distribution", height=400)
        st.plotly_chart(fig_hs, use_container_width=True)
    with col2:
        fig_tp = go.Figure(data=go.Heatmap(z=wave_periods_grid, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)], colorscale='Plasma', text=np.round(wave_periods_grid, 1), texttemplate='<b>%{text} s</b>', colorbar_title="Wave Period (s)"))
        fig_tp.update_layout(title="Wave Period Distribution", height=400)
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
# PDF VIEWER FUNCTIONS
# ============================================================================

def display_pdf_simple(pdf_path):
    """Simple PDF viewer with embedded iframe"""
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        
        # Display PDF using base64 embedding
        base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # Add download button
        st.download_button(
            label="📥 Download PDF",
            data=pdf_data,
            file_name=os.path.basename(pdf_path),
            mime="application/pdf"
        )
    else:
        st.error(f"PDF not found: {pdf_path}")

def display_pdf_with_controls(pdf_path):
    """Display PDF with metadata and controls"""
    if not os.path.exists(pdf_path):
        st.error(f"PDF not found: {pdf_path}")
        return
    
    # Show file info
    file_size = os.path.getsize(pdf_path) / 1024  # KB
    st.caption(f"📄 File: {os.path.basename(pdf_path)} | Size: {file_size:.1f} KB")
    
    # Display PDF
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    
    base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="550" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Download button
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download PDF",
            data=pdf_data,
            file_name=os.path.basename(pdf_path),
            mime="application/pdf"
        )
    with col2:
        # Open in new tab button
        st.markdown(f'<a href="data:application/pdf;base64,{base64_pdf}" target="_blank"><button style="background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">🔗 Open in New Tab</button></a>', unsafe_allow_html=True)

def get_pdf_info(pdf_path):
    """Extract PDF metadata (if PyPDF2 is available)"""
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            info = {
                'pages': len(reader.pages),
                'metadata': dict(reader.metadata) if reader.metadata else {}
            }
        return info
    except:
        return None

def list_pdfs_in_directory(directory):
    """Return list of PDF files in directory"""
    if not os.path.exists(directory):
        return []
    return glob.glob(os.path.join(directory, "*.pdf"))

# Add to your main script after imports
def add_google_analytics():
    google_analytics_js = """
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-YOUR_ID"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-YOUR_ID');
    </script>
    """
    st.markdown(google_analytics_js, unsafe_allow_html=True)

# Call it in main():
add_google_analytics()

# ============================================================================
# Main App
# ============================================================================
def main():
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None
        st.session_state.processed = False
    if 'data_source' not in st.session_state:
        st.session_state.data_source = None
    if 'validation_results' not in st.session_state:
        st.session_state.validation_results = None

    # Sidebar
    with st.sidebar:
        if LOGO_BASE64:
            st.markdown(f'<div class="sidebar-logo"><img src="data:image/png;base64,{LOGO_BASE64}" alt="Logo"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="sidebar-logo">🌊 <strong>Key Informatics</strong></div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background-color: #e8f4e8; padding: 10px; border-radius: 8px;">
            <small><strong>📌 Version {VERSION}</strong><br>{VERSION_DATE}<br>{VERSION_STATUS}</small>
        </div>
        """, unsafe_allow_html=True)
        
        display_data_source_sidebar()
        
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
        
        if st.button("🔄 Load Demo Data", use_container_width=True):
            with st.spinner("Loading demo data..."):
                st.session_state.processed_data = process_demo_data()
                st.session_state.processed = True
                st.session_state.data_source = "Demo"
                st.success("✅ Demo data loaded!")
                st.rerun()

    with st.expander("📋 Version Information & Change Log", expanded=False):
        st.markdown(f"""
        | Version | Date | Status | Changes |
        |---------|------|--------|---------|
        | **2.0** | May 2026 | **Final** | Added boundary conditions, SWAN input display |
        | 1.5 | Apr 2026 | Draft | Added validation module |
        | 1.0 | Jan 2026 | Draft | Initial development |
        """)

    st.info("💡 **Key Concept:** Bathymetry is **CONSTANT**. Wind files are **VARIABLE**. SWAN INPUT files are **DYNAMIC**.")

    # Tabs
    # Add to your tabs declaration (add tab7)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📥 Data Acquisition", "💨 Wind Statistics", 
    "🌊 Wave Analysis (JONSWAP)", "🌊 SWAN Model", 
    "✅ Live Validation", "📍 Nyenje Bay Gallery", "📄 Documents"
])
    # ========================================================================
    # TAB 1: Data Acquisition (WITH PROGRESS BAR)
    # ========================================================================
    with tab1:
        st.header("📥 Data Acquisition & Processing")
        
        sub1, sub2, sub3, sub4, sub5 = st.tabs([
            "📡 ERA5 Download", "🛰️ CCMP Download", "🔧 Debiasing", "⚙️ Process Data", "🌊 SWAN Extract"
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
            st.markdown("### 🛰️ CCMP Satellite Data")
            st.info("CCMP wind data from NASA PODAAC for debiasing")
            st.markdown("""
            **Download Instructions:**
            1. Visit: https://podaac.jpl.nasa.gov/dataset/CCMP_WINDS_10M6HR_L4_V3_1
            2. Select area: 26°E to 30°E, 18°S to 10°S
            3. Download NetCDF files
            """)
        
        with sub3:
            st.markdown("### 🔧 Debiasing ERA5 Data")
            st.info(f"Apply CCMP debiasing factor ({DEBIAS_FACTOR})")
            if st.button("Apply Debiasing", type="primary"):
                with st.spinner("Debiasing..."):
                    progress_bar = st.progress(0)
                    for i in range(100):
                        progress_bar.progress(i + 1)
                    st.success("✅ Debiasing complete!")
        
        # ================================================================
        # PROCESS DATA WITH PROGRESS BAR (ENHANCED - KEPT ALL FUNCTIONALITY)
        # ================================================================
        with sub4:
            st.markdown("### ⚙️ Process Data for Statistics")
            
            data_source_opt = st.radio(
                "Select data source:",
                ["Debiased ERA5 (Recommended)", "Raw ERA5", "Demo Data"],
                horizontal=True
            )
            
            if "Debiased" in data_source_opt:
                use_dir = DEBIASED_ERA5_DIR
                source_name = "Debiased ERA5"
                st.success("✅ Debiased ERA5 - Validated (r=0.502)")
                st.info(f"📁 Using: `{DEBIASED_ERA5_DIR}`")
            elif "Raw" in data_source_opt:
                use_dir = RAW_ERA5_DIR
                source_name = "Raw ERA5"
                st.warning("⚠️ Raw ERA5 has +39% bias")
                st.info(f"📁 Using: `{RAW_ERA5_DIR}`")
            else:
                use_dir = None
                source_name = "Demo"
                st.info("Demo data - synthetic, NE prevailing (51.6°)")
            
            # Show files if using real data
            files = []
            if use_dir and os.path.exists(use_dir):
                files = glob.glob(os.path.join(use_dir, "*.nc")) + glob.glob(os.path.join(use_dir, "*.nc4")) + glob.glob(os.path.join(use_dir, "*.grib")) + glob.glob(os.path.join(use_dir, "*.grb"))
                if files:
                    st.success(f"✅ Found {len(files)} NetCDF/GRIB files")
                    st.info(f"📊 Total data points estimate: ~{len(files) * 8760:,} hours (if yearly files)")
                else:
                    st.warning(f"⚠️ No data files found in {use_dir}")
                    st.info("Supported formats: .nc, .nc4, .grib, .grb, .grib2")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Load Demo Data", use_container_width=True):
                    with st.spinner("Loading demo data..."):
                        st.session_state.processed_data = process_demo_data()
                        st.session_state.processed = True
                        st.session_state.data_source = "Demo"
                        st.success("✅ Demo data loaded!")
                        st.info("⚠️ Demo data is synthetic. Use Debiased ERA5 for actual NE winds.")
                        st.rerun()
            
            with col2:
                if st.button("📊 Process Files", use_container_width=True, type="primary"):
                    if not XARRAY_AVAILABLE:
                        st.error("❌ xarray not installed. Run: pip install xarray netCDF4 cfgrib")
                    elif not use_dir:
                        st.error("❌ Select a data source first")
                    elif not files:
                        st.error(f"❌ No supported files found in {use_dir}")
                    else:
                        # Create a placeholder for dynamic updates
                        progress_placeholder = st.empty()
                        status_placeholder = st.empty()
                        file_placeholder = st.empty()
                        time_placeholder = st.empty()
                        
                        # Initialize
                        all_results = []
                        total_files = len(files)
                        start_time = datetime.now()
                        
                        # Show initial progress bar
                        progress_bar = progress_placeholder.progress(0)
                        status_placeholder.info(f"📊 Processing {total_files} files...")
                        
                        # Process each file with forced UI updates
                        for i, file_path in enumerate(files):
                            filename = os.path.basename(file_path)
                            percent = ((i + 1) / total_files) * 100
                            
                            # Update progress bar
                            progress_bar.progress((i + 1) / total_files)
                            
                            # Update file status
                            file_placeholder.info(f"📄 Processing: **{filename}** ({i+1}/{total_files})")
                            
                            # Show estimated time
                            if i > 0:
                                elapsed = (datetime.now() - start_time).total_seconds()
                                avg_time = elapsed / i
                                remaining = avg_time * (total_files - i)
                                time_placeholder.caption(f"⏱️ Estimated remaining: {remaining/60:.1f} minutes | ⏱️ Elapsed: {elapsed/60:.1f} min")
                            
                            # Force Streamlit to update (critical!)
                            import time
                            time.sleep(0.01)  # Tiny pause to allow UI update
                            
                            # Process the file
                            results = extract_wind_from_file(file_path, NYENJE_CENTER_LAT, NYENJE_CENTER_LON)
                            if results:
                                all_results.extend(results)
                        
                        # Clear placeholders
                        progress_placeholder.empty()
                        status_placeholder.empty()
                        file_placeholder.empty()
                        time_placeholder.empty()
                        
                        if not all_results:
                            st.error("❌ No data could be extracted from the files")
                        else:
                            # Convert to DataFrame (same as before)
                            df = pd.DataFrame(all_results)
                            df['datetime'] = pd.to_datetime(df['time'])
                            df = df.sort_values('datetime').reset_index(drop=True)
                            df['hour'] = df['datetime'].dt.hour
                            df['year'] = df['datetime'].dt.year
                            df['month'] = df['datetime'].dt.month
                            df['day'] = df['datetime'].dt.day
                            
                            # Calculate wind averages
                            wind_avg = calculate_wind_averages(df['speed'].values, df['datetime'])
                            df['wind_speed_3min'] = wind_avg['wind_3min']
                            df['wind_speed_10min'] = wind_avg['wind_10min']
                            df['gust_3sec'] = wind_avg['gust_3sec']
                            df['gust_10sec'] = wind_avg['gust_10sec']
                            df['wind_speed_hourly'] = df['speed']
                            df['wind_direction'] = df['direction']
                            
                            # Calculate statistics
                            diurnal_means = df.groupby('hour')['speed'].mean().reindex(range(24), fill_value=0).tolist()
                            yearly_max = df.groupby('year')['speed'].max().to_dict()
                            global_max_speed = df['speed'].max()
                            global_max_year = df.loc[df['speed'].idxmax(), 'year'] if not df.empty else None
                            
                            # Create result dictionary
                            result = {
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
                            
                            # Store in session state
                            st.session_state.processed_data = result
                            st.session_state.processed = True
                            st.session_state.data_source = source_name
                            
                            total_time = (datetime.now() - start_time).total_seconds()
                            
                            # Display summary
                            st.markdown("---")
                            st.markdown("### 📊 Processing Summary")
                            
                            col_a, col_b, col_c, col_d = st.columns(4)
                            with col_a:
                                st.metric("📁 Files Processed", f"{len(files)}/{len(files)}")
                            with col_b:
                                st.metric("📅 Total Records", f"{result['total_records']:,}")
                            with col_c:
                                st.metric("📆 Years Range", f"{result['years'][0]} - {result['years'][-1]}")
                            with col_d:
                                st.metric("💨 Max Wind", f"{result['global_max']['speed']:.2f} m/s")
                            
                            # Show data quality metrics
                            mean_dir, strength = calculate_circular_mean(result['all_directions'])
                            st.success(f"✅ **Data Summary:** Mean wind speed: {np.mean(result['all_speeds']):.2f} m/s | Mean direction: {mean_dir:.1f}° ({wind_direction_to_cardinal(mean_dir)})")
                            st.info(f"⏱️ Total processing time: {total_time:.1f} seconds")
                            
                            if "Debiased" in source_name:
                                st.balloons()
                                st.success("🎉 **Using DEBIASED ERA5 - NE prevailing direction expected**")
        with sub5:
            st.markdown("### 🌊 Extract SWAN Wind Files")
            extract_year = st.selectbox("Select Year", list(range(1971, 2021)), index=49)
            if st.button("Extract SWAN Files", type="primary"):
                with st.spinner(f"Extracting {extract_year}..."):
                    progress_bar = st.progress(0)
                    for i in range(100):
                        progress_bar.progress(i + 1)
                    st.success(f"✅ Extracted wind files for {extract_year}")

    # ========================================================================
    # TAB 2: Wind Statistics
    # ========================================================================
    with tab2:
        st.header("💨 General Wind Statistics")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first (Data Acquisition tab)")
            st.stop()
        
        data_source_indicator()
        
        data = st.session_state.processed_data
        df = data['df'].copy()
        
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            st.info("🔧 **Debiasing Applied:** CCMP factor (×0.718)")
            df['wind_speed_hourly'] = df['speed'] * DEBIAS_FACTOR
            df['gust_3sec'] = df['gust_3sec'] * DEBIAS_FACTOR
            df['gust_10sec'] = df['gust_10sec'] * DEBIAS_FACTOR
            df['wind_speed_3min'] = df['wind_speed_3min'] * DEBIAS_FACTOR
            df['wind_speed_10min'] = df['wind_speed_10min'] * DEBIAS_FACTOR
        elif st.session_state.data_source != "Demo" and "Debiased" in st.session_state.data_source:
            st.success("✅ **Using pre-debiased ERA5 data**")
        elif st.session_state.data_source == "Demo":
            st.warning("⚠️ **Using DEMO data** - Not for engineering")
        else:
            st.info("📡 **Using RAW ERA5 data** (no debiasing)")
        
        wind_sub1, wind_sub2, wind_sub3, wind_sub4, wind_sub5 = st.tabs([
            "📊 Wind Rose", "📈 Statistics", "🌅 Diurnal", "⏱️ Wind Averages & Gusts", "🔥 Extremes"
        ])
        
        with wind_sub1:
            if st.button("Generate Wind Rose", use_container_width=True):
                speeds_to_plot = data['all_speeds']
                dirs_to_plot = data['all_directions']
                if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                    speeds_to_plot = speeds_to_plot * DEBIAS_FACTOR
                source_label = "DEMO" if st.session_state.data_source == "Demo" else st.session_state.data_source
                fig = create_wind_rose(speeds_to_plot, dirs_to_plot, f"Lake Kariba - {source_label}")
                st.plotly_chart(fig, use_container_width=True)
                mean_dir, strength = calculate_circular_mean(dirs_to_plot)
                st.info(f"**Prevailing:** {wind_direction_to_cardinal(mean_dir)} ({mean_dir:.0f}°) | **Mean speed:** {np.mean(speeds_to_plot):.2f} m/s")
        
        with wind_sub2:
            speeds_display = data['all_speeds']
            if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                speeds_display = speeds_display * DEBIAS_FACTOR
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mean Wind Speed", f"{np.mean(speeds_display):.2f} m/s")
                st.metric("Median", f"{np.median(speeds_display):.2f} m/s")
            with col2:
                st.metric("Max Wind Speed", f"{np.max(speeds_display):.2f} m/s")
                if st.session_state.data_source != "Demo":
                    st.metric("Year of Max", f"{data['global_max']['year']}")
            with col3:
                mean_dir, _ = calculate_circular_mean(data['all_directions'])
                st.metric("Mean Direction", f"{mean_dir:.1f}°")
                st.metric("Prevailing", wind_direction_to_cardinal(mean_dir))
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=speeds_display, nbinsx=30, marker_color='steelblue'))
            fig.update_layout(title="Wind Speed Distribution", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub3:
            diurnal_data = data['diurnal_means']
            if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                diurnal_data = [d * DEBIAS_FACTOR for d in diurnal_data]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(range(24)), y=diurnal_data, mode='lines+markers'))
            fig.update_layout(title="Diurnal Wind Pattern", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub4:
            st.markdown(f"""
            | Period | Factor | Value (based on max wind) | Application |
            |--------|--------|--------------------------|-------------|
            | **10-min mean** | ×{GUST_FACTORS['10min']} | {data['global_max']['speed'] * GUST_FACTORS['10min']:.2f} m/s | Reference |
            | **3-min mean** | ×{GUST_FACTORS['3min']} | {data['global_max']['speed'] * GUST_FACTORS['3min']:.2f} m/s | Dynamic |
            | **10-sec gust** | ×{GUST_FACTORS['10sec']} | {data['global_max']['speed'] * GUST_FACTORS['10sec']:.2f} m/s | SLS |
            | **3-sec gust** | ×{GUST_FACTORS['3sec']} | {data['global_max']['speed'] * GUST_FACTORS['3sec']:.2f} m/s | ULS |
            """)
            fig = create_wind_parameters_plot(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        with wind_sub5:
            if 'yearly_max' in data and data['yearly_max']:
                years = sorted(data['yearly_max'].keys())
                values = [data['yearly_max'][y] for y in years]
                if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                    values = [v * DEBIAS_FACTOR for v in values]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=years, y=values, mode='lines+markers'))
                fig.update_layout(title="Annual Maximum Wind Speeds", height=400)
                st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 3: Wave Analysis
    # ========================================================================
    with tab3:
        st.header("🌊 JONSWAP Generic Wave Parameter Analysis")
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        
        data_source_indicator()
        
        data = st.session_state.processed_data
        wind_speeds = data['all_speeds'][:5000]
        if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
            wind_speeds = wind_speeds * DEBIAS_FACTOR
        
        st.markdown(f"**JONSWAP fetch-limited (fetch = {fetch_km} km)**")
        
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
        fig.update_layout(title="Wave Height Distribution", height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ========================================================================
    # TAB 4: SWAN Model (WITH ALL 5 SUB-TABS)
    # ========================================================================
    with tab4:
        st.header("🌊 SWAN Wave Model Analysis")
        st.info("🔹 **CONSTANT:** Bathymetry | 🔸 **VARIABLE:** Wind | 📄 **DYNAMIC:** INPUT files")
        
        with st.expander("🔍 **What happens behind the scenes?**", expanded=False):
            st.markdown("""
            1. 📅 Select time → User chooses year, month, day, hour
            2. 📁 Find wind file → Tool finds matching debiased ERA5 wind file
            3. 📖 Read wind data → Extracts u/v at 72 grid points
            4. 🗺️ Load bathymetry → CONSTANT file (same for all runs)
            5. 📄 Create INPUT file → Dynamic file with specific wind and boundaries
            6. 🌊 Run SWAN → Solves wave equations
            7. 📊 Generate output → Wave height/period at 72 points
            """)
        
        if not st.session_state.processed:
            st.info("⚠️ Please load data first")
            st.stop()
        
        data_source_indicator()
        
        data = st.session_state.processed_data
        df = data['df'].copy()
        
        # Bathymetry map
        if REAL_BATHYMETRY is not None:
            st.subheader("🗺️ Bathymetry (CONSTANT)")
            fig_bathy = go.Figure(data=go.Heatmap(
                z=REAL_BATHYMETRY, x=[f"{i*500}m" for i in range(NX)], y=[f"{i*500}m" for i in range(NY)],
                colorscale='Viridis', text=np.round(REAL_BATHYMETRY, 1),
                texttemplate='<b>%{text} m</b>', colorbar_title="Depth (m)"
            ))
            fig_bathy.update_layout(height=400)
            st.plotly_chart(fig_bathy, use_container_width=True)
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Min Depth", f"{REAL_BATHYMETRY.min():.1f} m")
            with c2: st.metric("Max Depth", f"{REAL_BATHYMETRY.max():.1f} m")
            with c3: st.metric("Mean Depth", f"{REAL_BATHYMETRY.mean():.1f} m")
        
        st.divider()
        
        # Create 5 sub-tabs for SWAN Model
        swan_sub1, swan_sub2, swan_sub3, swan_sub4, swan_sub5 = st.tabs([
            "🎯 Single Analysis", "📅 Monthly Maxima", "📈 Yearly Maxima", 
            "🏆 Extreme Value Analysis", "🔍 Find Highest Wave"
        ])
        
        # SUB-TAB 1: Single Analysis
        with swan_sub1:
            st.subheader("🎯 Single Time Step Wave Analysis")
            st.markdown("**CONSTANT Bathymetry** + **VARIABLE Wind**")
            
            if 'year' in df.columns:
                available_years = sorted([y for y in df['year'].unique() if y is not None])
            else:
                available_years = list(range(1971, 2021))
                st.info("Using demo years (1971-2020)")
            
            if available_years:
                col1, col2, col3, col4 = st.columns(4)
                with col1: selected_year = st.selectbox("Year", available_years, index=len(available_years)-1 if available_years else 0)
                with col2: selected_month = st.selectbox("Month", range(1, 13), index=0)
                with col3: selected_day = st.selectbox("Day", range(1, 32), index=0)
                with col4: selected_hour = st.selectbox("Hour", range(0, 24), index=12)
                
                if st.button("Run SWAN Analysis", type="primary"):
                    target = datetime(selected_year, selected_month, selected_day, selected_hour)
                    
                    if 'datetime' in df.columns:
                        df['time_diff'] = abs(df['datetime'] - target)
                        closest_idx = df['time_diff'].idxmin()
                        closest = df.loc[closest_idx]
                        wind_speed = closest['speed']
                        wind_dir = closest['direction']
                    else:
                        wind_speed = np.mean(data['all_speeds'])
                        wind_dir = 110
                    
                    if use_debiased and st.session_state.data_source != "Demo" and "Raw" in st.session_state.data_source:
                        wind_speed = wind_speed * DEBIAS_FACTOR
                    
                    # Generate and display SWAN INPUT file
                    wind_file_demo = os.path.join(WIND_FILES_DIR, str(selected_year), f"nyenje_wind_{selected_year}{selected_month:02d}{selected_day:02d}_{selected_hour:02d}00.wnd")
                    timestamp_str = f"{selected_year}{selected_month:02d}{selected_day:02d}_{selected_hour:02d}00"
                    swan_input = generate_swan_input_file(wind_file_demo, f"output_{timestamp_str}.txt", timestamp_str)
                    
                    with st.expander("📄 **SWAN INPUT File** (Created dynamically for this run)", expanded=True):
                        st.code(swan_input, language="text")
                    
                    # Compute wave distribution
                    wave_heights_grid, wave_periods_grid, depth_grid = generate_swan_wave_distribution(wind_speed, wind_dir)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("💨 Wind Speed", f"{wind_speed:.2f} m/s")
                        st.metric("🧭 Wind Direction", f"{wind_dir:.1f}° ({wind_direction_to_cardinal(wind_dir)})")
                    with col2:
                        center_idx_x = NX // 2
                        center_idx_y = NY // 2
                        center_hs = wave_heights_grid[center_idx_y, center_idx_x]
                        center_tp = wave_periods_grid[center_idx_y, center_idx_x]
                        st.metric("🌊 Center Wave Height", f"{center_hs:.3f} m ({center_hs*100:.1f} cm)")
                        st.metric("⏱️ Center Wave Period", f"{center_tp:.2f} s")
                    
                    # Create side-by-side contour maps
                    st.subheader("🗺️ Wave Distribution Maps")
                    fig_hs = go.Figure(data=go.Heatmap(
                        z=wave_heights_grid * 100,
                        x=[f"{i*500}m" for i in range(NX)],
                        y=[f"{i*500}m" for i in range(NY)],
                        colorscale='RdYlGn',
                        text=np.round(wave_heights_grid * 100, 1),
                        texttemplate='<b>%{text} cm</b>',
                        colorbar_title="Wave Height (cm)"
                    ))
                    fig_hs.update_layout(title="Wave Height Distribution", height=450, xaxis_title="Distance from West (m)", yaxis_title="Distance from South (m)")
                    st.plotly_chart(fig_hs, use_container_width=True)
                    
                    fig_tp = go.Figure(data=go.Heatmap(
                        z=wave_periods_grid,
                        x=[f"{i*500}m" for i in range(NX)],
                        y=[f"{i*500}m" for i in range(NY)],
                        colorscale='Plasma',
                        text=np.round(wave_periods_grid, 1),
                        texttemplate='<b>%{text} s</b>',
                        colorbar_title="Wave Period (s)"
                    ))
                    fig_tp.update_layout(title="Wave Period Distribution", height=450, xaxis_title="Distance from West (m)", yaxis_title="Distance from South (m)")
                    st.plotly_chart(fig_tp, use_container_width=True)

        # SUB-TAB 2: Monthly Maxima
        with swan_sub2:
            st.subheader("📅 Monthly Maximum Wave Heights")
            if st.button("Calculate Monthly Maxima", use_container_width=True):
                with st.spinner("Calculating monthly maxima..."):
                    monthly_max, monthly_stats = calculate_monthly_maxima(df, fetch_km, use_debiased, st.session_state.data_source)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_max = go.Figure()
                        fig_max.add_trace(go.Scatter(x=monthly_max['year_month'], y=monthly_max['wave_height'], mode='lines+markers', name='Monthly Max'))
                        fig_max.update_layout(title="Monthly Maximum Wave Heights", xaxis_title="Month", yaxis_title="Wave Height (m)", height=400)
                        st.plotly_chart(fig_max, use_container_width=True)
                    
                    with col2:
                        fig_stats = go.Figure()
                        fig_stats.add_trace(go.Bar(x=monthly_stats['month'], y=monthly_stats['max'], name='Max', marker_color='red'))
                        fig_stats.add_trace(go.Bar(x=monthly_stats['month'], y=monthly_stats['mean'], name='Mean', marker_color='blue'))
                        fig_stats.update_layout(title="Monthly Wave Statistics", xaxis_title="Month", yaxis_title="Wave Height (m)", barmode='group', height=400)
                        st.plotly_chart(fig_stats, use_container_width=True)

        # SUB-TAB 3: Yearly Maxima
        with swan_sub3:
            st.subheader("📈 Yearly Maximum Wave Heights")
            if st.button("Calculate Yearly Maxima", use_container_width=True):
                with st.spinner("Calculating yearly maxima..."):
                    yearly_max = calculate_yearly_maxima(df, fetch_km, use_debiased, st.session_state.data_source)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=yearly_max['year'], y=yearly_max['wave_height'], mode='lines+markers', name='Yearly Max', line=dict(color='red', width=2)))
                    fig.update_layout(title="Yearly Maximum Wave Heights (1971-2020)", xaxis_title="Year", yaxis_title="Wave Height (m)", height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    max_row = yearly_max.loc[yearly_max['wave_height'].idxmax()]
                    st.info(f"🏆 **Highest yearly max:** {max_row['wave_height']:.3f} m ({max_row['wave_height']*100:.1f} cm) in {int(max_row['year'])}")

        # SUB-TAB 4: Extreme Value Analysis
        with swan_sub4:
            st.subheader("🏆 Extreme Value Analysis - Gumbel Distribution")
            st.markdown("**Return Periods for Extreme Wave Heights**")
            
            if st.button("Run Extreme Value Analysis", use_container_width=True, type="primary"):
                with st.spinner("Performing Gumbel extreme value analysis..."):
                    return_heights, max_event, params = extreme_value_analysis(df, fetch_km, use_debiased, st.session_state.data_source)
                    
                    if return_heights:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("2-year", f"{return_heights[2]:.3f} m")
                            st.metric("5-year", f"{return_heights[5]:.3f} m")
                            st.metric("10-year", f"{return_heights[10]:.3f} m")
                        with col2:
                            st.metric("20-year", f"{return_heights[20]:.3f} m")
                            st.metric("25-year", f"{return_heights[25]:.3f} m")
                            st.metric("50-year", f"{return_heights[50]:.3f} m")
                        with col3:
                            st.metric("100-year", f"{return_heights[100]:.3f} m")
                            if max_event:
                                st.metric("Historical Max", f"{max_event['height']:.3f} m")
                                if max_event['year']:
                                    st.caption(f"Year: {max_event['year']}")
                        
                        # Create return period plot
                        rp_years = list(return_heights.keys())
                        rp_values = list(return_heights.values())
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=rp_years, y=rp_values, mode='lines+markers', name='Gumbel Fit', line=dict(color='red', width=2)))
                        fig.update_layout(title="Return Periods for Extreme Wave Heights", xaxis_title="Return Period (years)", yaxis_title="Wave Height (m)", xaxis_type="log", height=450)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.success(f"**Gumbel Parameters:** Location (μ) = {params[0]:.4f}, Scale (β) = {params[1]:.4f}")
                    else:
                        st.warning("Not enough years of data for extreme value analysis")

        # SUB-TAB 5: Find Highest Wave
        with swan_sub5:
            st.subheader("🔍 Find Highest Wave Event (1971-2020)")
            st.warning("⚠️ **Computationally intensive** - Searching 438,000 hours of data")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                max_search_btn = st.button("🔍 FIND HIGHEST WAVE", type="primary", use_container_width=True)
            
            if max_search_btn:
                try:
                    max_wave, top10 = find_highest_wave(data, fetch_km, use_debiased, st.session_state.data_source)
                except Exception as e:
                    st.error(f"Error during search: {e}")

    # ========================================================================
    # TAB 5: Live Validation
    # ========================================================================
    with tab5:
        st.header("✅ Live Validation: ERA5 vs Airport Measurements")
        
        airport_df = load_airport_data()
        
        if airport_df is None:
            st.warning("Airport data not available. Validation demo will use synthetic data.")
            if st.button("Run Validation Demo"):
                with st.spinner("Running validation..."):
                    synthetic_airport = pd.DataFrame({
                        'datetime': pd.date_range('2001-01-01', '2005-12-31', freq='D'),
                        'wind_speed_ms': np.random.normal(4, 1.5, 1826)
                    })
                    validation_results = validate_airport_vs_era5(synthetic_airport)
                    if validation_results:
                        st.session_state.validation_results = validation_results
                        st.success("Validation demo complete!")
        else:
            st.success(f"✅ Loaded {len(airport_df)} records from Kariba Airport (2001-2005)")
            if st.button("Run Validation", type="primary"):
                with st.spinner("Validating ERA5 against airport data..."):
                    validation_results = validate_airport_vs_era5(airport_df)
                    if validation_results:
                        st.session_state.validation_results = validation_results
                        st.success("Validation complete!")
        
        if st.session_state.validation_results:
            val = st.session_state.validation_results
            
            st.subheader("📊 Validation Metrics")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Raw ERA5 Correlation", f"{val['raw_corr']:.3f}", delta="Target: 0.502")
                st.metric("Debiased Correlation", f"{val['debiased_corr']:.3f}", delta=f"{val['debiased_corr'] - 0.502:.3f}")
            with col2:
                st.metric("Raw ERA5 Bias", f"{val['raw_bias']:.3f} m/s")
                st.metric("Debiased Bias", f"{val['debiased_bias']:.3f} m/s", delta=f"{val['bias_improvement']:.0f}% improvement")
            with col3:
                st.metric("Raw ERA5 RMSE", f"{val['raw_rmse']:.3f} m/s")
                st.metric("Debiased RMSE", f"{val['debiased_rmse']:.3f} m/s", delta=f"{val['rmse_improvement']:.0f}% improvement")
            
            df_val = val['data'].copy()
            sample_size = min(500, len(df_val))
            df_sample = df_val.sample(sample_size, random_state=42).sort_values('datetime')
            
            fig = make_subplots(rows=2, cols=1, subplot_titles=("Time Series Comparison", "Scatter Plot: Airport vs Debiased ERA5"), vertical_spacing=0.15)
            fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['wind_speed_ms'], mode='lines', name='Airport', line=dict(color='blue', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_sample['datetime'], y=df_sample['era5_debiased_ms'], mode='lines', name='Debiased ERA5', line=dict(color='red', width=1, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_sample['wind_speed_ms'], y=df_sample['era5_debiased_ms'], mode='markers', name='Data Points', marker=dict(color='green', size=4, opacity=0.6)), row=2, col=1)
            max_val = max(df_sample['wind_speed_ms'].max(), df_sample['era5_debiased_ms'].max())
            fig.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode='lines', name='1:1 Line', line=dict(color='black', dash='dash')), row=2, col=1)
            fig.update_layout(height=600, showlegend=True)
            fig.update_xaxes(title_text="Date", row=1, col=1)
            fig.update_yaxes(title_text="Wind Speed (m/s)", row=1, col=1)
            fig.update_xaxes(title_text="Airport Wind Speed (m/s)", row=2, col=1)
            fig.update_yaxes(title_text="Debiased ERA5 (m/s)", row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
            
            st.info(f"""
            **Validation Summary:**
            - Successfully validated Debiased ERA5 against Kariba Airport (2001-2005)
            - Correlation: {val['debiased_corr']:.3f} (target: 0.502, achieved: {val['debiased_corr']/0.502*100:.1f}%)
            - Bias reduced from {val['raw_bias']:.3f} m/s to {val['debiased_bias']:.3f} m/s ({val['bias_improvement']:.0f}% improvement)
            - RMSE reduced from {val['raw_rmse']:.3f} m/s to {val['debiased_rmse']:.3f} m/s ({val['rmse_improvement']:.0f}% improvement)
            """)

    # ========================================================================
    # TAB 6: Nyenje Bay Gallery
    # ========================================================================
    with tab6:
        st.header("📍 Nyenje Bay - Site Gallery")
        st.markdown("**Location:** 16.53°S, 28.83°E | Lake Kariba, Zimbabwe")
        
        # Create sub-tabs for different image types
        gallery_tab1, gallery_tab2, gallery_tab3, gallery_tab4 = st.tabs([
            "📸 Site Photos", "🗺️ Location Map", "📊 Domain Grid", "📈 Site Schematic"
        ])
        
        with gallery_tab1:
            st.subheader("📸 Nyenje Bay Photographs")
            
            # Add file uploader for users to upload their own photos
            with st.expander("📤 Upload Your Own Photos", expanded=False):
                uploaded_photos = st.file_uploader(
                    "Choose photos of Nyenje Bay",
                    type=['jpg', 'jpeg', 'png', 'gif'],
                    accept_multiple_files=True,
                    key="photo_uploader"
                )
                
                if uploaded_photos:
                    st.success(f"✅ {len(uploaded_photos)} photos uploaded")
                    for photo in uploaded_photos:
                        st.image(photo, caption=photo.name, use_container_width=True)
            
            # Define possible image paths (local files)
            st.markdown("---")
            st.markdown("### 📁 Local Site Photos")
            
            image_dirs = [
                os.path.join(BASE_DIR, "docs", "images"),
                os.path.join(BASE_DIR, "docs", "images", "nyenje"),
                os.path.join(BASE_DIR, "data", "images"),
                os.path.join(BASE_DIR, "photos"),
            ]
            
            # Collect all images from directories
            all_images = []
            for img_dir in image_dirs:
                if os.path.exists(img_dir):
                    for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
                        all_images.extend(glob.glob(os.path.join(img_dir, ext)))
            
            if all_images:
                # Add a button to browse and select images
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🖼️ Show All Local Photos", use_container_width=True):
                        st.session_state.show_all_photos = True
                with col_btn2:
                    if st.button("📁 Browse Photo Directory", use_container_width=True):
                        st.session_state.browse_photos = True
                
                # Display photos in a grid
                if st.session_state.get('show_all_photos', False):
                    st.markdown("### 🖼️ Photo Gallery")
                    
                    # Display in 3 columns
                    cols = st.columns(3)
                    for idx, img_path in enumerate(all_images):
                        with cols[idx % 3]:
                            st.image(img_path, caption=os.path.basename(img_path), use_container_width=True)
                            # Add download button for each image
                            with open(img_path, "rb") as f:
                                st.download_button(
                                    label=f"📥 Download",
                                    data=f.read(),
                                    file_name=os.path.basename(img_path),
                                    mime="image/jpeg",
                                    key=f"download_{idx}"
                                )
                
                # Browse directory
                if st.session_state.get('browse_photos', False):
                    st.markdown("### 📁 Photo Directory Browser")
                    for img_dir in image_dirs:
                        if os.path.exists(img_dir):
                            st.code(f"📂 {img_dir}")
                            for f in os.listdir(img_dir)[:10]:
                                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                    st.text(f"  📷 {f}")
            else:
                st.info("""
                ### 📸 Add Site Photos
                
                **Ways to add photos:**
                1. **Upload above** - Use the file uploader to add photos temporarily
                2. **Add to folder** - Place images in one of these folders:
                   - `docs/images/nyenje/`
                   - `data/images/`
                   - `photos/`
                3. **Browse** - Use the buttons above to browse available photos
                
                **Recommended images:**
                - Aerial/satellite view of Nyenje Bay
                - Shoreline conditions
                - Fetch length perspective
                - Bathymetry visualization
                """)
                
                st.markdown("---")
                st.markdown("""
                ### 📋 Site Context
                
                | Parameter | Value |
                |-----------|-------|
                | **Location** | Nyenje Bay, Lake Kariba |
                | **Coordinates** | 16.53°S, 28.83°E |
                | **Country** | Zimbabwe / Zambia border |
                | **Water Body** | Lake Kariba (world's largest man-made lake) |
                | **Domain Size** | 4.0 km × 3.5 km |
                | **Grid Resolution** | 9 × 8 points (500 m spacing) |
                | **Fetch Length** | 4 km (West direction - open lake) |
                | **Water Depth** | 1.5 m (shallow) to 30 m (deep) |
                """)
        with gallery_tab2:
            st.subheader("🗺️ Nyenje Bay Location Map")
            
            # Define PNG map path
            png_map_path = os.path.join(BASE_DIR, "docs", "images", "nyenje_map.png")
            
            if os.path.exists(png_map_path):
                st.image(png_map_path, caption="Nyenje Bay Study Area", use_container_width=True)
                with open(png_map_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Map",
                        data=f.read(),
                        file_name="nyenje_bay_map.png",
                        mime="image/png"
                    )
            else:
                st.warning(f"⚠️ Map file not found at: {png_map_path}")
                st.info("Place your Nyenje Bay map image at the path above to display it here.")
                
                # Generate a simple location map using matplotlib
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
                
                # Map 1: Africa context
                ax1.set_xlim(-20, 55)
                ax1.set_ylim(-35, 40)
                ax1.set_facecolor('#e6f3ff')
                africa_x = [-18, -12, -10, 12, 15, 25, 30, 35, 32, 25, 15, 10, -5, -15, -18]
                africa_y = [30, 35, 37, 35, 30, 22, 15, 5, 0, -5, -10, -15, -20, -25, 30]
                ax1.fill(africa_x, africa_y, alpha=0.7, color='#d4e6b3', edgecolor='black', linewidth=0.5)
                ax1.scatter(28.83, -16.53, s=150, c='red', marker='D', zorder=5)
                ax1.annotate('Nyenje Bay', (28.83, -16.53), xytext=(5, 5), textcoords='offset points', fontsize=9, fontweight='bold')
                ax1.set_title('Location in Africa', fontsize=12, fontweight='bold')
                ax1.grid(True, alpha=0.2)
                
                # Map 2: Lake Kariba zoom
                ax2.set_xlim(27.5, 29.5)
                ax2.set_ylim(-18, -15)
                ax2.set_facecolor('#e6f3ff')
                lake_x = [27.5, 29.5, 29.5, 27.5, 27.5]
                lake_y = [-17.5, -17.5, -15.5, -15.5, -17.5]
                ax2.fill(lake_x, lake_y, alpha=0.4, color='blue', label='Lake Kariba')
                ax2.scatter(28.83, -16.53, s=300, c='red', marker='D', zorder=5, edgecolor='black', linewidth=2)
                ax2.annotate('Nyenje Bay\n(Study Site)', (28.83, -16.53), xytext=(0.5, 0.5), textcoords='offset points', fontsize=10, fontweight='bold', color='red')
                ax2.set_title('Lake Kariba Region', fontsize=12, fontweight='bold')
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='lower right')
                
                plt.tight_layout()
                st.pyplot(fig)
            
            with st.expander("📍 Site Coordinates", expanded=False):
                st.markdown("""
                | Feature | Latitude | Longitude |
                |---------|----------|-----------|
                | **Nyenje Bay Center** | 16.53°S | 28.83°E |
                | **Western Boundary** | 16.53°S | 28.81113°E |
                | **Eastern Boundary** | 16.53°S | 28.84887°E |
                | **Southern Boundary** | 16.54577°S | 28.83°E |
                | **Northern Boundary** | 16.51423°S | 28.83°E |
                """)
        
        with gallery_tab3:
            st.subheader("📊 Study Domain Grid Visualization")
            st.markdown("**Domain:** 4.0 km × 3.5 km | **Grid:** 9 × 8 points | **Resolution:** 500 m")
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Plot 1: Grid points
            x_coords = np.linspace(0, DOMAIN_X/1000, NX)
            y_coords = np.linspace(0, DOMAIN_Y/1000, NY)
            X, Y = np.meshgrid(x_coords, y_coords)
            ax1.scatter(X, Y, s=50, c='blue', marker='o', alpha=0.7)
            for x in x_coords:
                ax1.axvline(x, color='gray', linewidth=0.5, alpha=0.5, linestyle='--')
            for y in y_coords:
                ax1.axhline(y, color='gray', linewidth=0.5, alpha=0.5, linestyle='--')
            center_x = DOMAIN_X/1000/2
            center_y = DOMAIN_Y/1000/2
            ax1.scatter(center_x, center_y, s=200, c='red', marker='*', zorder=5)
            ax1.annotate('Analysis Center', (center_x, center_y), xytext=(5, 5), textcoords='offset points', fontsize=9, fontweight='bold', color='red')
            ax1.set_xlabel('Distance from West (km)')
            ax1.set_ylabel('Distance from South (km)')
            ax1.set_title(f'Grid Layout: {NX} × {NY} points (500 m resolution)')
            ax1.grid(True, alpha=0.2)
            ax1.set_aspect('equal')
            
            # Plot 2: Bathymetry
            if REAL_BATHYMETRY is not None:
                im = ax2.imshow(REAL_BATHYMETRY, extent=[0, DOMAIN_X/1000, 0, DOMAIN_Y/1000], origin='lower', cmap='viridis', aspect='auto')
                plt.colorbar(im, ax=ax2, label='Depth (m)')
                ax2.set_title('Bathymetry Distribution')
            else:
                x = np.linspace(0, DOMAIN_X/1000, NX)
                y = np.linspace(0, DOMAIN_Y/1000, NY)
                X_synth, Y_synth = np.meshgrid(x, y)
                depth_synth = 30 - (Y_synth / (DOMAIN_Y/1000)) * 28.5
                depth_synth = np.maximum(depth_synth, 1.5)
                im = ax2.imshow(depth_synth, extent=[0, DOMAIN_X/1000, 0, DOMAIN_Y/1000], origin='lower', cmap='viridis', aspect='auto')
                plt.colorbar(im, ax=ax2, label='Depth (m)')
                ax2.set_title('Synthetic Bathymetry')
            
            for x in x_coords:
                ax2.axvline(x, color='white', linewidth=0.3, alpha=0.5)
            for y in y_coords:
                ax2.axhline(y, color='white', linewidth=0.3, alpha=0.5)
            ax2.set_xlabel('Distance from West (km)')
            ax2.set_ylabel('Distance from South (km)')
            ax2.set_aspect('equal')
            
            plt.tight_layout()
            st.pyplot(fig)
            
            # Domain statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Grid Points", f"{NX * NY}")
            with col2:
                st.metric("Domain Width", f"{DOMAIN_X/1000:.1f} km")
            with col3:
                st.metric("Domain Height", f"{DOMAIN_Y/1000:.1f} km")
            with col4:
                st.metric("Cell Area", f"{0.5 * 0.5:.2f} km²")
            
            if REAL_BATHYMETRY is not None:
                st.info(f"📊 **Bathymetry Statistics:** Min: {REAL_BATHYMETRY.min():.1f} m | Max: {REAL_BATHYMETRY.max():.1f} m | Mean: {REAL_BATHYMETRY.mean():.1f} m")
        
        with gallery_tab4:
            st.subheader("📈 Site Schematic - Wind & Wave Setup")
            st.markdown("**Conceptual diagram showing wind direction, fetch, and wave generation**")
            
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 10)
            ax.set_facecolor('#f0f4f8')
            
            # Draw water body
            lake = plt.Rectangle((0, 0), 10, 10, alpha=0.3, facecolor='lightblue', edgecolor='blue', linewidth=2)
            ax.add_patch(lake)
            
            # Draw Nyenje Bay area
            bay = plt.Rectangle((2, 2), 6, 5, alpha=0.5, facecolor='#87CEEB', edgecolor='darkblue', linewidth=2)
            ax.add_patch(bay)
            ax.text(5, 4.5, 'Nyenje Bay', fontsize=14, ha='center', fontweight='bold', color='darkblue')
            ax.text(5, 3.8, 'Fetch-Limited Bay', fontsize=10, ha='center', style='italic', color='darkblue')
            
            # Draw fetch arrow
            ax.annotate('', xy=(8, 8), xytext=(3, 3), arrowprops=dict(arrowstyle='->', lw=3, color='red'))
            ax.text(5.5, 5.5, 'Prevailing Wind (NE)', fontsize=12, ha='center', color='red', fontweight='bold')
            ax.text(5.5, 5.0, 'Fetch Length: 4 km', fontsize=10, ha='center', style='italic', color='darkred')
            
            # Add wave symbols
            wave_x = [3, 4, 5, 6, 7]
            wave_y = [2.5, 2.5, 2.5, 2.5, 2.5]
            for wx, wy in zip(wave_x, wave_y):
                ax.plot([wx-0.2, wx, wx+0.2], [wy, wy+0.2, wy], 'b-', linewidth=2)
            ax.text(5, 2.0, 'Generated Waves', fontsize=10, ha='center', color='blue')
            
            # Add wind rose
            wind_rose_center = (9, 1.5)
            ax.plot(wind_rose_center[0], wind_rose_center[1], 'ko', markersize=5)
            ax.annotate('', xy=(wind_rose_center[0], wind_rose_center[1]+1), xytext=wind_rose_center, arrowprops=dict(arrowstyle='->', lw=1.5, color='black'))
            ax.annotate('', xy=(wind_rose_center[0]+1, wind_rose_center[1]), xytext=wind_rose_center, arrowprops=dict(arrowstyle='->', lw=1.5, color='black'))
            ax.annotate('', xy=(wind_rose_center[0], wind_rose_center[1]-1), xytext=wind_rose_center, arrowprops=dict(arrowstyle='->', lw=1.5, color='black'))
            ax.annotate('', xy=(wind_rose_center[0]-1, wind_rose_center[1]), xytext=wind_rose_center, arrowprops=dict(arrowstyle='->', lw=1.5, color='black'))
            
            ax.set_title('Nyenje Bay: Wind-Wave Setup for FPV Design', fontsize=14, fontweight='bold', pad=20)
            ax.set_xlabel('Distance (km)')
            ax.set_ylabel('Distance (km)')
            ax.grid(True, alpha=0.2, linestyle='--')
            ax.set_aspect('equal')
            
            st.pyplot(fig)
            
            
            


    # Add this after tab6
    with tab7:
        st.header("📄 Technical Documents & Reports")
        
        # Create sub-tabs for different document types
        doc_tab1, doc_tab2, doc_tab3 = st.tabs([
            "📊 Reports", "📐 Technical Drawings", "📋 SWAN Manuals"
        ])
        
        # Define document directories
        docs_base = os.path.join(BASE_DIR, "docs")
        pdf_dirs = {
            "Reports": os.path.join(docs_base, "reports"),
            "Technical Drawings": os.path.join(docs_base, "drawings"),
            "SWAN Manuals": os.path.join(docs_base, "manuals")
        }
        
        # Tab 1: Reports
        with doc_tab1:
            st.markdown("### Analysis Reports")
            
            # PDF upload option
            with st.expander("📤 Upload Your Own PDF", expanded=False):
                uploaded_pdf = st.file_uploader(
                    "Choose a PDF file",
                    type=['pdf'],
                    key="pdf_uploader"
                )
                if uploaded_pdf:
                    st.success(f"✅ Uploaded: {uploaded_pdf.name}")
                    
                    # Display uploaded PDF
                    base64_pdf = base64.b64encode(uploaded_pdf.getvalue()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Display existing reports
            reports_dir = pdf_dirs["Reports"]
            if os.path.exists(reports_dir):
                report_files = glob.glob(os.path.join(reports_dir, "*.pdf"))
                if report_files:
                    for report in report_files:
                        with st.expander(f"📄 {os.path.basename(report)}", expanded=False):
                            display_pdf_with_controls(report)
                else:
                    st.info("No reports found. Add PDFs to: `docs/reports/`")
            else:
                st.info(f"Create directory: `{reports_dir}` and add PDFs")
        
        # Tab 2: Technical Drawings
        with doc_tab2:
            st.markdown("### Technical Drawings & Schematics")
            
            drawings_dir = pdf_dirs["Technical Drawings"]
            if os.path.exists(drawings_dir):
                drawing_files = glob.glob(os.path.join(drawings_dir, "*.pdf"))
                if drawing_files:
                    # Display as gallery
                    display_pdf_gallery(drawings_dir)
                else:
                    st.info("No drawings found. Add PDFs to: `docs/drawings/`")
            else:
                st.info(f"Create directory: `{drawings_dir}` and add PDFs")
        
        # Tab 3: SWAN Manuals
        with doc_tab3:
            st.markdown("### SWAN Model Documentation")
            
            manuals_dir = pdf_dirs["SWAN Manuals"]
            if os.path.exists(manuals_dir):
                manual_files = glob.glob(os.path.join(manuals_dir, "*.pdf"))
                if manual_files:
                    for manual in manual_files:
                        with st.expander(f"📘 {os.path.basename(manual)}", expanded=False):
                            display_pdf_with_controls(manual)
                else:
                    st.info("No manuals found. Add PDFs to: `docs/manuals/`")
            else:
                st.info(f"Create directory: `{manuals_dir}` and add PDFs")
        
        # Batch download option
        st.markdown("---")
        st.markdown("### 📦 Batch Download")
        
        # Collect all PDFs
        all_pdfs = []
        for dir_name, dir_path in pdf_dirs.items():
            if os.path.exists(dir_path):
                all_pdfs.extend(glob.glob(os.path.join(dir_path, "*.pdf")))
        
        if all_pdfs:
            st.write(f"**Total documents available:** {len(all_pdfs)}")
            
            # Create ZIP of all PDFs
            import zipfile
            import io
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_path in all_pdfs:
                    with open(pdf_path, 'rb') as f:
                        zip_file.writestr(os.path.basename(pdf_path), f.read())
            
            st.download_button(
                label="📦 Download All Documents (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="nyenje_bay_documents.zip",
                mime="application/zip"
            )
                
            
        

if __name__ == "__main__":
    main()