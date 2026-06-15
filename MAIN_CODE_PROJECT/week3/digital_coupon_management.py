# Digital Coupon Management System with Expiry Handling

import random, string
from datetime import date, timedelta

coupons = {}
redemption_log = []

def create_coupon(code, discount_type, discount_value, valid_days,
                  min_order=0, max_uses=100, category="All"):
    if code in coupons:
        print(f"  Coupon '{code}' already exists.")
        return False
    if discount_type not in ("percent", "flat"):
        print("  discount_type must be 'percent' or 'flat'.")
        return False
    expiry = date.today() + timedelta(days=valid_days)
    coupons[code] = {
        "type": discount_type, "value": discount_value,
        "expiry": expiry, "min_order": min_order,
        "max_uses": max_uses, "used": 0,
        "category": category, "active": True
    }
    print(f"  Coupon [{code}]: {discount_type} {discount_value} | Expires: {expiry} | Min: Rs.{min_order} | Max uses: {max_uses}")
    return True

def generate_coupons(prefix, count, discount_type, value, valid_days):
    created = []
    for _ in range(count):
        code = prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        create_coupon(code, discount_type, value, valid_days)
        created.append(code)
    print(f"  Generated {count} coupon(s) with prefix '{prefix}'.")
    return created

def validate_coupon(code, order_amount, check_date=None):
    today = check_date or date.today()
    if code not in coupons:
        return False, "Coupon does not exist."
    c = coupons[code]
    if not c["active"]:
        return False, "Coupon is deactivated."
    if c["expiry"] < today:
        return False, f"Coupon expired on {c['expiry']}."
    if c["used"] >= c["max_uses"]:
        return False, "Coupon usage limit reached."
    if order_amount < c["min_order"]:
        return False, f"Minimum order Rs.{c['min_order']} required."
    return True, "Valid"

def apply_coupon(code, order_amount, customer, check_date=None):
    valid, msg = validate_coupon(code, order_amount, check_date)
    if not valid:
        print(f"  Coupon [{code}] rejected: {msg}")
        return order_amount
    c = coupons[code]
    if c["type"] == "percent":
        discount = round(order_amount * c["value"] / 100, 2)
    else:
        discount = min(c["value"], order_amount)
    final = round(order_amount - discount, 2)
    c["used"] += 1
    redemption_log.append({
        "code": code, "customer": customer,
        "original": order_amount, "discount": discount,
        "final": final, "date": check_date or date.today()
    })
    print(f"  [{code}] Applied for {customer}: Rs.{order_amount} - Rs.{discount} = Rs.{final}")
    return final

def deactivate_coupon(code):
    if code not in coupons:
        print("  Coupon not found.")
        return
    coupons[code]["active"] = False
    print(f"  Coupon [{code}] deactivated.")

def coupon_stats(code):
    if code not in coupons:
        print("  Coupon not found.")
        return
    c = coupons[code]
    logs = [r for r in redemption_log if r["code"] == code]
    total_savings = sum(r["discount"] for r in logs)
    print(f"\n  Stats for [{code}]:")
    print(f"  Type         : {c['type']} {c['value']}")
    print(f"  Used / Max   : {c['used']} / {c['max_uses']}")
    print(f"  Total Savings: Rs.{total_savings:.2f}")
    print(f"  Expiry       : {c['expiry']} | Active: {c['active']}")

def redemption_report():
    print(f"\n{'='*52}")
    print("  COUPON REDEMPTION REPORT")
    print(f"{'='*52}")
    total_discount = sum(r["discount"] for r in redemption_log)
    total_orders   = sum(r["original"] for r in redemption_log)
    print(f"  Total Redemptions : {len(redemption_log)}")
    print(f"  Total Orders Value: Rs.{total_orders:.2f}")
    print(f"  Total Discounts   : Rs.{total_discount:.2f}")
    print(f"\n  {'Coupon':<12} {'Customer':<15} {'Order':>8} {'Disc':>8} {'Final':>8}")
    for r in redemption_log:
        print(f"  {r['code']:<12} {r['customer']:<15} {r['original']:>8} {r['discount']:>8.2f} {r['final']:>8.2f}")
    expired = sum(1 for c in coupons.values() if c["expiry"] < date.today())
    print(f"\n  Active Coupons  : {sum(1 for c in coupons.values() if c['active'])}")
    print(f"  Expired Coupons : {expired}")
    print(f"{'='*52}")

def main():
    print("=== Digital Coupon Management System ===")
    create_coupon("WELCOME20", "percent", 20, 30, min_order=200, max_uses=50)
    create_coupon("FLAT100",   "flat",   100, 15, min_order=500, max_uses=20)
    create_coupon("VIP50",     "percent", 50, 7,  min_order=1000,max_uses=10)
    create_coupon("FREEDEL",   "flat",    30, 60, min_order=0,   max_uses=200)
    today = date.today()
    apply_coupon("WELCOME20", 450,  "Aarav Mehta",   today)
    apply_coupon("FLAT100",   800,  "Bhavna Singh",  today)
    apply_coupon("VIP50",     1500, "Chetan Rao",    today)
    apply_coupon("FLAT100",   300,  "Divya Nair",    today)   # Below min order
    apply_coupon("WELCOME20", 250,  "Eshan Das",     today)
    apply_coupon("EXPIRED99", 500,  "Fiona Roy",     today)   # Non-existent
    coupon_stats("WELCOME20")
    deactivate_coupon("VIP50")
    redemption_report()

if __name__ == "__main__":
    main()
