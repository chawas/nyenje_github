#!/usr/bin/env python3
"""
Nyenje Bay ERA5 Climate Analysis Tool
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Page config
st.set_page_config(
    page_title="Nyenje Bay Climate Tool",
    page_icon="🌊",
    layout="wide"
)

# Title
st.title("🌊 Nyenje Bay Climate Analysis Tool")
st.markdown("### Lake Kariba | Wind, Wave & SWAN Modeling")

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
    **Location:** Nyenje Bay, Lake Kariba  
    **Domain:** 4 km × 3.5 km  
    **Resolution:** 500 m (9×8 grid)  
    """)
    
    st.header("Settings")
    fetch_km = st.slider("Fetch Length (km)", 1, 50, 4)

# Demo data
@st.cache_data
def load_demo_data():
    np.random.seed(42)
    dates = pd.date_range(start='1971-01-01', end='2020-12-31', freq='D')
    wind_speeds = np.random.gamma(2, 1.5, len(dates))
    return dates, wind_speeds

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Wind Analysis", "🌊 Wave Analysis", "ℹ️ About"])

with tab1:
    st.header("Wind Analysis")
    
    if st.button("Load Demo Data"):
        with st.spinner("Loading..."):
            dates, wind_speeds = load_demo_data()
            st.session_state['dates'] = dates
            st.session_state['wind_speeds'] = wind_speeds
        st.success("Demo data loaded!")
    
    if 'wind_speeds' in st.session_state:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Mean Wind Speed", f"{np.mean(st.session_state['wind_speeds']):.2f} m/s")
        with col2:
            st.metric("Max Wind Speed", f"{np.max(st.session_state['wind_speeds']):.2f} m/s")
        with col3:
            st.metric("Data Points", f"{len(st.session_state['wind_speeds']):,}")
        
        # Time series plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=st.session_state['dates'], y=st.session_state['wind_speeds'], 
                                  mode='lines', name='Wind Speed'))
        fig.update_layout(title="Wind Speed Time Series", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Wave Analysis")
    st.info("JONSWAP fetch-limited wave prediction")
    
    if 'wind_speeds' in st.session_state:
        # Calculate wave heights
        g = 9.81
        wind_speeds = st.session_state['wind_speeds']
        fetch_m = fetch_km * 1000
        x_tilde = g * fetch_m / (wind_speeds**2 + 0.1)
        wave_heights = 0.0016 * (wind_speeds**2 / g) * np.sqrt(x_tilde)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Mean Wave Height", f"{np.mean(wave_heights):.3f} m")
        with col2:
            st.metric("Max Wave Height", f"{np.max(wave_heights):.3f} m")
        
        # Histogram
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=wave_heights, nbinsx=30, marker_color='blue'))
        fig.update_layout(title="Wave Height Distribution", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("About This Tool")
    st.markdown("""
    ### Nyenje Bay Climate Analysis Tool
    
    This tool provides wind and wave analysis for Nyenje Bay (Gache-Gache Bay), 
    Lake Kariba, supporting floating solar infrastructure design.
    
    **Features:**
    - Wind speed analysis and visualization
    - JONSWAP fetch-limited wave predictions
    - Integration with SWAN wave model
    
    **Data Sources:**
    - ERA5 reanalysis (debiased using CCMP)
    - Local bathymetry from GEBCO
    
    **Contact:** Key Informatics (Pvt) Ltd
    """)

print("App ready")
