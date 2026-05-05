import re
import sys

def extract_data():
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
        return len(waves)
    return 0

if __name__ == "__main__":
    count = extract_data()
    print(count)
