# Courier Tracking System with Shipment History

import random, string
from datetime import datetime

shipments = {}

CHECKPOINTS = [
    "Order Placed", "Picked Up", "In Transit - Origin Hub",
    "In Transit - Mid Hub", "Arrived at Destination Hub",
    "Out for Delivery", "Delivered"
]

def create_shipment(sender, receiver, origin, destination, weight_kg, service="Standard"):
    tracking_id = "CUR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    charges = round((10 + weight_kg * 15) * (1.2 if service == "Express" else 1.0), 2)
    shipments[tracking_id] = {
        "sender": sender, "receiver": receiver,
        "origin": origin, "destination": destination,
        "weight": weight_kg, "service": service,
        "charges": charges, "status": "Order Placed",
        "status_index": 0,
        "history": [{"status": "Order Placed",
                     "location": origin,
                     "time": datetime.now().strftime("%Y-%m-%d %H:%M")}]
    }
    print(f"  Shipment created: [{tracking_id}] | {sender} → {receiver} | Rs.{charges}")
    return tracking_id

def update_shipment(tid, location=None):
    if tid not in shipments:
        print("  Tracking ID not found.")
        return
    s = shipments[tid]
    if s["status_index"] >= len(CHECKPOINTS) - 1:
        print(f"  [{tid}] Already delivered.")
        return
    s["status_index"] += 1
    s["status"] = CHECKPOINTS[s["status_index"]]
    loc = location or s["destination"]
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
    s["history"].append({"status": s["status"], "location": loc, "time": ts})
    print(f"  [{tid}] → {s['status']} at {loc}")

def track_shipment(tid):
    if tid not in shipments:
        print("  Tracking ID not found.")
        return
    s = shipments[tid]
    print(f"\n{'='*50}")
    print(f"  TRACKING: {tid}")
    print(f"  {s['sender']} → {s['receiver']}")
    print(f"  Route   : {s['origin']} → {s['destination']}")
    print(f"  Weight  : {s['weight']} kg | Service: {s['service']} | Charges: Rs.{s['charges']}")
    print(f"  Status  : {s['status']}")
    print(f"{'─'*50}")
    print("  Movement History:")
    for i, h in enumerate(s["history"]):
        marker = "●" if i == len(s["history"]) - 1 else "○"
        print(f"  {marker} [{h['time']}] {h['status']:<30} @ {h['location']}")
    print(f"{'='*50}")

def delivery_report():
    print(f"\n{'='*48}")
    print("  DELIVERY REPORT")
    print(f"{'='*48}")
    delivered   = sum(1 for s in shipments.values() if s["status"] == "Delivered")
    in_transit  = sum(1 for s in shipments.values() if "Transit" in s["status"])
    out_del     = sum(1 for s in shipments.values() if s["status"] == "Out for Delivery")
    total_rev   = sum(s["charges"] for s in shipments.values())
    print(f"  Total Shipments  : {len(shipments)}")
    print(f"  Delivered        : {delivered}")
    print(f"  In Transit       : {in_transit}")
    print(f"  Out for Delivery : {out_del}")
    print(f"  Pending          : {len(shipments) - delivered}")
    print(f"  Total Revenue    : Rs.{total_rev:.2f}")
    print(f"\n  {'Tracking ID':<15} {'Service':<10} {'Status':<30} {'Rs.'}")
    for tid, s in shipments.items():
        print(f"  {tid:<15} {s['service']:<10} {s['status']:<30} {s['charges']}")
    print(f"{'='*48}")

def main():
    print("=== Courier Tracking System ===")
    t1 = create_shipment("Arjun Mehta", "Pooja Nair",    "Delhi",   "Mumbai",    2.5, "Express")
    t2 = create_shipment("Rohit Sen",   "Kavya Iyer",    "Chennai", "Bangalore", 1.0, "Standard")
    t3 = create_shipment("Sunita Rao",  "Vikram Das",    "Kolkata", "Hyderabad", 5.0, "Standard")
    t4 = create_shipment("Anil Sharma", "Deepa Reddy",   "Pune",    "Ahmedabad", 0.5, "Express")
    for _ in range(5): update_shipment(t1, "Transit Hub")
    update_shipment(t1, "Mumbai")
    for _ in range(3): update_shipment(t2, "Bangalore Hub")
    for _ in range(2): update_shipment(t3, "Hyderabad")
    track_shipment(t1)
    track_shipment(t2)
    delivery_report()

if __name__ == "__main__":
    main()
