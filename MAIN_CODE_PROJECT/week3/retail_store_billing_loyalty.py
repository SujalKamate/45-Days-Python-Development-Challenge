# Retail Store Billing System with Loyalty Points

TAX_RATE = 0.12
POINTS_PER_RUPEE = 0.05
POINT_VALUE = 0.5   # 1 point = Rs.0.50

catalog = {
    "P001": ("Rice 5kg",        250, "Grocery"),
    "P002": ("Cooking Oil 1L",  120, "Grocery"),
    "P003": ("Soap Pack (6)",    90, "Personal Care"),
    "P004": ("Shampoo 200ml",   180, "Personal Care"),
    "P005": ("Notebook 200pg",   60, "Stationery"),
    "P006": ("Biscuits (pack)",  40, "Snacks"),
    "P007": ("Juice 1L",         75, "Beverages"),
}
customers = {}
transactions = []
_tid = 1

def register_customer(name, phone):
    if phone in customers:
        print(f"  {customers[phone]['name']} is already registered.")
        return
    customers[phone] = {"name": name, "points": 0, "total_spent": 0, "visits": 0}
    print(f"  Customer registered: {name} | Phone: {phone}")

def show_catalog():
    print("\n  Catalog:")
    for pid, (name, price, cat) in catalog.items():
        print(f"  {pid} | {name:<22} Rs.{price:<6} [{cat}]")

def create_bill(phone, cart, redeem_points=0):
    global _tid
    if phone not in customers:
        print("  Customer not found.")
        return None
    c = customers[phone]
    invalid = [p for p in cart if p not in catalog]
    if invalid:
        print(f"  Unknown product codes: {invalid}")
        return None
    subtotal = sum(catalog[pid][1] * qty for pid, qty in cart.items())
    tax      = round(subtotal * TAX_RATE, 2)
    gross    = round(subtotal + tax, 2)
    redeem   = 0
    if redeem_points > 0:
        max_redeem = min(redeem_points, c["points"])
        redeem_value = round(max_redeem * POINT_VALUE, 2)
        redeem_value = min(redeem_value, gross)
        redeem       = max_redeem
        points_used  = redeem
    else:
        redeem_value = 0
        points_used  = 0
    payable   = round(gross - redeem_value, 2)
    pts_earned = int(payable * POINTS_PER_RUPEE)
    c["points"]      = c["points"] - points_used + pts_earned
    c["total_spent"] += payable
    c["visits"]      += 1
    tid = f"TXN{_tid:05d}"
    _tid += 1
    txn = {"tid": tid, "phone": phone, "cart": cart, "subtotal": subtotal,
           "tax": tax, "gross": gross, "redeemed": redeem_value,
           "payable": payable, "pts_earned": pts_earned}
    transactions.append(txn)
    print(f"\n{'='*42}")
    print(f"  RECEIPT — {tid} | {c['name']}")
    print(f"{'='*42}")
    for pid, qty in cart.items():
        name, price, _ = catalog[pid]
        print(f"  {name:<22} x{qty}  Rs.{price*qty}")
    print(f"  {'Subtotal':<26} Rs.{subtotal:.2f}")
    print(f"  {'Tax(12%)':<26} Rs.{tax:.2f}")
    print(f"  {'Gross':<26} Rs.{gross:.2f}")
    if redeem_value:
        print(f"  {'Points Redeemed':<26} -Rs.{redeem_value:.2f} ({points_used} pts)")
    print(f"  {'PAYABLE':<26} Rs.{payable:.2f}")
    print(f"  {'Loyalty Points Earned':<26} +{pts_earned}")
    print(f"  {'Balance Points':<26} {c['points']}")
    print(f"{'='*42}")
    return tid

def customer_summary(phone):
    if phone not in customers:
        print("  Customer not found.")
        return
    c = customers[phone]
    txns = [t for t in transactions if t["phone"] == phone]
    print(f"\n  Customer: {c['name']} | {phone}")
    print(f"  Total Visits  : {c['visits']}")
    print(f"  Total Spent   : Rs.{c['total_spent']:.2f}")
    print(f"  Loyalty Points: {c['points']}  (worth Rs.{c['points']*POINT_VALUE:.2f})")

def main():
    print("=== Retail Store Billing System ===")
    register_customer("Amit Sharma",  "9876543210")
    register_customer("Priya Nair",   "9123456789")
    register_customer("Ravi Kumar",   "9011223344")
    show_catalog()
    create_bill("9876543210", {"P001":1, "P002":2, "P006":3})
    create_bill("9876543210", {"P003":2, "P004":1, "P007":2}, redeem_points=20)
    create_bill("9123456789", {"P001":2, "P005":3, "P007":1})
    create_bill("9011223344", {"P002":1, "P006":5, "P003":1})
    customer_summary("9876543210")
    customer_summary("9123456789")

if __name__ == "__main__":
    main()
