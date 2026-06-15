# Package Delivery Cost Estimator with Distance Factors

RATES = {
    "Standard":  {"base":50, "per_km":0.8,  "per_kg":12, "max_kg":30},
    "Express":   {"base":100,"per_km":1.5,  "per_kg":20, "max_kg":20},
    "Overnight": {"base":200,"per_km":2.0,  "per_kg":30, "max_kg":15},
    "Economy":   {"base":30, "per_km":0.5,  "per_kg":8,  "max_kg":50},
}
ZONE_MULTIPLIER = {"Local":1.0,"City":1.2,"State":1.4,"National":1.8,"Remote":2.5}
estimates = []

def estimate_cost(sender, receiver, weight_kg, length, breadth, height,
                  distance_km, zone, service="Standard"):
    if service not in RATES:
        print(f"  Invalid service. Options: {list(RATES.keys())}"); return None
    if zone not in ZONE_MULTIPLIER:
        print(f"  Invalid zone. Options: {list(ZONE_MULTIPLIER.keys())}"); return None
    r = RATES[service]
    if weight_kg > r["max_kg"]:
        print(f"  Weight {weight_kg}kg exceeds {service} limit of {r['max_kg']}kg"); return None
    vol_weight = round((length * breadth * height) / 5000, 2)
    chargeable = max(weight_kg, vol_weight)
    zone_mult  = ZONE_MULTIPLIER[zone]
    base_cost  = r["base"]
    dist_cost  = round(distance_km * r["per_km"], 2)
    weight_cost= round(chargeable  * r["per_kg"], 2)
    subtotal   = round((base_cost + dist_cost + weight_cost) * zone_mult, 2)
    gst        = round(subtotal * 0.18, 2)
    total      = round(subtotal + gst, 2)
    result = {
        "sender":sender, "receiver":receiver, "service":service, "zone":zone,
        "weight":weight_kg, "vol_weight":vol_weight, "chargeable":chargeable,
        "distance":distance_km, "base":base_cost, "dist_cost":dist_cost,
        "weight_cost":weight_cost, "zone_mult":zone_mult,
        "subtotal":subtotal, "gst":gst, "total":total
    }
    estimates.append(result)
    print(f"\n  Cost Estimate: {sender} → {receiver}")
    print(f"  Service      : {service} | Zone: {zone} | Multiplier: {zone_mult}x")
    print(f"  Weight       : {weight_kg}kg | Vol.Weight: {vol_weight}kg | Chargeable: {chargeable}kg")
    print(f"  Distance     : {distance_km} km")
    print(f"  Base Charge  : Rs.{base_cost}")
    print(f"  Distance Cost: Rs.{dist_cost}")
    print(f"  Weight Cost  : Rs.{weight_cost}")
    print(f"  Zone Factor  : Rs.{subtotal} (after {zone_mult}x)")
    print(f"  GST (18%)    : Rs.{gst}")
    print(f"  TOTAL        : Rs.{total}")
    return result

def compare_services(weight_kg, length, breadth, height, distance_km, zone):
    print(f"\n  Service Comparison ({weight_kg}kg, {distance_km}km, {zone}):")
    print(f"  {'Service':<12} {'Max kg':>7} {'Rate/km':>8} {'Rate/kg':>8} {'Total':>10}")
    print(f"  {'-'*50}")
    for svc, r in RATES.items():
        if weight_kg > r["max_kg"]:
            print(f"  {svc:<12} {'N/A (overweight)':>35}")
            continue
        vol_wt = (length*breadth*height) / 5000
        charg  = max(weight_kg, vol_wt)
        mult   = ZONE_MULTIPLIER.get(zone, 1.0)
        sub    = (r["base"] + distance_km*r["per_km"] + charg*r["per_kg"]) * mult
        total  = round(sub * 1.18, 2)
        print(f"  {svc:<12} {r['max_kg']:>7} {r['per_km']:>8.1f} {r['per_kg']:>8} Rs.{total:>8.2f}")

def bulk_estimate_report():
    if not estimates:
        print("  No estimates recorded."); return
    print(f"\n{'='*54}\n  DELIVERY COST SUMMARY REPORT\n{'='*54}")
    total_rev = sum(e["total"] for e in estimates)
    print(f"  Total Estimates : {len(estimates)}")
    print(f"  Total Value     : Rs.{total_rev:.2f}")
    print(f"  Avg Cost        : Rs.{total_rev/len(estimates):.2f}")
    svc_totals = {}
    for e in estimates:
        svc_totals[e["service"]] = svc_totals.get(e["service"], 0) + e["total"]
    print("\n  By Service:")
    for svc, total in sorted(svc_totals.items(), key=lambda x: -x[1]):
        print(f"    {svc:<12}: Rs.{total:.2f}")
    print(f"\n  {'From':<14} {'To':<14} {'Svc':<12} {'kg':>5} {'km':>6} {'Rs.':>8}")
    for e in estimates:
        print(f"  {e['sender']:<14} {e['receiver']:<14} {e['service']:<12} {e['weight']:>5} {e['distance']:>6} {e['total']:>8.2f}")
    print(f"{'='*54}")

def main():
    print("=== Package Delivery Cost Estimator ===")
    estimate_cost("Delhi Warehouse","Mumbai Store",    8, 40,30,20, 1400,"National","Standard")
    estimate_cost("Pune Factory",   "Bangalore Shop",  3, 30,20,15,  850,"State",   "Express")
    estimate_cost("Chennai Hub",    "Hyderabad Store", 15,60,40,30,  500,"State",   "Economy")
    estimate_cost("Kolkata Depot",  "Remote Village",  2, 25,20,10, 2200,"Remote",  "Standard")
    estimate_cost("Mumbai Office",  "Delhi Office",   25, 50,40,35, 1400,"National","Economy")
    estimate_cost("Local Bakery",   "Customer Home",   0.5,20,15,10,  12,"Local",   "Express")
    compare_services(5, 40, 30, 20, 1000, "National")
    bulk_estimate_report()

if __name__ == "__main__":
    main()
