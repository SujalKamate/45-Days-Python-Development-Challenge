# Manufacturing Production Tracker with Efficiency Metrics

from datetime import date

machines  = {}
production= []
_mid = 1

def add_machine(name, model, target_units_per_hour, section):
    global _mid
    mid = f"MCH{_mid:03d}"; _mid += 1
    machines[mid] = {"name":name,"model":model,"target_uph":target_units_per_hour,
                     "section":section,"total_produced":0,"total_hours":0,"downtime_hours":0}
    print(f"  [{mid}] {name} ({model}) | Target: {target_units_per_hour} u/h | Section: {section}")
    return mid

def log_production(mid, prod_date, shift, units_produced, hours_run, downtime_hours=0, defects=0):
    if mid not in machines: print("  Machine not found."); return None
    if hours_run <= 0: print("  Hours must be positive."); return None
    m = machines[mid]
    target      = m["target_uph"] * hours_run
    efficiency  = round(units_produced / target * 100, 1) if target else 0
    defect_rate = round(defects / units_produced * 100, 2) if units_produced else 0
    good_units  = units_produced - defects
    m["total_produced"]  += units_produced
    m["total_hours"]     += hours_run
    m["downtime_hours"]  += downtime_hours
    record = {
        "mid":mid, "date":prod_date, "shift":shift, "units":units_produced,
        "good_units":good_units, "defects":defects, "hours":hours_run,
        "downtime":downtime_hours, "efficiency":efficiency, "defect_rate":defect_rate
    }
    production.append(record)
    print(f"  [{mid}] {prod_date} {shift} | {units_produced} units | Eff: {efficiency}% | Defects: {defects}")
    return record

def machine_performance(mid):
    if mid not in machines: return
    m = machines[mid]
    records = [r for r in production if r["mid"] == mid]
    if not records: print(f"  No production data for [{mid}]."); return
    avg_eff = round(sum(r["efficiency"] for r in records) / len(records), 1)
    total_good = sum(r["good_units"] for r in records)
    total_def  = sum(r["defects"]    for r in records)
    availability = round((m["total_hours"] - m["downtime_hours"]) / m["total_hours"] * 100, 1) if m["total_hours"] else 0
    oee = round(avg_eff * availability / 100, 1)
    print(f"\n  Performance [{mid}] {m['name']}:")
    print(f"  Total Produced : {m['total_produced']} units")
    print(f"  Good Units     : {total_good} | Defects: {total_def}")
    print(f"  Avg Efficiency : {avg_eff}%")
    print(f"  Availability   : {availability}%  (Downtime: {m['downtime_hours']}h)")
    print(f"  OEE            : {oee}%")

def daily_production_report(report_date):
    day_records = [r for r in production if r["date"] == report_date]
    if not day_records: print(f"  No data for {report_date}."); return
    print(f"\n{'='*58}\n  DAILY PRODUCTION REPORT — {report_date}\n{'='*58}")
    total_units = sum(r["units"]    for r in day_records)
    total_good  = sum(r["good_units"]for r in day_records)
    total_def   = sum(r["defects"]  for r in day_records)
    avg_eff     = round(sum(r["efficiency"] for r in day_records) / len(day_records), 1)
    print(f"  {'Machine':<10} {'Shift':<10} {'Units':>7} {'Good':>6} {'Def':>5} {'Eff%':>7}")
    for r in sorted(day_records, key=lambda x: (x["mid"],x["shift"])):
        mname = machines[r["mid"]]["name"][:10]
        print(f"  {mname:<10} {r['shift']:<10} {r['units']:>7} {r['good_units']:>6} {r['defects']:>5} {r['efficiency']:>6}%")
    print(f"  {'TOTAL':<10} {'':10} {total_units:>7} {total_good:>6} {total_def:>5} {avg_eff:>6}%")
    print(f"{'='*58}")

def compare_shifts():
    shift_stats = {}
    for r in production:
        s = r["shift"]
        if s not in shift_stats: shift_stats[s] = {"units":0,"efficiency":[],"records":0}
        shift_stats[s]["units"]      += r["units"]
        shift_stats[s]["efficiency"].append(r["efficiency"])
        shift_stats[s]["records"]    += 1
    print("\n  Shift Comparison:")
    for shift, stats in shift_stats.items():
        avg = round(sum(stats["efficiency"]) / len(stats["efficiency"]), 1) if stats["efficiency"] else 0
        print(f"  {shift:<12}: {stats['units']} units | Avg Eff: {avg}% | Records: {stats['records']}")

def main():
    print("=== Manufacturing Production Tracker ===")
    m1 = add_machine("CNC Lathe A1",    "HAAS ST-10",  45, "Machining")
    m2 = add_machine("Assembly Bot B2", "KUKA KR 10",  80, "Assembly")
    m3 = add_machine("Stamping Press",  "AIDA FX2000", 120,"Forming")
    today = date.today()
    log_production(m1, today, "Morning",   320, 8, downtime_hours=0.5, defects=8)
    log_production(m1, today, "Evening",   295, 8, downtime_hours=1.0, defects=5)
    log_production(m2, today, "Morning",   600, 8, downtime_hours=0,   defects=12)
    log_production(m2, today, "Evening",   580, 8, downtime_hours=0.5, defects=10)
    log_production(m3, today, "Morning",   900, 8, downtime_hours=0,   defects=20)
    log_production(m3, today, "Evening",   870, 7, downtime_hours=1,   defects=18)
    machine_performance(m1)
    machine_performance(m2)
    daily_production_report(today)
    compare_shifts()

if __name__ == "__main__":
    main()
