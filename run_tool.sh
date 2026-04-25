#!/bin/bash

# Nyenje Bay Climate Analysis Tool Launcher
# Automatically finds available port and launches Streamlit

echo "============================================================"
echo "🌊 Nyenje Bay Climate Analysis Tool - Lake Kariba"
echo "============================================================"
echo ""

# Function to find an available port
find_available_port() {
    local port=8501
    while lsof -i:$port >/dev/null 2>&1; do
        port=$((port + 1))
    done
    echo $port
}

# Find an available port
PORT=$(find_available_port)
echo "🔍 Found available port: $PORT"
echo ""

# Set paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="$SCRIPT_DIR/src/era5_analysis.py"

# Check if app exists
if [ ! -f "$APP_PATH" ]; then
    echo "❌ Error: Could not find $APP_PATH"
    echo "   Please ensure src/era5_analysis.py exists"
    exit 1
fi

echo "📁 Found app at: $APP_PATH"
echo ""

# Source conda and activate environment (optional, use if conda is available)
if [ -f "/home/chawas/anaconda3/etc/profile.d/conda.sh" ]; then
    echo "📌 Activating conda environment..."
    source /home/chawas/anaconda3/etc/profile.d/conda.sh
    conda activate deploy_env 2>/dev/null
    echo "✅ Environment ready"
fi
echo ""

# Verify streamlit
if ! command -v streamlit &> /dev/null; then
    echo "⚠️  Streamlit not found. Installing..."
    pip install streamlit pandas numpy plotly scipy -q
    echo "✅ Streamlit installed"
fi

echo "🚀 Starting Streamlit server on port $PORT..."
echo "📊 The app will open in your browser at http://localhost:$PORT"
echo "⌨️  Press Ctrl+C to stop the server"
echo ""

# Open browser after a short delay
(
    sleep 3
    URL="http://localhost:$PORT"
    if command -v xdg-open &> /dev/null; then
        xdg-open $URL 2>/dev/null
    elif command -v firefox &> /dev/null; then
        firefox $URL 2>/dev/null &
    elif command -v google-chrome &> /dev/null; then
        google-chrome $URL 2>/dev/null &
    else
        echo "🌐 Please open $URL manually"
    fi
) &

# Run streamlit - FIXED SYNTAX
streamlit run "$APP_PATH" \
    --server.port $PORT \
    --server.address localhost
    # Removed --server.headless and --browser.gatherUsageStats as they cause issues

# Handle exit
EXIT_CODE=$?
echo ""
echo "============================================================"
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Streamlit exited with code $EXIT_CODE"
else
    echo "✅ Streamlit exited normally"
fi
echo "============================================================"
