#!/bin/bash

echo "========================================="
echo "Lake Kariba Wave Model Analysis"
echo "Started at: $(date)"
echo "========================================="

# Run SWAN
echo "Running SWAN model..."
./swan.exe 

# Check what output file was created
echo ""
echo "Output files created:"
ls -la kariba_output*

# Process with the header parser
echo ""
echo "Processing output with Python..."
python3 process_swan_output_header.py kariba_output.raw

echo ""
echo "========================================="
echo "Analysis Complete!"
echo "Finished at: $(date)"
echo "========================================="