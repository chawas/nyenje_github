#!/bin/bash
#===============================================================================
# COMPLETE AUTOMATION FOR LAKE KARIBA WAVE MODELING
# Handles: SWAN execution, data extraction, report generation
#===============================================================================

set -e  # Stop on error

# Configuration
SWAN_EXE="./swan.exe"
INPUT_FILE="kariba_final.swn"
BATHY_FILE="nyenje_bathymetry_8x7.bot"
WIND_SPEED=10
WIND_DIR=90
DOMAIN_X=4000
DOMAIN_Y=3500
GRID_X=9
GRID_Y=8

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}LAKE KARIBA WAVE MODEL AUTOMATION${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "Started: $(date)"
echo -e "Wind: ${WIND_SPEED} m/s from ${WIND_DIR}° (East wind)"
echo -e "Domain: ${DOMAIN_X}m x ${DOMAIN_Y}m"
echo -e "Grid: ${GRID_X} x ${GRID_Y} points"
echo -e "${BLUE}=========================================${NC}"

#===============================================================================
# STEP 1: Create SWAN input file
#===============================================================================
echo -e "\n${YELLOW}[1/5] Creating SWAN input file...${NC}"

cat > ${INPUT_FILE} << 'EOF'
PROJECT 'Kariba' '001' 'Lake Kariba Nyenje' ' ' ' '

MODE STATIONARY TWODIMENSIONAL

COORDINATES CARTESIAN

CGRID REGULAR 0.0 0.0 0.0 4000.0 3500.0 8 7 CIRCLE 36 0.04 1.00 25

INPGRID BOTTOM REGULAR 0.0 0.0 0.0 8 7 500.0 500.0
READINP BOTTOM 1.0 'nyenje_bathymetry_8x7.bot' 1 0 FREE

WIND 10.0 90.0

GEN3 KOMEN 2.36E-5 3.02E-3
FRICTION JONSWAP CONSTANT 0.038
BREAKING CONSTANT 1.0 0.73

NUMERIC STOPC 0.02 0.01 0.001 98 STAT 50 0.01

BLOCK 'COMPGRID' NOHEADER 'kariba_output.txt' LAYOUT 4 HSIGN TM01 DIR

COMPUTE

STOP
EOF

# Update wind speed in the file
sed -i "s/WIND 10.0 90.0/WIND ${WIND_SPEED}.0 ${WIND_DIR}.0/g" ${INPUT_FILE}

echo -e "${GREEN}✓ SWAN input file created${NC}"

#===============================================================================
# STEP 2: Check/Create bathymetry file
#===============================================================================
echo -e "\n${YELLOW}[2/5] Checking bathymetry file...${NC}"

if [ ! -f "${BATHY_FILE}" ]; then
    echo -e "${YELLOW}Creating default bathymetry file...${NC}"
    cat > ${BATHY_FILE} << 'EOF'
5.36 1.50 2.29 0.50 2.87 3.09 3.20 1.56 1.50
6.61 5.98 3.80 5.14 6.42 2.86 1.50 1.50 1.50
16.82 7.58 7.80 10.22 10.30 3.07 1.50 1.50 1.50
16.06 9.90 11.06 15.05 11.97 4.45 1.50 1.50 1.50
19.21 16.55 13.52 17.65 8.72 5.03 1.50 1.50 1.50
29.30 15.17 16.64 5.63 5.74 3.26 1.50 1.50 1.50
16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50
16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50
EOF
fi

echo -e "${GREEN}✓ Bathymetry file ready${NC}"

#===============================================================================
# STEP 3: Run SWAN
#===============================================================================
echo -e "\n${YELLOW}[3/5] Running SWAN model...${NC}"

# Clean old outputs
rm -f kariba_output.txt kariba_output.raw PRINT Errfile norm_end

# Run SWAN
${SWAN_EXE} ${INPUT_FILE} > /dev/null 2>&1

if [ -f "kariba_output.txt" ] || [ -f "kariba_output.raw" ]; then
    echo -e "${GREEN}✓ SWAN completed successfully${NC}"
else
    echo -e "${RED}✗ SWAN failed to produce output${NC}"
    exit 1
fi

#===============================================================================
# STEP 4: Extract wave data
#===============================================================================
echo -e "\n${YELLOW}[4/5] Extracting wave data...${NC}"

# Python script for extraction
cat > extract_data.py << 'PYTHON_SCRIPT'
import re
import sys
import numpy as np

def extract_from_raw(filename):
    """Extract from .raw format (TABLE/POINTS output)"""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    waves, periods, directions = [], [], []
    for line in lines:
        if re.match(r'\s+0\s+', line):
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    waves.append(float(parts[1]))
                    periods.append(float(parts[2]))
                    directions.append(float(parts[3]))
                except:
                    pass
    return waves, periods, directions

def extract_from_txt(filename):
    """Extract from .txt format (BLOCK output with scientific notation)"""
    with open(filename, 'r') as f:
        content = f.read()
    
    pattern = r'[-+]?\d+\.\d+E[+-]\d+'
    numbers = re.findall(pattern, content)
    if not numbers:
        pattern = r'[-+]?\d+\.\d+'
        numbers = re.findall(pattern, content)
    
    floats = [float(x) for x in numbers]
    if len(floats) >= 216:
        return floats[0:72], floats[72:144], floats[144:216]
    return [], [], []

# Find and parse the output file
raw_file = 'kariba_output.raw'
txt_file = 'kariba_output.txt'

waves, periods, directions = [], [], []

if os.path.exists(raw_file) and os.path.getsize(raw_file) > 1000:
    waves, periods, directions = extract_from_raw(raw_file)
elif os.path.exists(txt_file):
    waves, periods, directions = extract_from_txt(txt_file)

if waves:
    # Save to numpy format for easy loading
    np.save('wave_heights.npy', np.array(waves))
    np.save('wave_periods.npy', np.array(periods))
    np.save('wave_directions.npy', np.array(directions))
    print(f"EXTRACTED:{len(waves)}")
else:
    print("EXTRACTED:0")
PYTHON_SCRIPT

# Run extraction
EXTRACTED=$(python3 extract_data.py 2>/dev/null | grep "EXTRACTED:" | cut -d: -f2)

if [ "${EXTRACTED}" = "0" ] || [ -z "${EXTRACTED}" ]; then
    echo -e "${RED}✗ Failed to extract wave data${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Extracted ${EXTRACTED} wave data points${NC}"

#===============================================================================
# STEP 5: Generate comprehensive report
#===============================================================================
echo -e "\n${YELLOW}[5/5] Generating report...${NC}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="kariba_report_${TIMESTAMP}.txt"
CSV_FILE="kariba_data_${TIMESTAMP}.csv"

python3 << PYTHON_REPORT
import numpy as np
import datetime

# Load data
waves = np.load('wave_heights.npy')
periods = np.load('wave_periods.npy')
directions = np.load('wave_directions.npy')

# Remove zeros (land/dry cells)
valid = waves > 0.001
waves_valid = waves[valid]
periods_valid = periods[valid]
directions_valid = directions[valid]

# Statistics
hs_min = waves_valid.min()
hs_max = waves_valid.max()
hs_mean = waves_valid.mean()
hs_median = np.median(waves_valid)

tm_min = periods_valid.min()
tm_max = periods_valid.max()
tm_mean = periods_valid.mean()

dir_min = directions_valid.min()
dir_max = directions_valid.max()
dir_mean = directions_valid.mean()

# Create report
report = f"""
{'='*70}
LAKE KARIBA - NYENJE AREA WAVE ANALYSIS
{'='*70}
Report generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Wind: 10 m/s from 090° (East wind)
Domain: 4.0 km × 3.5 km
Grid: 9 × 8 points (500 m resolution)
{'='*70}

{'='*70}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*70}
┌─────────────────────┬─────────────┬──────────────────────────────────────────┐
│ Statistic           │ Value       │ Interpretation                           │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Hs          │ {hs_min:8.4f} m  │ {hs_min*100:.2f} cm                                    │
│ Maximum Hs          │ {hs_max:8.4f} m  │ {hs_max*100:.2f} cm                                    │
│ Mean Hs             │ {hs_mean:8.4f} m  │ {hs_mean*100:.2f} cm                                    │
│ Median Hs           │ {hs_median:8.4f} m  │                                                          │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum Tm01        │ {tm_min:8.2f} s   │                                                          │
│ Maximum Tm01        │ {tm_max:8.2f} s   │                                                          │
│ Mean Tm01           │ {tm_mean:8.2f} s   │                                                          │
├─────────────────────┼─────────────┼──────────────────────────────────────────┤
│ Minimum DIR         │ {dir_min:8.1f}°   │                                                          │
│ Maximum DIR         │ {dir_max:8.1f}°   │                                                          │
│ Mean DIR            │ {dir_mean:8.1f}°   │                                                          │
└─────────────────────┴─────────────┴──────────────────────────────────────────┘

{'='*70}
WAVE HEIGHT GRID (HSIGN in meters)
{'='*70}
North (top) to South (bottom), West (left) to East (right)
{'='*70}

     Col:    1      2      3      4      5      6      7      8      9
     {'-'*55}
"""

# Reshape to 8x9 grid
for row in range(8):
    start = row * 9
    row_vals = waves[start:start+9]
    report += f"Row {row+1}: " + " ".join([f"{v:6.3f}" for v in row_vals]) + "\n"

report += f"""
{'='*70}
WAVE HEIGHT VISUAL MAP
{'='*70}
                    NORTH (Shallow area)
    ┌─────────────────────────────────────────────────────────────────┐
"""

for row in range(8):
    start = row * 9
    row_vals = waves[start:start+9]
    row_str = "    │"
    for v in row_vals:
        if v < 0.01:
            row_str += "  0.000  "
        else:
            row_str += f" {v:6.3f} "
    row_str += "│"
    if row == 0:
        row_str += " ← North shore (wave breaking zone)"
    elif row == 3 or row == 4:
        row_str += " ← Center of domain"
    elif row == 7:
        row_str += " ← South shore"
    report += row_str + "\n"

report += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH
    WIND → → → → → → → → → 10 m/s FROM EAST (090°)

Note: Values are in meters. Small values indicate shallow water wave breaking.
"""

# Save report
with open('{REPORT_FILE}', 'w') as f:
    f.write(report)

# Create CSV
with open('{CSV_FILE}', 'w') as f:
    f.write("X_km,Y_km,HSIGN_m,TM01_s,DIR_deg\\n")
    for row in range(8):
        for col in range(9):
            idx = row * 9 + col
            x_km = col * 0.5
            y_km = (7 - row) * 0.5
            f.write(f"{x_km:.1f},{y_km:.1f},{waves[idx]:.4f},{periods[idx]:.2f},{directions[idx]:.1f}\\n")

print(f"Report saved: {REPORT_FILE}")
print(f"CSV saved: {CSV_FILE}")
PYTHON_REPORT

#===============================================================================
# Display results
#===============================================================================
echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}AUTOMATION COMPLETE!${NC}"
echo -e "${GREEN}=========================================${NC}"

# Find and display the latest report
LATEST_REPORT=$(ls -t kariba_report_*.txt 2>/dev/null | head -1)
if [ -f "${LATEST_REPORT}" ]; then
    echo -e "\n${BLUE}REPORT PREVIEW:${NC}"
    echo -e "${BLUE}=========================================${NC}"
    head -30 ${LATEST_REPORT}
    echo -e "${BLUE}...${NC}"
    echo -e "\n${GREEN}Full report: ${LATEST_REPORT}${NC}"
fi

# Display wave height summary
echo -e "\n${BLUE}WAVE HEIGHT SUMMARY:${NC}"
python3 -c "
import numpy as np
waves = np.load('wave_heights.npy')
valid = waves[waves > 0.001]
print(f\"  Min: {valid.min():.4f} m ({valid.min()*100:.1f} cm)\")
print(f\"  Max: {valid.max():.4f} m ({valid.max()*100:.1f} cm)\")
print(f\"  Avg: {valid.mean():.4f} m ({valid.mean()*100:.1f} cm)\")
"

echo -e "\n${GREEN}Generated files:${NC}"
ls -la kariba_*${TIMESTAMP}* 2>/dev/null || ls -la kariba_report_*.txt kariba_data_*.csv 2>/dev/null

echo -e "\n${BLUE}=========================================${NC}"
echo -e "Finished: $(date)"
echo -e "${BLUE}=========================================${NC}"