#!/bin/bash

# Nyenje Bay Climate Analysis Tool Launcher
# Flexible browser support - Firefox preferred, but works with any browser

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

# Function to open URL in best available browser
open_browser() {
    local URL=$1
    
    # Priority order: Firefox > Chrome > Edge > Brave > Default browser
    
    if command -v firefox &> /dev/null; then
        echo "🔥 Opening in Firefox (recommended for progress bar)..."
        if pgrep -x "firefox" > /dev/null; then
            firefox --new-tab "$URL" 2>/dev/null
        else
            firefox --new-window "$URL" 2>/dev/null &
        fi
        return 0
        
    elif command -v google-chrome &> /dev/null; then
        echo "🌐 Opening in Chrome (progress bar may have issues)..."
        echo "💡 Tip: Install Firefox for better progress bar experience"
        if pgrep -x "chrome" > /dev/null; then
            google-chrome --new-tab "$URL" 2>/dev/null
        else
            google-chrome --new-window "$URL" 2>/dev/null &
        fi
        return 0
        
    elif command -v chromium-browser &> /dev/null; then
        echo "🌐 Opening in Chromium..."
        chromium-browser "$URL" 2>/dev/null &
        return 0
        
    elif command -v brave-browser &> /dev/null; then
        echo "🌐 Opening in Brave..."
        brave-browser "$URL" 2>/dev/null &
        return 0
        
    elif command -v microsoft-edge &> /dev/null; then
        echo "🌐 Opening in Edge..."
        microsoft-edge "$URL" 2>/dev/null &
        return 0
        
    elif command -v xdg-open &> /dev/null; then
        echo "🌐 Opening in default browser..."
        xdg-open "$URL" 2>/dev/null &
        return 0
        
    else
        echo "⚠️  No browser found! Please manually open: $URL"
        return 1
    fi
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

# Source conda and activate environment
if [ -f "/home/chawas/anaconda3/etc/profile.d/conda.sh" ]; then
    echo "📌 Activating conda environment..."
    source /home/chawas/anaconda3/etc/profile.d/conda.sh
    conda activate deploy_env 2>/dev/null
    echo "✅ Environment ready"
else
    echo "📌 Using system Python..."
fi
echo ""

# Verify streamlit
if ! command -v streamlit &> /dev/null; then
    echo "⚠️  Streamlit not found. Installing..."
    pip install streamlit pandas numpy plotly scipy -q
    echo "✅ Streamlit installed"
fi

echo "🚀 Starting Streamlit server on port $PORT..."
echo "📊 The app will open in your browser"
echo "⌨️  Press Ctrl+C to stop the server"
echo ""

# Open browser after delay
(
    sleep 4
    URL="http://localhost:$PORT"
    open_browser "$URL"
) &

# Run streamlit
streamlit run "$APP_PATH" \
    --server.port $PORT \
    --server.address localhost \
    --server.headless false

# Handle exit
EXIT_CODE=$?
echo ""
echo "============================================================"
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Streamlit exited with code $EXIT_CODE"
    echo "   Try running: pkill -f streamlit && ./nyenje_tool.sh"
else
    echo "✅ Streamlit exited normally"
fi
echo "============================================================"