# School Bus Tracking Simulator with Route Monitoring

import time as _time
from datetime import date

buses   = {}
routes  = {}
students= {}
_bid = _rid = _sid = 1

def add_route(name, stops):
    global _rid
    rid = f"RTE{_rid:03d}"; _rid += 1
    routes[rid] = {"name":name, "stops":stops, "buses":[], "total_distance":0}
    dist = 0
    for i in range(1, len(stops)):
        dist += stops[i].get("dist_from_prev", 2)
    routes[rid]["total_distance"] = dist
    print(f"  [{rid}] {name} | {len(stops)} stops | ~{dist} km")
    return rid

def add_bus(number, driver, capacity, route_id):
    global _bid
    if route_id not in routes: print("  Route not found."); return None
    bid = f"BUS{_bid:03d}"; _bid += 1
    buses[bid] = {
        "number":number, "driver":driver, "capacity":capacity,
        "route":route_id, "current_stop_idx":0,
        "status":"Depot", "students_onboard":[], "trips_today":0
    }
    routes[route_id]["buses"].append(bid)
    print(f"  [{bid}] Bus {number} | Driver: {driver} | Cap: {capacity} | Route: {routes[route_id]['name']}")
    return bid

def register_student(name, stop_name, route_id):
    global _sid
    if route_id not in routes: print("  Route not found."); return None
    stop_names = [s["name"] for s in routes[route_id]["stops"]]
    if stop_name not in stop_names: print(f"  Stop '{stop_name}' not on route."); return None
    sid = f"STU{_sid:04d}"; _sid += 1
    students[sid] = {"name":name, "stop":stop_name, "route":route_id, "picked_up":False}
    print(f"  [{sid}] {name} | Stop: {stop_name}")
    return sid

def start_trip(bid):
    if bid not in buses: print("  Bus not found."); return
    b = buses[bid]
    b["status"] = "En Route"
    b["current_stop_idx"] = 0
    b["trips_today"] += 1
    print(f"  [{bid}] Bus {b['number']} started trip #{b['trips_today']} on {routes[b['route']]['name']}")

def advance_stop(bid):
    if bid not in buses: return
    b    = buses[bid]
    rte  = routes[b["route"]]
    stops= rte["stops"]
    if b["current_stop_idx"] >= len(stops) - 1:
        b["status"] = "Depot"
        print(f"  [{bid}] Bus {b['number']} completed route. Back to depot.")
        return
    b["current_stop_idx"] += 1
    current_stop = stops[b["current_stop_idx"]]["name"]
    b["status"] = f"At {current_stop}"
    pickups = [sid for sid, s in students.items()
               if s["stop"] == current_stop and s["route"] == b["route"] and not s["picked_up"]]
    for sid in pickups:
        if len(b["students_onboard"]) < b["capacity"]:
            b["students_onboard"].append(sid)
            students[sid]["picked_up"] = True
            print(f"    Picked up: {students[sid]['name']}")
    progress = (b["current_stop_idx"] + 1) / len(stops) * 100
    print(f"  [{bid}] Bus {b['number']} → {current_stop} | Onboard: {len(b['students_onboard'])} | Progress: {progress:.0f}%")

def bus_status(bid):
    if bid not in buses: return
    b   = buses[bid]
    rte = routes[b["route"]]
    print(f"\n  Bus Status [{bid}]")
    print(f"  Number   : {b['number']} | Driver: {b['driver']}")
    print(f"  Route    : {rte['name']} | Status: {b['status']}")
    print(f"  Onboard  : {len(b['students_onboard'])}/{b['capacity']}")
    print(f"  Trips    : {b['trips_today']} today")
    stops = rte["stops"]
    for i, stop in enumerate(stops):
        marker = "●" if i == b["current_stop_idx"] else ("✔" if i < b["current_stop_idx"] else "○")
        print(f"    {marker} {stop['name']}")

def transport_report():
    print(f"\n{'='*50}\n  SCHOOL BUS TRANSPORT REPORT\n{'='*50}")
    print(f"  Buses    : {len(buses)} | Routes: {len(routes)} | Students: {len(students)}")
    picked_up = sum(1 for s in students.values() if s["picked_up"])
    print(f"  Picked Up: {picked_up}/{len(students)}")
    for bid, b in buses.items():
        rte = routes[b["route"]]
        print(f"  [{bid}] {b['number']:<8} {rte['name']:<20} {b['status']}")
    print(f"{'='*50}")

def main():
    print("=== School Bus Tracking Simulator ===")
    r1 = add_route("North Route", [
        {"name":"School Gate",    "dist_from_prev":0},
        {"name":"Sector 15",      "dist_from_prev":3},
        {"name":"Civil Lines",    "dist_from_prev":4},
        {"name":"Model Town",     "dist_from_prev":2},
        {"name":"Railway Colony", "dist_from_prev":5},
    ])
    r2 = add_route("South Route", [
        {"name":"School Gate", "dist_from_prev":0},
        {"name":"Ashok Nagar", "dist_from_prev":4},
        {"name":"Green Park",  "dist_from_prev":3},
        {"name":"Lajpat Nagar","dist_from_prev":3},
    ])
    b1 = add_bus("UP32-1234", "Ram Singh",   40, r1)
    b2 = add_bus("UP32-5678", "Shyam Kumar", 35, r2)
    s1 = register_student("Aarav Mehta",  "Sector 15",      r1)
    s2 = register_student("Bhavna Singh", "Model Town",     r1)
    s3 = register_student("Chetan Rao",   "Railway Colony", r1)
    s4 = register_student("Divya Nair",   "Ashok Nagar",    r2)
    s5 = register_student("Eshan Kumar",  "Green Park",     r2)
    start_trip(b1)
    for _ in range(3): advance_stop(b1)
    start_trip(b2)
    for _ in range(2): advance_stop(b2)
    bus_status(b1)
    transport_report()

if __name__ == "__main__":
    main()
