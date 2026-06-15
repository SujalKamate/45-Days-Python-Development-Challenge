# Food Delivery Order Manager with Delivery Status Updates

from datetime import datetime

MENU = {
    "Burger": 120, "Pizza": 250, "Biryani": 200,
    "Noodles": 150, "Sandwich": 100, "Cold Drink": 50,
    "Fries": 80, "Paneer Roll": 130, "Dal Rice": 110, "Ice Cream": 70
}
TAX_RATE = 0.05
DELIVERY_FEE = 30
STATUS_FLOW = ["Placed", "Confirmed", "Preparing", "Out for Delivery", "Delivered"]

orders = {}
_oid = 1

def place_order(customer, address, items_dict):
    global _oid
    invalid = [i for i in items_dict if i not in MENU]
    if invalid:
        print(f"  Items not on menu: {invalid}")
        return None
    oid = f"ORD{_oid:04d}"
    _oid += 1
    subtotal = sum(MENU[item] * qty for item, qty in items_dict.items())
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax + DELIVERY_FEE, 2)
    orders[oid] = {
        "customer": customer, "address": address,
        "items": items_dict, "subtotal": subtotal,
        "tax": tax, "delivery_fee": DELIVERY_FEE, "total": total,
        "status": "Placed", "status_index": 0,
        "placed_at": datetime.now().strftime("%H:%M:%S"),
        "history": [("Placed", datetime.now().strftime("%H:%M:%S"))]
    }
    print(f"  Order [{oid}] placed for {customer} | Total: Rs.{total}")
    return oid

def update_status(oid):
    if oid not in orders:
        print("  Order not found.")
        return
    o = orders[oid]
    if o["status_index"] >= len(STATUS_FLOW) - 1:
        print(f"  Order [{oid}] already Delivered.")
        return
    o["status_index"] += 1
    o["status"] = STATUS_FLOW[o["status_index"]]
    ts = datetime.now().strftime("%H:%M:%S")
    o["history"].append((o["status"], ts))
    print(f"  [{oid}] Status → {o['status']} at {ts}")

def track_order(oid):
    if oid not in orders:
        print("  Order not found.")
        return
    o = orders[oid]
    print(f"\n  Tracking Order [{oid}] — {o['customer']}")
    for i, stage in enumerate(STATUS_FLOW):
        marker = "✔" if i <= o["status_index"] else "○"
        print(f"    {marker} {stage}")
    print(f"  Current: {o['status']}")

def order_bill(oid):
    if oid not in orders:
        print("  Order not found.")
        return
    o = orders[oid]
    print(f"\n{'='*42}")
    print(f"  BILL — Order {oid} | {o['customer']}")
    print(f"{'='*42}")
    for item, qty in o["items"].items():
        print(f"  {item:<18} x{qty}  Rs.{MENU[item]*qty}")
    print(f"  {'Subtotal':<22} Rs.{o['subtotal']}")
    print(f"  {'Tax (5%)':<22} Rs.{o['tax']}")
    print(f"  {'Delivery Fee':<22} Rs.{o['delivery_fee']}")
    print(f"  {'TOTAL':<22} Rs.{o['total']}")
    print(f"{'='*42}")

def customer_history(customer):
    print(f"\n  Order History — {customer}")
    cust_orders = [(oid, o) for oid, o in orders.items() if o["customer"] == customer]
    if not cust_orders:
        print("  No orders found.")
        return
    for oid, o in cust_orders:
        print(f"  [{oid}] Rs.{o['total']} | {o['status']} | Placed at {o['placed_at']}")
    total_spent = sum(o["total"] for _, o in cust_orders)
    print(f"  Total Spent: Rs.{total_spent:.2f}")

def main():
    print("=== Food Delivery Order Manager ===")
    o1 = place_order("Ravi Kumar", "12 MG Road", {"Burger": 2, "Fries": 1, "Cold Drink": 2})
    o2 = place_order("Sita Devi",  "45 Park Ave", {"Biryani": 1, "Cold Drink": 1})
    o3 = place_order("Arjun S",   "7 Lake View", {"Pizza": 1, "Ice Cream": 2})
    for _ in range(3): update_status(o1)
    for _ in range(2): update_status(o2)
    track_order(o1)
    track_order(o2)
    order_bill(o1)
    order_bill(o3)
    place_order("Ravi Kumar", "12 MG Road", {"Paneer Roll": 2, "Dal Rice": 1})
    customer_history("Ravi Kumar")

if __name__ == "__main__":
    main()
