# Asset Tracking System with Depreciation Calculator

from datetime import date

DEPRECIATION_RATES = {
    "Electronics":  0.25,
    "Furniture":    0.10,
    "Vehicle":      0.20,
    "Machinery":    0.15,
    "Building":     0.05,
    "IT Equipment": 0.33,
}
assets = {}
_aid = 1

def add_asset(name, category, cost, purchase_date_str, location="HQ"):
    global _aid
    if category not in DEPRECIATION_RATES:
        print(f"  Unknown category. Available: {list(DEPRECIATION_RATES.keys())}")
        return None
    aid = f"AST{_aid:04d}"
    _aid += 1
    assets[aid] = {
        "name": name, "category": category, "cost": cost,
        "purchase_date": date.fromisoformat(purchase_date_str),
        "location": location, "disposed": False
    }
    print(f"  [{aid}] {name} | {category} | Rs.{cost:,.0f} | Purchased: {purchase_date_str}")
    return aid

def calc_depreciation(aid, ref_date=None):
    if aid not in assets:
        return None
    a = assets[aid]
    ref = ref_date or date.today()
    years = (ref - a["purchase_date"]).days / 365.25
    rate  = DEPRECIATION_RATES[a["category"]]
    book_value = a["cost"] * ((1 - rate) ** years)
    total_dep  = a["cost"] - book_value
    annual_dep = a["cost"] * rate
    return {
        "years": round(years, 2),
        "rate": rate,
        "annual_depreciation": round(annual_dep, 2),
        "total_depreciation":  round(total_dep, 2),
        "book_value":          round(max(book_value, 0), 2)
    }

def display_asset(aid):
    if aid not in assets:
        print("  Asset not found.")
        return
    a = assets[aid]
    d = calc_depreciation(aid)
    print(f"\n  Asset: [{aid}] {a['name']}")
    print(f"  Category      : {a['category']}")
    print(f"  Purchase Cost : Rs.{a['cost']:,.2f}")
    print(f"  Location      : {a['location']}")
    print(f"  Purchased On  : {a['purchase_date']}")
    print(f"  Age           : {d['years']} years")
    print(f"  Dep. Rate     : {d['rate']*100:.0f}% p.a.")
    print(f"  Annual Dep.   : Rs.{d['annual_depreciation']:,.2f}")
    print(f"  Total Dep.    : Rs.{d['total_depreciation']:,.2f}")
    print(f"  Book Value    : Rs.{d['book_value']:,.2f}")

def dispose_asset(aid):
    if aid not in assets:
        print("  Asset not found.")
        return
    assets[aid]["disposed"] = True
    print(f"  Asset [{aid}] {assets[aid]['name']} marked as disposed.")

def assets_by_category():
    print("\n--- Assets by Category ---")
    from collections import defaultdict
    grouped = defaultdict(list)
    for aid, a in assets.items():
        grouped[a["category"]].append(aid)
    for cat, aids in grouped.items():
        print(f"\n  [{cat}]")
        for aid in aids:
            a = assets[aid]
            d = calc_depreciation(aid)
            status = "Disposed" if a["disposed"] else "Active"
            print(f"    {aid} | {a['name']:<20} | BV: Rs.{d['book_value']:>10,.2f} | {status}")

def valuation_report():
    print(f"\n{'='*52}")
    print("  ASSET VALUATION REPORT")
    print(f"{'='*52}")
    total_cost   = sum(a["cost"] for a in assets.values() if not a["disposed"])
    total_bv     = sum(calc_depreciation(aid)["book_value"]
                       for aid, a in assets.items() if not a["disposed"])
    total_dep    = total_cost - total_bv
    print(f"  Total Assets     : {len(assets)}")
    print(f"  Active Assets    : {sum(1 for a in assets.values() if not a['disposed'])}")
    print(f"  Original Cost    : Rs.{total_cost:>12,.2f}")
    print(f"  Total Deprec.    : Rs.{total_dep:>12,.2f}")
    print(f"  Net Book Value   : Rs.{total_bv:>12,.2f}")
    pct_dep = (total_dep / total_cost * 100) if total_cost else 0
    print(f"  Depreciated By   : {pct_dep:.1f}%")
    print(f"{'='*52}")

def main():
    print("=== Asset Tracking System ===")
    add_asset("Dell Laptop",      "IT Equipment", 75000,  "2022-01-15", "Head Office")
    add_asset("Office Chair Set", "Furniture",    45000,  "2021-06-01", "Floor 2")
    add_asset("Company SUV",      "Vehicle",      850000, "2020-03-10", "Garage")
    add_asset("CNC Machine",      "Machinery",    320000, "2019-11-20", "Factory")
    add_asset("Air Conditioner",  "Electronics",  38000,  "2023-05-05", "Server Room")
    add_asset("Projector",        "Electronics",  25000,  "2021-08-15", "Board Room")
    print()
    for aid in list(assets.keys())[:3]:
        display_asset(aid)
    dispose_asset("AST0006")
    assets_by_category()
    valuation_report()

if __name__ == "__main__":
    main()
