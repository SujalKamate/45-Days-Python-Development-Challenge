# Real Estate Property Listing Manager with Search Filters

properties = {}
_pid = 1

TYPES = ["Apartment", "Villa", "Plot", "Commercial", "Office", "Shop"]
STATUSES = ["Available", "Sold", "Rented", "Under Negotiation"]

def add_property(title, prop_type, city, area_sqft, price, bedrooms=0,
                 amenities=None, contact=None):
    global _pid
    if prop_type not in TYPES:
        print(f"  Invalid type. Options: {TYPES}"); return None
    pid = f"PROP{_pid:04d}"; _pid += 1
    properties[pid] = {
        "title": title, "type": prop_type, "city": city,
        "area": area_sqft, "price": price, "bedrooms": bedrooms,
        "amenities": amenities or [], "contact": contact or "N/A",
        "status": "Available", "views": 0
    }
    print(f"  [{pid}] {title} | {prop_type} | {city} | {area_sqft} sqft | Rs.{price:,}")
    return pid

def search_by_price(min_price, max_price):
    results = [(pid, p) for pid, p in properties.items()
               if min_price <= p["price"] <= max_price and p["status"] == "Available"]
    print(f"\n  Price Rs.{min_price:,}–Rs.{max_price:,}: {len(results)} result(s)")
    for pid, p in sorted(results, key=lambda x: x[1]["price"]):
        print(f"  [{pid}] {p['title']:<28} {p['city']:<12} Rs.{p['price']:,}")
    return results

def search_by_city(city):
    results = [(pid, p) for pid, p in properties.items()
               if p["city"].lower() == city.lower()]
    print(f"\n  Properties in {city}: {len(results)}")
    for pid, p in results:
        print(f"  [{pid}] {p['title']:<28} {p['type']:<12} Rs.{p['price']:,} | {p['status']}")

def search_by_type(prop_type):
    results = [(pid, p) for pid, p in properties.items()
               if p["type"].lower() == prop_type.lower() and p["status"] == "Available"]
    print(f"\n  Available {prop_type}s: {len(results)}")
    for pid, p in results:
        print(f"  [{pid}] {p['title']:<28} {p['city']:<12} {p['area']} sqft | Rs.{p['price']:,}")

def filter_properties(city=None, prop_type=None, min_price=None, max_price=None,
                      min_area=None, bedrooms=None, status="Available"):
    results = []
    for pid, p in properties.items():
        if status and p["status"] != status: continue
        if city and p["city"].lower() != city.lower(): continue
        if prop_type and p["type"].lower() != prop_type.lower(): continue
        if min_price and p["price"] < min_price: continue
        if max_price and p["price"] > max_price: continue
        if min_area and p["area"] < min_area: continue
        if bedrooms and p["bedrooms"] != bedrooms: continue
        results.append((pid, p))
    print(f"\n  Filter Results ({len(results)} found):")
    for pid, p in results:
        print(f"  [{pid}] {p['title']:<28} {p['type']:<12} {p['city']:<10} Rs.{p['price']:,}")
    return results

def update_status(pid, new_status):
    if pid not in properties: print("  Property not found."); return
    if new_status not in STATUSES: print(f"  Invalid status."); return
    old = properties[pid]["status"]
    properties[pid]["status"] = new_status
    print(f"  [{pid}] Status: {old} → {new_status}")

def view_property(pid):
    if pid not in properties: print("  Not found."); return
    p = properties[pid]; p["views"] += 1
    print(f"\n{'='*50}")
    print(f"  [{pid}] {p['title']}")
    print(f"  Type     : {p['type']}   City: {p['city']}")
    print(f"  Area     : {p['area']} sqft  {'Beds: '+str(p['bedrooms']) if p['bedrooms'] else ''}")
    print(f"  Price    : Rs.{p['price']:,}")
    print(f"  Status   : {p['status']}   Views: {p['views']}")
    print(f"  Amenities: {', '.join(p['amenities']) or 'None'}")
    print(f"  Contact  : {p['contact']}")
    print(f"{'='*50}")

def listing_report():
    print(f"\n{'='*52}\n  PROPERTY LISTING REPORT\n{'='*52}")
    status_count = {s: 0 for s in STATUSES}
    for p in properties.values():
        status_count[p["status"]] += 1
    for s, c in status_count.items():
        print(f"  {s:<22}: {c}")
    available = [p for p in properties.values() if p["status"] == "Available"]
    if available:
        avg_price = sum(p["price"] for p in available) / len(available)
        print(f"\n  Available Listings : {len(available)}")
        print(f"  Avg Price          : Rs.{avg_price:,.0f}")
    cities = sorted(set(p["city"] for p in properties.values()))
    print(f"\n  Cities: {', '.join(cities)}")
    print(f"  Total Listings: {len(properties)}")
    print(f"{'='*52}")

def main():
    print("=== Real Estate Property Listing Manager ===")
    add_property("Green Meadows 3BHK",  "Apartment","Pune",      1200, 7500000, 3, ["Gym","Pool","Parking"])
    add_property("City Center Studio",  "Apartment","Mumbai",     450, 4200000, 1, ["Security","Lift"])
    add_property("Sunrise Villa 4BHK",  "Villa",    "Bangalore", 2800,18000000, 4, ["Garden","Pool","Garage"])
    add_property("Tech Park Office",    "Office",   "Hyderabad", 3000,15000000, 0, ["24/7 Power","Parking"])
    add_property("Corner Shop MG Road", "Shop",     "Pune",       600, 3500000, 0, ["Main Road","Parking"])
    add_property("Lake View 2BHK",      "Apartment","Pune",       900, 5800000, 2, ["Lake View","Gym"])
    add_property("Golden Heights Plot", "Plot",     "Bangalore", 1800, 9000000, 0, [])
    update_status("PROP0002", "Sold")
    update_status("PROP0004", "Under Negotiation")
    search_by_price(5000000, 10000000)
    search_by_city("Pune")
    filter_properties(prop_type="Apartment", max_price=8000000)
    view_property("PROP0001")
    listing_report()

if __name__ == "__main__":
    main()
