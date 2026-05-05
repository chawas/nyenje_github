cat > run_nyenje_auto.sh << 'EOF'
#!/bin/bash
#===============================================================================
# COMPLETE AUTOMATION FOR LAKE KARIBA WAVE MODELING
#===============================================================================

set -e

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

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

cat > ${INPUT_FILE} << 'EOF2'
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
EOF2

sed -i "s/WIND 10.0 90.0/WIND ${WIND_SPEED}.0 ${WIND_DIR}.0/g" ${INPUT_FILE}
echo -e "${GREEN}✓ SWAN input file created${NC}"

#===============================================================================
# STEP 2: Check/Create bathymetry file
#===============================================================================
echo -e "\n${YELLOW}[2/5] Checking bathymetry file...${NC}"

if [ ! -f "${BATHY_FILE}" ]; then
    echo -e "${YELLOW}Creating default bathymetry file...${NC}"
    cat > ${BATHY_FILE} << 'EOF2'
5.36 1.50 2.29 0.50 2.87 3.09 3.20 1.56 1.50
6.61 5.98 3.80 5.14 6.42 2.86 1.50 1.50 1.50
16.82 7.58 7.80 10.22 10.30 3.07 1.50 1.50 1.50
16.06 9.90 11.06 15.05 11.97 4.45 1.50 1.50 1.50
19.21 16.55 13.52 17.65 8.72 5.03 1.50 1.50 1.50
29.30 15.17 16.64 5.63 5.74 3.26 1.50 1.50 1.50
16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50
16.45 1.50 1.50 1.50 1.50 1.50 1.50 1.50 1.50
EOF2
fi

echo -e "${GREEN}✓ Bathymetry file ready${NC}"

#===============================================================================
# STEP 3: Run SWAN
#===============================================================================
echo -e "\n${YELLOW}[3/5] Running SWAN model...${NC}"

rm -f kariba_output.txt kariba_output.raw PRINT Errfile norm_end
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

# Simple extraction script
cat > extract_simple.py << 'PYEOF'
import re

# Try to read from raw file first
raw_file = 'kariba_output.raw'
txt_file = 'kariba_output.txt'

waves = []
periods = []
directions = []

# Try raw file
try:
    with open(raw_file, 'r') as f:
        for line in f:
            if re.match(r'\s+0\s+', line):
                parts = line.strip().split()
                if len(parts) >= 4:
                    waves.append(float(parts[1]))
                    periods.append(float(parts[2]))
                    directions.append(float(parts[3]))
except:
    pass

# If raw didn't work, try txt file
if len(waves) == 0:
    try:
        with open(txt_file, 'r') as f:
            content = f.read()
        nums = re.findall(r'[-+]?\d+\.\d+E[+-]\d+', content)
        if not nums:
            nums = re.findall(r'[-+]?\d+\.\d+', content)
        floats = [float(x) for x in nums]
        if len(floats) >= 216:
            waves = floats[0:72]
            periods = floats[72:144]
            directions = floats[144:216]
    except:
        pass

# Save results
if len(waves) > 0:
    with open('waves.txt', 'w') as f:
        for w in waves:
            f.write(f"{w}\n")
    with open('periods.txt', 'w') as f:
        for p in periods:
            f.write(f"{p}\n")
    with open('directions.txt', 'w') as f:
        for d in directions:
            f.write(f"{d}\n")
    print(f"OK {len(waves)}")
else:
    print("FAIL 0")
PYEOF

EXTRACT_RESULT=$(python3 extract_simple.py 2>/dev/null)
if [[ "$EXTRACT_RESULT" == FAIL* ]]; then
    echo -e "${RED}✗ Failed to extract wave data${NC}"
    echo "Debug: Showing first 500 chars of output file"
    head -c 500 kariba_output.txt 2>/dev/null || head -c 500 kariba_output.raw 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓ Extracted wave data${NC}"

#===============================================================================
# STEP 5: Generate report
#===============================================================================
echo -e "\n${YELLOW}[5/5] Generating report...${NC}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="nyenje_report_${TIMESTAMP}.txt"

python3 << PYREPORT
import numpy as np

# Load data
waves = []
with open('waves.txt', 'r') as f:
    for line in f:
        waves.append(float(line.strip()))

periods = []
with open('periods.txt', 'r') as f:
    for line in f:
        periods.append(float(line.strip()))

directions = []
with open('directions.txt', 'r') as f:
    for line in f:
        directions.append(float(line.strip()))

waves = np.array(waves)
periods = np.array(periods)
directions = np.array(directions)

# Statistics (exclude zeros)
valid = waves > 0.001
if valid.sum() > 0:
    hs_min = waves[valid].min()
    hs_max = waves[valid].max()
    hs_mean = waves[valid].mean()
    hs_median = np.median(waves[valid])
    tm_min = periods[valid].min()
    tm_max = periods[valid].max()
    tm_mean = periods[valid].mean()
    dir_mean = directions[valid].mean()
else:
    hs_min = hs_max = hs_mean = hs_median = 0
    tm_min = tm_max = tm_mean = dir_mean = 0

# Create report
report = f"""
{'='*70}
LAKE KARIBA - NYENJE AREA WAVE ANALYSIS
{'='*70}
Report generated: $(date)
Wind: 10 m/s from 090° (East wind)
Domain: 4.0 km × 3.5 km
Grid: 9 × 8 points (500 m resolution)
{'='*70}

{'='*70}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*70}
┌─────────────────────┬─────────────┐
│ Statistic           │ Value       │
├─────────────────────┼─────────────┤
│ Minimum Hs          │ {hs_min:8.4f} m  │
│ Maximum Hs          │ {hs_max:8.4f} m  │
│ Mean Hs             │ {hs_mean:8.4f} m  │
│ Median Hs           │ {hs_median:8.4f} m  │
├─────────────────────┼─────────────┤
│ Minimum Tm01        │ {tm_min:8.2f} s   │
│ Maximum Tm01        │ {tm_max:8.2f} s   │
│ Mean Tm01           │ {tm_mean:8.2f} s   │
├─────────────────────┼─────────────┤
│ Mean DIR            │ {dir_mean:8.1f}°   │
└─────────────────────┴─────────────┘

{'='*70}
WAVE HEIGHT GRID (HSIGN in meters)
{'='*70}
North (top) to South (bottom), West (left) to East (right)
{'='*70}

     Col:    1      2      3      4      5      6      7      8      9
     {'-'*55}
"""

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
        row_str += " ← North shore"
    elif row == 7:
        row_str += " ← South shore"
    report += row_str + "\n"

report += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH
    WIND → → → → → → → → → 10 m/s FROM EAST (090°)
"""

with open('{REPORT_FILE}', 'w') as f:
    f.write(report)

print(f"Report saved: {REPORT_FILE}")
PYREPORT

# Display results
echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}AUTOMATION COMPLETE!${NC}"
echo -e "${GREEN}=========================================${NC}"

if [ -f "${REPORT_FILE}" ]; then
    echo -e "\n${BLUE}WAVE HEIGHT SUMMARY:${NC}"
    grep -A 10 "WAVE HEIGHT SUMMARY" ${REPORT_FILE} | head -15
    echo -e "\n${GREEN}Full report: ${REPORT_FILE}${NC}"
fi

echo -e "\n${BLUE}=========================================${NC}"
echo -e "Finished: $(date)"
echo -e "${BLUE}=========================================${NC}"
EOF

# Make executable and run
chmod +x run_nyenje_auto.sh
./run_nyenje_auto.sh