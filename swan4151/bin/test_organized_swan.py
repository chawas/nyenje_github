import sys
sys.path.append('/home/chawas/deployed/charara_github/scripts')

# Import the functions
from era5_analysis import run_swan_for_timestamp, parse_swan_output, get_swan_run_status

# Test with a single file
timestamp = "19800727_1200"
wind_file = f"/home/chawas/deployed/charara_github/scripts/nyenje_era5_debiased/1980/nyenje_wind_{timestamp}.wnd"

print("=" * 60)
print("Testing Organized SWAN Runner")
print("=" * 60)

output_file, swn_file = run_swan_for_timestamp(timestamp, wind_file)

if output_file:
    print(f"\n✅ SUCCESS!")
    print(f"   SWAN input file: {swn_file}")
    print(f"   Output file: {output_file}")
    
    stats = parse_swan_output(output_file)
    if stats:
        print(f"\n📊 Wave Height Results:")
        print(f"   Max: {stats['max_hs']:.4f} m")
        print(f"   Mean: {stats['mean_hs']:.4f} m")
        print(f"   Min: {stats['min_hs']:.4f} m")
else:
    print("\n❌ FAILED")

# Check status
print("\n" + "=" * 60)
print("SWAN Run Status")
print("=" * 60)
status = get_swan_run_status("1980")
print(f"1980: {status['1980']['completed']} files completed")
