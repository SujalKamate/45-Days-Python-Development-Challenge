# Pharmacy Inventory System with Expiry Date Monitoring

from datetime import date, timedelta

ALERT_DAYS   = 30
LOW_STOCK_QTY = 20
inventory = {}
sales_log = []
_mid = 1

def add_medicine(name, batch, category, qty, unit_price, expiry_str, supplier):
    global _mid
    mid    = f"MED{_mid:04d}"; _mid += 1
    expiry = date.fromisoformat(expiry_str)
    inventory[mid] = {
        "name":name, "batch":batch, "category":category,
        "qty":qty, "unit_price":unit_price, "expiry":expiry,
        "supplier":supplier, "total_sold":0
    }
    days_left = (expiry - date.today()).days
    status = "⚠EXPIRING SOON" if days_left <= ALERT_DAYS else ("✗EXPIRED" if days_left < 0 else "✔OK")
    print(f"  [{mid}] {name} | Batch:{batch} | {qty} units @ Rs.{unit_price} | Exp:{expiry} {status}")
    return mid

def sell_medicine(mid, qty_sold, customer="Walk-in"):
    if mid not in inventory: print("  Medicine not found."); return False
    m = inventory[mid]
    today = date.today()
    if m["expiry"] < today: print(f"  ✗ CANNOT SELL: {m['name']} is EXPIRED!"); return False
    if m["qty"] < qty_sold: print(f"  Insufficient stock. Available: {m['qty']}"); return False
    m["qty"]       -= qty_sold
    m["total_sold"] += qty_sold
    amount = round(qty_sold * m["unit_price"], 2)
    sales_log.append({"mid":mid,"name":m["name"],"qty":qty_sold,
                      "amount":amount,"customer":customer,"date":today})
    print(f"  Sold {qty_sold}x {m['name']} = Rs.{amount} | Remaining: {m['qty']}")
    if m["qty"] <= LOW_STOCK_QTY:
        print(f"  ⚠ LOW STOCK ALERT: {m['name']} has only {m['qty']} units left!")
    return True

def restock(mid, qty, new_price=None):
    if mid not in inventory: print("  Not found."); return
    inventory[mid]["qty"] += qty
    if new_price: inventory[mid]["unit_price"] = new_price
    print(f"  [{mid}] {inventory[mid]['name']} restocked +{qty} | New qty: {inventory[mid]['qty']}")

def expiry_alerts(ref_date=None):
    today = ref_date or date.today()
    print(f"\n--- Expiry Alerts (as of {today}) ---")
    expired  = [(mid, m) for mid, m in inventory.items() if m["expiry"] < today]
    expiring = [(mid, m) for mid, m in inventory.items()
                if today <= m["expiry"] <= today + timedelta(days=ALERT_DAYS)]
    if expired:
        print(f"  EXPIRED ({len(expired)}):")
        for mid, m in expired:
            print(f"    [{mid}] {m['name']} (Batch:{m['batch']}) — Expired {m['expiry']}")
    if expiring:
        print(f"  EXPIRING WITHIN {ALERT_DAYS} DAYS ({len(expiring)}):")
        for mid, m in expiring:
            days = (m["expiry"] - today).days
            print(f"    [{mid}] {m['name']} — {days} days left | Stock: {m['qty']}")
    if not expired and not expiring:
        print("  No expiry issues found.")

def low_stock_report():
    print("\n--- Low Stock Report ---")
    low = [(mid, m) for mid, m in inventory.items() if m["qty"] <= LOW_STOCK_QTY]
    if not low: print("  All stocks adequate."); return
    for mid, m in sorted(low, key=lambda x: x[1]["qty"]):
        print(f"  [{mid}] {m['name']:<22} Stock: {m['qty']:>4} | Supplier: {m['supplier']}")

def inventory_report():
    print(f"\n{'='*58}\n  PHARMACY INVENTORY REPORT\n{'='*58}")
    total_value = sum(m["qty"] * m["unit_price"] for m in inventory.values())
    total_sales = sum(s["amount"] for s in sales_log)
    cat_counts  = {}
    for m in inventory.values():
        cat_counts[m["category"]] = cat_counts.get(m["category"], 0) + 1
    print(f"  Total Medicines : {len(inventory)}")
    print(f"  Inventory Value : Rs.{total_value:,.2f}")
    print(f"  Total Sales     : Rs.{total_sales:,.2f}")
    print(f"\n  {'ID':<8} {'Name':<22} {'Qty':>5} {'Price':>8} {'Sold':>6} {'Expiry'}")
    for mid, m in inventory.items():
        print(f"  {mid:<8} {m['name']:<22} {m['qty']:>5} Rs.{m['unit_price']:>6.2f} {m['total_sold']:>6} {m['expiry']}")
    print(f"{'='*58}")

def main():
    print("=== Pharmacy Inventory System ===")
    today = date.today()
    add_medicine("Paracetamol 500mg", "B001", "Analgesic",  200, 2.50,  str(today+timedelta(days=365)), "MedCo")
    add_medicine("Amoxicillin 250mg", "B002", "Antibiotic", 150, 8.00,  str(today+timedelta(days=90)),  "PharmX")
    add_medicine("Ibuprofen 400mg",   "B003", "Analgesic",  100, 5.50,  str(today+timedelta(days=20)),  "MedCo")
    add_medicine("Cetirizine 10mg",   "B004", "Antihistamine",80,3.75,  str(today+timedelta(days=10)),  "AllerGen")
    add_medicine("Vitamin C 500mg",   "B005", "Supplement",  50, 6.00,  str(today+timedelta(days=180)), "VitaPlus")
    add_medicine("Expired Cough Syrup","B006","Cough",       30, 45.00, str(today-timedelta(days=5)),   "OldPharma")
    sell_medicine("MED0001", 50, "Amit Sharma")
    sell_medicine("MED0002", 80, "Clinic A")
    sell_medicine("MED0005", 10, "Walk-in")
    sell_medicine("MED0006",  5, "Customer")   # expired
    sell_medicine("MED0003", 95, "Hospital")   # low stock trigger
    restock("MED0003", 100)
    expiry_alerts()
    low_stock_report()
    inventory_report()

if __name__ == "__main__":
    main()
