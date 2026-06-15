# Bus Route Management System with Fare Calculation

FARE_PER_KM = 1.5
BASE_FARE = 10.0
routes = {}
bookings = {}
_bid = 1

def add_route(rid, name, stops):
    """stops = list of (stop_name, cumulative_km_from_start)"""
    routes[rid] = {"name": name, "stops": stops, "bookings": []}
    print(f"  Route [{rid}] '{name}' added — {len(stops)} stops")

def display_routes():
    print("\n--- Available Routes ---")
    for rid, r in routes.items():
        path = " → ".join(s[0] for s in r["stops"])
        dist = r["stops"][-1][1]
        print(f"  [{rid}] {r['name']}  ({dist} km)  {path}")

def display_stops(rid):
    if rid not in routes:
        print("  Route not found.")
        return
    print(f"\n  Stops for [{rid}] {routes[rid]['name']}:")
    for i, (stop, km) in enumerate(routes[rid]["stops"]):
        print(f"    {i}. {stop:<22} {km} km")

def calc_fare(rid, from_i, to_i):
    stops = routes[rid]["stops"]
    if from_i >= to_i:
        return 0
    dist = stops[to_i][1] - stops[from_i][1]
    return round(BASE_FARE + FARE_PER_KM * dist, 2)

def book_ticket(passenger, rid, from_i, to_i):
    global _bid
    if rid not in routes:
        print("  Route not found.")
        return
    fare = calc_fare(rid, from_i, to_i)
    if fare == 0:
        print("  Invalid stop selection.")
        return
    stops = routes[rid]["stops"]
    bid = f"BUS{_bid:04d}"
    _bid += 1
    record = {
        "passenger": passenger, "route": rid,
        "from": stops[from_i][0], "to": stops[to_i][0], "fare": fare
    }
    bookings[bid] = record
    routes[rid]["bookings"].append(bid)
    print(f"\n  Ticket: {bid}")
    print(f"  Passenger : {passenger}")
    print(f"  Route     : {routes[rid]['name']}")
    print(f"  From      : {stops[from_i][0]}")
    print(f"  To        : {stops[to_i][0]}")
    dist = stops[to_i][1] - stops[from_i][1]
    print(f"  Distance  : {dist} km  |  Fare: Rs.{fare}")

def route_summary(rid):
    if rid not in routes:
        print("  Route not found.")
        return
    r = routes[rid]
    rev = sum(bookings[b]["fare"] for b in r["bookings"] if b in bookings)
    print(f"\n  Route [{rid}] {r['name']}:")
    print(f"    Total Bookings : {len(r['bookings'])}")
    print(f"    Total Revenue  : Rs.{rev:.2f}")

def all_bookings_report():
    print(f"\n{'='*50}")
    print("  ALL BOOKINGS REPORT")
    print(f"{'='*50}")
    for bid, b in bookings.items():
        rname = routes[b["route"]]["name"]
        print(f"  {bid} | {b['passenger']:<15} | {b['from']} → {b['to']} | Rs.{b['fare']}")
    total = sum(b["fare"] for b in bookings.values())
    print(f"\n  Total Bookings : {len(bookings)}")
    print(f"  Total Revenue  : Rs.{total:.2f}")
    print(f"{'='*50}")

def main():
    print("=== Bus Route Management System ===")
    add_route("R01", "City Express",
              [("Central Stand", 0), ("Market", 5), ("Hospital", 12),
               ("University", 18), ("Airport", 30)])
    add_route("R02", "Suburb Link",
              [("Old Town", 0), ("Park", 7), ("Tech Park", 15), ("Mall", 22)])
    display_routes()
    display_stops("R01")
    book_ticket("Ajay Kumar",  "R01", 0, 3)
    book_ticket("Meena Sharma","R01", 1, 4)
    book_ticket("Pooja Rao",   "R02", 0, 2)
    book_ticket("Ravi Nair",   "R02", 1, 3)
    route_summary("R01")
    route_summary("R02")
    all_bookings_report()

if __name__ == "__main__":
    main()
