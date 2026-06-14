# Smart Utility Consumption Dashboard with Monthly Comparisons

RATES = {"electricity":{"unit":"kWh","rate":6.50,"fixed":100},
         "water":      {"unit":"kL", "rate":18.0,"fixed":50},
         "gas":        {"unit":"m3", "rate":45.0,"fixed":75}}
TAX_PCT = 0.05
readings = {}
_hid = 1

def add_household(name, address):
    global _hid
    hid = f"HH{_hid:04d}"; _hid += 1
    readings[hid] = {"name":name,"address":address,"logs":[]}
    print(f"  [{hid}] {name} | {address}")
    return hid

def record_reading(hid, month, year, electricity, water, gas):
    if hid not in readings: print("  Household not found."); return None
    bills = {}; total = 0
    for util, usage in [("electricity",electricity),("water",water),("gas",gas)]:
        r = RATES[util]
        charge = round(usage*r["rate"]+r["fixed"],2)
        tax    = round(charge*TAX_PCT,2)
        bills[util] = {"usage":usage,"charge":charge,"tax":tax,"total":round(charge+tax,2)}
        total += bills[util]["total"]
    entry = {"month":month,"year":year,"electricity":electricity,"water":water,
             "gas":gas,"bills":bills,"total_bill":round(total,2)}
    readings[hid]["logs"].append(entry)
    print(f"  [{hid}] {month}/{year} | Elec:{electricity}kWh Water:{water}kL Gas:{gas}m3 | Rs.{total:.2f}")
    return entry

def monthly_bill(hid, month, year):
    if hid not in readings: return
    log = next((l for l in readings[hid]["logs"] if l["month"]==month and l["year"]==year),None)
    if not log: print(f"  No data for {month}/{year}."); return
    h = readings[hid]
    print(f"\n{'='*52}\n  UTILITY BILL — {h['name']} | {month}/{year}\n{'='*52}")
    for util, b in log["bills"].items():
        r = RATES[util]
        print(f"  {util.capitalize():<14} {b['usage']:>7.1f} {r['unit']:<5} "
              f"Rs.{b['charge']:.2f} + Tax Rs.{b['tax']:.2f} = Rs.{b['total']:.2f}")
    print(f"  {'TOTAL':<40} Rs.{log['total_bill']:.2f}\n{'='*52}")

def monthly_comparison(hid):
    if hid not in readings: return
    logs = sorted(readings[hid]["logs"],key=lambda x:(x["year"],x["month"]))
    if len(logs)<2: print("  Need ≥2 months of data."); return
    print(f"\n  Monthly Comparison — {readings[hid]['name']}")
    print(f"  {'Month':<8} {'Elec':>8} {'Water':>8} {'Gas':>7} {'Bill':>10}")
    for l in logs:
        print(f"  {l['month']:02d}/{l['year']} {l['electricity']:>8.1f} {l['water']:>8.1f} {l['gas']:>7.1f} Rs.{l['total_bill']:>8.2f}")
    prev,curr = logs[-2],logs[-1]
    print(f"  Month-on-Month Change ({prev['month']}/{prev['year']} → {curr['month']}/{curr['year']}):")
    for util in ["electricity","water","gas"]:
        diff = curr[util]-prev[util]; pct = round(diff/prev[util]*100,1) if prev[util] else 0
        arrow = "▲" if diff>0 else "▼"
        print(f"    {util.capitalize():<14}: {arrow} {abs(diff):.1f} {RATES[util]['unit']} ({pct:+.1f}%)")

def usage_trends(hid):
    if hid not in readings: return
    logs = readings[hid]["logs"]
    if not logs: return
    print(f"\n  Usage Trends — {readings[hid]['name']}:")
    for util in ["electricity","water","gas"]:
        vals = [l[util] for l in logs]
        avg  = round(sum(vals)/len(vals),1)
        print(f"  {util.capitalize():<14}: Avg {avg} | Peak {max(vals)} | Low {min(vals)} {RATES[util]['unit']}")

def consumption_alerts(hid, limits=None):
    if hid not in readings: return
    thresholds = limits or {"electricity":300,"water":20,"gas":30}
    logs = readings[hid]["logs"]
    if not logs: return
    latest = sorted(logs,key=lambda x:(x["year"],x["month"]))[-1]
    print(f"\n  Alerts [{hid}] {readings[hid]['name']} ({latest['month']}/{latest['year']}):")
    any_alert = False
    for util,limit in thresholds.items():
        usage = latest[util]
        if usage>limit:
            pct = round((usage-limit)/limit*100,1)
            print(f"  ⚠ {util.capitalize()}: {usage} {RATES[util]['unit']} — {pct}% above limit ({limit})")
            any_alert = True
    if not any_alert: print("  ✔ All utilities within normal range.")

def utility_report():
    print(f"\n{'='*54}\n  UTILITY CONSUMPTION REPORT\n{'='*54}")
    for hid,h in readings.items():
        if not h["logs"]: continue
        total_bills = sum(l["total_bill"] for l in h["logs"])
        months      = len(h["logs"])
        avg_bill    = round(total_bills/months,2)
        all_elec    = sum(l["electricity"] for l in h["logs"])
        all_water   = sum(l["water"]       for l in h["logs"])
        print(f"  [{hid}] {h['name']:<22} {months}mo | Total:Rs.{total_bills:.0f} | "
              f"AvgBill:Rs.{avg_bill:.0f} | Elec:{all_elec:.0f}kWh Water:{all_water:.0f}kL")
    print(f"{'='*54}")

def main():
    print("=== Smart Utility Consumption Dashboard ===")
    h1 = add_household("Sharma Family",   "12-A, Green Park, Delhi")
    h2 = add_household("Patel Residence", "45 Satellite Rd, Ahmedabad")
    data_h1 = [(1,210,12.0,18.0),(2,195,11.5,17.0),(3,220,13.0,19.5),
               (4,260,14.5,20.0),(5,320,16.0,22.0),(6,380,18.5,24.0)]
    data_h2 = [(4,180,10.0,15.0),(5,200,11.0,16.5),(6,350,22.0,28.0)]
    for m,e,w,g in data_h1: record_reading(h1,m,2025,e,w,g)
    for m,e,w,g in data_h2: record_reading(h2,m,2025,e,w,g)
    monthly_bill(h1,6,2025)
    monthly_comparison(h1)
    usage_trends(h1)
    consumption_alerts(h1)
    consumption_alerts(h2)
    utility_report()

if __name__ == "__main__":
    main()
