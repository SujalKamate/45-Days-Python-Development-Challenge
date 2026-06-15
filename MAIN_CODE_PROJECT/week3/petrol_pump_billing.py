# Petrol Pump Billing System with Fuel Analytics

from datetime import date

FUEL_PRICES = {"Petrol": 106.50, "Diesel": 92.30, "CNG": 84.00, "Premium Petrol": 115.00}
transactions = []
daily_totals = {}

def record_sale(vehicle_no, fuel_type, litres, payment_mode="Cash", sale_date=None):
    if fuel_type not in FUEL_PRICES:
        print(f"  Unknown fuel type: {fuel_type}")
        return None
    if litres <= 0:
        print("  Litres must be positive.")
        return None
    d = sale_date or date.today()
    price = FUEL_PRICES[fuel_type]
    amount = round(price * litres, 2)
    txn = {
        "vehicle": vehicle_no, "fuel": fuel_type, "litres": litres,
        "price_per_litre": price, "amount": amount,
        "payment": payment_mode, "date": d
    }
    transactions.append(txn)
    key = str(d)
    if key not in daily_totals:
        daily_totals[key] = {"amount": 0, "litres": 0, "count": 0}
    daily_totals[key]["amount"] += amount
    daily_totals[key]["litres"] += litres
    daily_totals[key]["count"]  += 1
    print(f"  {vehicle_no} | {fuel_type} | {litres}L × Rs.{price} = Rs.{amount:.2f} | {payment_mode}")
    return txn

def print_receipt(txn):
    if not txn:
        return
    print(f"\n{'='*40}")
    print("  FUEL RECEIPT")
    print(f"{'='*40}")
    print(f"  Vehicle      : {txn['vehicle']}")
    print(f"  Fuel Type    : {txn['fuel']}")
    print(f"  Litres       : {txn['litres']} L")
    print(f"  Rate         : Rs.{txn['price_per_litre']:.2f}/L")
    print(f"  Amount       : Rs.{txn['amount']:.2f}")
    print(f"  Payment      : {txn['payment']}")
    print(f"  Date         : {txn['date']}")
    print(f"{'='*40}")

def daily_summary(sale_date=None):
    d = str(sale_date or date.today())
    if d not in daily_totals:
        print(f"  No sales recorded for {d}.")
        return
    dt = daily_totals[d]
    print(f"\n  Daily Summary — {d}")
    print(f"  Transactions : {dt['count']}")
    print(f"  Total Litres : {dt['litres']:.2f} L")
    print(f"  Total Revenue: Rs.{dt['amount']:.2f}")

def fuel_analytics():
    print(f"\n{'='*48}")
    print("  FUEL ANALYTICS REPORT")
    print(f"{'='*48}")
    fuel_stats = {f: {"litres": 0, "revenue": 0, "count": 0} for f in FUEL_PRICES}
    for t in transactions:
        fs = fuel_stats[t["fuel"]]
        fs["litres"]  += t["litres"]
        fs["revenue"] += t["amount"]
        fs["count"]   += 1
    total_rev = sum(fs["revenue"] for fs in fuel_stats.values())
    print(f"  {'Fuel':<18} {'Sales':>5} {'Litres':>8} {'Revenue':>12} {'Share':>7}")
    print(f"  {'-'*52}")
    for fuel, fs in sorted(fuel_stats.items(), key=lambda x: -x[1]["revenue"]):
        pct = (fs["revenue"] / total_rev * 100) if total_rev else 0
        print(f"  {fuel:<18} {fs['count']:>5} {fs['litres']:>8.1f} Rs.{fs['revenue']:>10.2f} {pct:>6.1f}%")
    payment_modes = {}
    for t in transactions:
        payment_modes[t["payment"]] = payment_modes.get(t["payment"], 0) + t["amount"]
    print(f"\n  Payment Mode Breakdown:")
    for mode, amt in payment_modes.items():
        print(f"    {mode:<15}: Rs.{amt:.2f}")
    print(f"\n  Total Revenue : Rs.{total_rev:.2f}")
    print(f"{'='*48}")

def main():
    print("=== Petrol Pump Billing System ===")
    today = date.today()
    t1 = record_sale("MH12AB1234", "Petrol",         35.5, "UPI",   today)
    t2 = record_sale("DL05CD5678", "Diesel",         60.0, "Card",  today)
    t3 = record_sale("KA03EF9012", "CNG",            20.0, "Cash",  today)
    t4 = record_sale("GJ07GH3456", "Premium Petrol", 40.0, "Cash",  today)
    t5 = record_sale("MH12AB1234", "Petrol",         15.0, "UPI",   today)
    t6 = record_sale("TN22IJ7890", "Diesel",         80.0, "Card",  today)
    print_receipt(t1)
    daily_summary(today)
    fuel_analytics()

if __name__ == "__main__":
    main()
