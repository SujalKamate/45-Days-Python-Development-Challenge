# Parcel Packing Optimizer with Weight Validation

CARRIERS = {
    "SpeedPost": {"max_weight": 35,  "max_dim_sum": 150, "base_rate": 50, "per_kg": 15},
    "BlueDart":  {"max_weight": 50,  "max_dim_sum": 200, "base_rate": 80, "per_kg": 20},
    "DTDC":      {"max_weight": 30,  "max_dim_sum": 120, "base_rate": 40, "per_kg": 12},
    "FedEx":     {"max_weight": 70,  "max_dim_sum": 300, "base_rate": 150,"per_kg": 35},
}
parcels = {}
_pid = 1

def add_parcel(description, weight_kg, length_cm, breadth_cm, height_cm, fragile=False):
    global _pid
    pid = f"PKG{_pid:04d}"
    _pid += 1
    dim_sum = length_cm + breadth_cm + height_cm
    volume  = round(length_cm * breadth_cm * height_cm / 1000, 2)
    parcels[pid] = {
        "description": description, "weight": weight_kg,
        "length": length_cm, "breadth": breadth_cm, "height": height_cm,
        "dim_sum": dim_sum, "volume_litres": volume, "fragile": fragile
    }
    print(f"  [{pid}] {description} | {weight_kg}kg | {length_cm}x{breadth_cm}x{height_cm}cm | Vol:{volume}L {'[FRAGILE]' if fragile else ''}")
    return pid

def validate_parcel(pid, carrier):
    if pid not in parcels:
        print("  Parcel not found.")
        return False, []
    if carrier not in CARRIERS:
        print("  Carrier not found.")
        return False, []
    p = parcels[pid]
    c = CARRIERS[carrier]
    issues = []
    if p["weight"] > c["max_weight"]:
        issues.append(f"Weight {p['weight']}kg exceeds limit {c['max_weight']}kg")
    if p["dim_sum"] > c["max_dim_sum"]:
        issues.append(f"Dimensions sum {p['dim_sum']}cm exceeds limit {c['max_dim_sum']}cm")
    if issues:
        return False, issues
    return True, []

def calculate_shipping(pid, carrier):
    valid, issues = validate_parcel(pid, carrier)
    if not valid:
        print(f"  [{pid}] Cannot ship via {carrier}:")
        for issue in issues:
            print(f"    ✗ {issue}")
        return None
    p = parcels[pid]
    c = CARRIERS[carrier]
    charge = round(c["base_rate"] + p["weight"] * c["per_kg"], 2)
    if p["fragile"]:
        charge = round(charge * 1.15, 2)
    print(f"  [{pid}] via {carrier}: Rs.{charge}" + (" (fragile surcharge applied)" if p["fragile"] else ""))
    return charge

def suggest_best_carrier(pid):
    if pid not in parcels:
        print("  Parcel not found.")
        return
    print(f"\n  Carrier Options for [{pid}] {parcels[pid]['description']}:")
    options = []
    for carrier in CARRIERS:
        valid, issues = validate_parcel(pid, carrier)
        if valid:
            charge = calculate_shipping(pid, carrier)
            if charge:
                options.append((carrier, charge))
    if not options:
        print("  No carrier can handle this parcel.")
        return
    best = min(options, key=lambda x: x[1])
    print(f"  ★ Best option: {best[0]} at Rs.{best[1]}")
    return best

def packing_suggestion(pids):
    print(f"\n  Packing Suggestion for {len(pids)} item(s):")
    total_weight = sum(parcels[p]["weight"] for p in pids if p in parcels)
    total_vol    = sum(parcels[p]["volume_litres"] for p in pids if p in parcels)
    fragile_items = [parcels[p]["description"] for p in pids if parcels.get(p, {}).get("fragile")]
    print(f"  Total Weight : {total_weight:.2f} kg")
    print(f"  Total Volume : {total_vol:.2f} L")
    if fragile_items:
        print(f"  Fragile Items: {', '.join(fragile_items)}")
        print("  ⚠ Place fragile items on top with extra padding.")
    if total_weight > 30:
        print("  ⚠ Consider splitting into multiple parcels.")
    if total_vol > 50:
        print("  ⚠ Use a large box (approx. 50x40x30 cm or larger).")

def shipment_report():
    print(f"\n{'='*55}")
    print("  SHIPMENT SUMMARY REPORT")
    print(f"{'='*55}")
    total_weight = sum(p["weight"] for p in parcels.values())
    print(f"  Total Parcels   : {len(parcels)}")
    print(f"  Total Weight    : {total_weight:.2f} kg")
    fragile_count = sum(1 for p in parcels.values() if p["fragile"])
    print(f"  Fragile Items   : {fragile_count}")
    print(f"\n  {'ID':<8} {'Description':<20} {'Wt(kg)':>7} {'Dims (cm)':>14} {'Vol(L)':>7}")
    for pid, p in parcels.items():
        dims = f"{p['length']}x{p['breadth']}x{p['height']}"
        print(f"  {pid:<8} {p['description']:<20} {p['weight']:>7} {dims:>14} {p['volume_litres']:>7}")
    print(f"{'='*55}")

def main():
    print("=== Parcel Packing Optimizer ===")
    p1 = add_parcel("Laptop",       2.5, 40, 30, 10, fragile=True)
    p2 = add_parcel("Books (set)",  4.0, 35, 25, 20)
    p3 = add_parcel("Clothes",      1.2, 50, 40, 15)
    p4 = add_parcel("Heavy Machine",45, 80, 60, 50)
    p5 = add_parcel("Glassware",    3.0, 45, 35, 30, fragile=True)
    print("\n--- Carrier Validation ---")
    calculate_shipping(p4, "DTDC")
    calculate_shipping(p4, "FedEx")
    calculate_shipping(p1, "SpeedPost")
    print("\n--- Best Carrier Suggestions ---")
    suggest_best_carrier(p1)
    suggest_best_carrier(p3)
    packing_suggestion([p1, p2, p5])
    shipment_report()

if __name__ == "__main__":
    main()
