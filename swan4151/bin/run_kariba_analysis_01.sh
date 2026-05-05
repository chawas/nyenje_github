#!/bin/bash

echo "========================================="
echo "Lake Kariba Wave Model Analysis"
echo "Started at: $(date)"
echo "========================================="

# Clean previous outputs
rm -f kariba_output.txt kariba_output.raw kariba_wave_report_*.txt kariba_wave_data_*.csv

# Run SWAN
echo "Running SWAN model..."
./swan.exe kariba_final.swn

# Check if SWAN succeeded
if [ -f "kariba_output.txt" ]; then
    echo "SWAN completed successfully!"
    echo "Output file size: $(wc -l kariba_output.txt) lines"
else
    echo "ERROR: SWAN output not found!"
    exit 1
fi

# Process output with Python
echo ""
echo "Processing output with Python..."
python3 process_swan_output_v2.py kariba_output.txt

echo ""
echo "========================================="
echo "Analysis Complete!"
echo "Finished at: $(date)"
echo "========================================="

# List generated files
echo ""
echo "Generated files:"
ls -la kariba_wave_report_*.txt kariba_wave_data_*.csv 2>/dev/null