#!/bin/bash

echo "========================================="
echo "LAKE KARIBA WAVE MODEL"
echo "========================================="
echo "Started: $(date)"

# Use the INPUT file that worked before (adjust name as needed)
# Try different possible input files
if [ -f "INPUT_30" ]; then
    INPUT="INPUT_30"
elif [ -f "INPUT_31" ]; then
    INPUT="INPUT_31"
elif [ -f "INPUT_32" ]; then
    INPUT="INPUT_32"
elif [ -f "kariba_final.swn" ]; then
    INPUT="kariba_final.swn"
else
    echo "No input file found!"
    exit 1
fi

echo "Using input file: $INPUT"

# Run SWAN
echo "Running SWAN..."
./swan.exe $INPUT

# Check if output was created
if [ -f "kariba_output.raw" ]; then
    echo "✓ SWAN completed successfully"
    
    # Extract wave heights
    echo ""
    echo "WAVE HEIGHT SUMMARY:"
    grep "^  0" kariba_output.raw | awk '{print $2}' | \
        awk 'BEGIN{min=999;max=0;sum=0} 
             {sum+=$1; count++; if($1<min) min=$1; if($1>max) max=$1} 
             END{printf "  Min: %.4f m (%.1f cm)\n", min, min*100;
                 printf "  Max: %.4f m (%.1f cm)\n", max, max*100;
                 printf "  Avg: %.4f m (%.1f cm)\n", sum/count, (sum/count)*100}'
    
    # Show grid
    echo ""
    echo "WAVE HEIGHT GRID (meters):"
    echo "North to South, West to East"
    echo "-----------------------------------"
    grep "^  0" kariba_output.raw | awk '{print $2}' | \
        awk 'BEGIN{row=1} {printf "%6.3f ", $1; if(NR%9==0){print ""; row++}}'
    
else
    echo "✗ SWAN failed - no output file"
    cat Errfile 2>/dev/null
fi

echo ""
echo "Finished: $(date)"
echo "========================================="
