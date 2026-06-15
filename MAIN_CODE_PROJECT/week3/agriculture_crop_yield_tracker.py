# Agriculture Crop Yield Tracker with Seasonal Analysis

records = {}
_rid = 1

SEASONS = ["Kharif", "Rabi", "Zaid"]

def add_record(farmer, crop, season, year, area_acres, yield_kg):
    global _rid
    if season not in SEASONS:
        print(f"  Invalid season. Options: {SEASONS}")
        return None
    if area_acres <= 0 or yield_kg <= 0:
        print("  Area and yield must be positive.")
        return None
    rid = f"YLD{_rid:04d}"
    _rid += 1
    yield_per_acre = round(yield_kg / area_acres, 2)
    records[rid] = {
        "farmer": farmer, "crop": crop, "season": season,
        "year": year, "area": area_acres, "yield_kg": yield_kg,
        "yield_per_acre": yield_per_acre
    }
    print(f"  [{rid}] {farmer} | {crop} | {season} {year} | {area_acres} acres | {yield_kg} kg ({yield_per_acre} kg/acre)")
    return rid

def crop_analysis(crop_name):
    crop_records = [r for r in records.values() if r["crop"].lower() == crop_name.lower()]
    if not crop_records:
        print(f"  No records found for crop '{crop_name}'.")
        return
    total_yield = sum(r["yield_kg"] for r in crop_records)
    total_area  = sum(r["area"]     for r in crop_records)
    avg_ypa     = round(total_yield / total_area, 2) if total_area else 0
    best  = max(crop_records, key=lambda x: x["yield_per_acre"])
    worst = min(crop_records, key=lambda x: x["yield_per_acre"])
    print(f"\n  Crop Analysis: {crop_name}")
    print(f"  Records       : {len(crop_records)}")
    print(f"  Total Yield   : {total_yield} kg")
    print(f"  Total Area    : {total_area} acres")
    print(f"  Avg Yield/acre: {avg_ypa} kg")
    print(f"  Best  Season  : {best['season']} {best['year']} — {best['yield_per_acre']} kg/acre ({best['farmer']})")
    print(f"  Worst Season  : {worst['season']} {worst['year']} — {worst['yield_per_acre']} kg/acre ({worst['farmer']})")

def season_comparison(season):
    s_records = [r for r in records.values() if r["season"] == season]
    if not s_records:
        print(f"  No records for season '{season}'.")
        return
    print(f"\n--- {season} Season Comparison ---")
    crops = sorted(set(r["crop"] for r in s_records))
    for crop in crops:
        cr = [r for r in s_records if r["crop"] == crop]
        avg = round(sum(r["yield_per_acre"] for r in cr) / len(cr), 2)
        print(f"  {crop:<18}: avg {avg} kg/acre over {len(cr)} record(s)")

def year_trend(crop_name):
    crop_records = sorted(
        [r for r in records.values() if r["crop"].lower() == crop_name.lower()],
        key=lambda x: x["year"]
    )
    if not crop_records:
        print(f"  No trend data for '{crop_name}'.")
        return
    print(f"\n  Yield Trend — {crop_name}")
    print(f"  {'Year':<6} {'Season':<10} {'Yield/Acre':>12} {'Bar'}")
    max_ypa = max(r["yield_per_acre"] for r in crop_records)
    for r in crop_records:
        bar = "█" * int(r["yield_per_acre"] / max_ypa * 20)
        print(f"  {r['year']:<6} {r['season']:<10} {r['yield_per_acre']:>10} kg  {bar}")

def full_report():
    print(f"\n{'='*52}")
    print("  CROP YIELD SUMMARY REPORT")
    print(f"{'='*52}")
    farmers = sorted(set(r["farmer"] for r in records.values()))
    for farmer in farmers:
        fr = [r for r in records.values() if r["farmer"] == farmer]
        total = sum(r["yield_kg"] for r in fr)
        print(f"  {farmer:<20}: {len(fr)} crops | {total:,} kg total")
    print(f"\n  All Records:")
    for rid, r in records.items():
        print(f"  {rid} | {r['crop']:<15} {r['season']:<8} {r['year']} | {r['yield_per_acre']} kg/acre")
    print(f"{'='*52}")

def main():
    print("=== Agriculture Crop Yield Tracker ===")
    add_record("Ramesh Patel",  "Wheat",  "Rabi",   2022, 5.0, 9500)
    add_record("Ramesh Patel",  "Wheat",  "Rabi",   2023, 5.0, 10200)
    add_record("Suresh Kumar",  "Rice",   "Kharif", 2022, 4.0, 7200)
    add_record("Suresh Kumar",  "Rice",   "Kharif", 2023, 4.5, 8100)
    add_record("Anita Singh",   "Cotton", "Kharif", 2022, 6.0, 5400)
    add_record("Anita Singh",   "Cotton", "Kharif", 2023, 6.0, 6000)
    add_record("Ramesh Patel",  "Maize",  "Zaid",   2023, 3.0, 5100)
    add_record("Kavya Rao",     "Wheat",  "Rabi",   2023, 7.0, 14700)
    crop_analysis("Wheat")
    season_comparison("Kharif")
    year_trend("Rice")
    full_report()

if __name__ == "__main__":
    main()
