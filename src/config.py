#!/usr/bin/env python3
"""
Configuration file for Nyenje Bay ERA5-SWAN Tool
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent.resolve()

# Data directories
DATA_DIR = BASE_DIR / "data"
ERA5_RAW_DIR = DATA_DIR / "era5" / "raw"
ERA5_DEBIASED_DIR = DATA_DIR / "era5" / "debiased"
CCMP_DIR = DATA_DIR / "ccmp"
BATHYMETRY_DIR = DATA_DIR / "bathymetry"
WIND_FILES_DIR = DATA_DIR / "wind_files"

# SWAN directories
SWAN_DIR = BASE_DIR / "swan"
SWAN_BIN_DIR = SWAN_DIR / "bin"
SWAN_INPUTS_DIR = SWAN_DIR / "inputs" / "swan_input_files"
SWAN_OUTPUTS_DIR = SWAN_DIR / "outputs" / "swan_era5_debiased_outputs"
SWAN_ARCHIVE_DIR = SWAN_DIR / "archive" / "swan_wind_archive"

# Output directories
OUTPUTS_DIR = BASE_DIR / "outputs"
WIND_ANALYSES_DIR = OUTPUTS_DIR / "wind_analyses"
WAVE_ANALYSES_DIR = OUTPUTS_DIR / "wave_analyses"
EXTREME_ANALYSIS_DIR = OUTPUTS_DIR / "extreme_analysis"
FIGURES_DIR = OUTPUTS_DIR / "figures"

# Documentation
DOCS_DIR = BASE_DIR / "docs"
IMAGES_DIR = DOCS_DIR / "images"

# Logs
LOGS_DIR = BASE_DIR / "logs"
SWAN_LOGS_DIR = LOGS_DIR / "swan_runs"

# SWAN configuration
SWAN_EXE = SWAN_BIN_DIR / "swan.exe"
BATHYMETRY_FILE = BATHYMETRY_DIR / "nyenje_bathymetry_9x8.bot"

# Create all directories
for dir_path in [
    ERA5_RAW_DIR, ERA5_DEBIASED_DIR, CCMP_DIR, BATHYMETRY_DIR, WIND_FILES_DIR,
    SWAN_BIN_DIR, SWAN_INPUTS_DIR, SWAN_OUTPUTS_DIR, SWAN_ARCHIVE_DIR,
    WIND_ANALYSES_DIR, WAVE_ANALYSES_DIR, EXTREME_ANALYSIS_DIR, FIGURES_DIR,
    DOCS_DIR, IMAGES_DIR, LOGS_DIR, SWAN_LOGS_DIR
]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Model parameters
NX = 9
NY = 8
DOMAIN_X = 4000.0
DOMAIN_Y = 3500.0
CENTER_LAT = -16.53
CENTER_LON = 28.83
DEBIAS_FACTOR = 0.718

print("Configuration loaded successfully")
