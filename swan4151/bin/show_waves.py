import re

# Read the file
with open('kariba_output.raw', 'r') as f:
    lines = f.readlines()

# Extract wave heights
waves = []
for i, line in enumerate(lines):
    if re.match(r'\s+0\s+', line):
        parts = line.strip().split()
        if len(parts) >= 2:
            waves.append(float(parts[1]))

print(f"Found {len(waves)} wave height values")
print(f"\n{'='*50}")
print("LAKE KARIBA WAVE HEIGHT SUMMARY")
print(f"{'='*50}")
print(f"Minimum: {min(waves):.4f} m ({min(waves)*100:.2f} cm)")
print(f"Maximum: {max(waves):.4f} m ({max(waves)*100:.2f} cm)")
print(f"Average: {sum(waves)/len(waves):.4f} m")
print()

# Show as 8x9 grid (if we have 72 values)
if len(waves) >= 72:
    print("WAVE HEIGHT GRID (8 rows x 9 columns)")
    print("North (top) to South (bottom), West to East")
    print("-" * 50)
    for row in range(8):
        start = row * 9
        row_vals = waves[start:start+9]
        print(f"Row{row+1}: " + " ".join([f"{v:6.3f}" for v in row_vals]))
    print("\nWIND → → → 10 m/s FROM EAST (090°)")
