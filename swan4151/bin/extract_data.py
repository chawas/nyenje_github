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
