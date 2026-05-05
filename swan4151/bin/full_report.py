import re
import datetime

with open('kariba_output.raw', 'r') as f:
    lines = f.readlines()

waves = []
periods = []
directions = []

for i, line in enumerate(lines):
    if re.match(r'\s+0\s+', line):
        parts = line.strip().split()
        if len(parts) >= 4:
            waves.append(float(parts[1]))
            periods.append(float(parts[2]))
            directions.append(float(parts[3]))

timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

report = f"""
{'='*60}
LAKE KARIBA - NYENJE AREA WAVE ANALYSIS
{'='*60}
Report Date/Time: {timestamp}
Wind: 10 m/s from 090° (East wind)
Domain: 4.0 km × 3.5 km
Grid: 9 × 8 points
{'='*60}

{'='*60}
WAVE HEIGHT SUMMARY (HSIGN)
{'='*60}
┌─────────────────────┬─────────────┬────────────────────────────────┐
│ Statistic           │ Value       │ Interpretation                 │
├─────────────────────┼─────────────┼────────────────────────────────┤
│ Minimum Hs          │ {min(waves):8.4f} m  │ {min(waves)*100:.2f} cm                        │
│ Maximum Hs          │ {max(waves):8.4f} m  │ {max(waves)*100:.2f} cm                        │
│ Average Hs          │ {sum(waves)/len(waves):8.4f} m  │ {sum(waves)/len(waves)*100:.2f} cm          │
└─────────────────────┴─────────────┴────────────────────────────────┘

{'='*60}
WAVE HEIGHT GRID (HSIGN in meters)
{'='*60}
North (top) to South (bottom), West (left) to East (right)
{'='*60}

     Col:    1      2      3      4      5      6      7      8      9
     {'-'*55}
"""

for row in range(8):
    start = row * 9
    row_vals = waves[start:start+9]
    report += f"Row {row+1}: " + " ".join([f"{v:6.3f}" for v in row_vals]) + "\n"

report += f"""
{'='*60}
WAVE HEIGHT VISUAL MAP
{'='*60}

                    NORTH (Y=3.5 km)
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
        row_str += " ← North shore (shallow, wave breaking)"
    elif row == 7:
        row_str += " ← South shore"
    elif row == 4:
        row_str += " ← Center of domain"
    report += row_str + "\n"

report += f"""    └─────────────────────────────────────────────────────────────────┘
                    SOUTH (Y=0.0 km)

    WIND → → → → → → → → → 10 m/s FROM EAST (090°)

Note: Values are in meters. Smaller values indicate wave breaking in shallow areas.
"""

# Save report
report_file = f'kariba_analysis_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
with open(report_file, 'w') as f:
    f.write(report)

print(report)
print(f"\nReport saved to: {report_file}")
