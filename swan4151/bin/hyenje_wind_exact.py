cat > create_exact_wind.py << 'EOF'
#!/usr/bin/env python3
"""
Create a wind file with exact format for SWAN
8 rows, 18 numbers per row (9 points × u + v components)
"""

# Configuration
rows = 8
cols = 9
u_val = -10.0  # u component for 10 m/s from 090°
v_val = 0.0    # v component for 10 m/s from 090°

# Create the wind file
with open('nyenje_wind_exact.wnd', 'w') as f:
    for i in range(rows):
        row_numbers = []
        for j in range(cols):
            row_numbers.extend([u_val, v_val])
        # Write with exactly one space between numbers, no trailing space
        line = ' '.join([f"{x:.3f}" for x in row_numbers])
        f.write(line + '\n')

print("Created: nyenje_wind_exact.wnd")
print(f"Rows: {rows}")
print(f"Numbers per row: {cols * 2}")
print("\nFirst row preview:")
with open('nyenje_wind_exact.wnd', 'r') as f:
    first = f.readline().strip()
    print(first[:80] + "...")
EOF

# Run the Python script
python3 create_exact_wind.py