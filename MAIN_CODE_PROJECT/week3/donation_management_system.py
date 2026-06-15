# Donation Management System with Contributor Reports

from datetime import date

donors = {}
donations = []
_did = 1

def register_donor(name, email, phone):
    if email in donors:
        print(f"  Donor with email {email} already registered.")
        return None
    donors[email] = {"name": name, "phone": phone, "total_donated": 0, "count": 0}
    print(f"  Registered: {name} | {email}")
    return email

def record_donation(email, amount, cause, method="Online", don_date=None):
    global _did
    if email not in donors:
        print("  Donor not found. Please register first.")
        return None
    if amount <= 0:
        print("  Donation amount must be positive.")
        return None
    d = don_date or date.today()
    did = f"DON{_did:05d}"
    _did += 1
    donations.append({
        "id": did, "email": email, "amount": amount,
        "cause": cause, "method": method, "date": d
    })
    donors[email]["total_donated"] += amount
    donors[email]["count"] += 1
    print(f"  [{did}] {donors[email]['name']} donated Rs.{amount} for '{cause}' via {method} on {d}")
    return did

def donor_summary(email):
    if email not in donors:
        print("  Donor not found.")
        return
    d = donors[email]
    donor_donations = [x for x in donations if x["email"] == email]
    print(f"\n  Donor: {d['name']} | {email}")
    print(f"  Total Donated : Rs.{d['total_donated']:.2f} across {d['count']} donation(s)")
    for don in donor_donations:
        print(f"    [{don['id']}] Rs.{don['amount']:<8} {don['cause']:<25} {don['date']}")

def cause_summary():
    cause_totals = {}
    for don in donations:
        cause_totals[don["cause"]] = cause_totals.get(don["cause"], 0) + don["amount"]
    print("\n--- Donations by Cause ---")
    for cause, total in sorted(cause_totals.items(), key=lambda x: -x[1]):
        print(f"  {cause:<30}: Rs.{total:,.2f}")

def top_contributors(n=5):
    ranked = sorted(donors.items(), key=lambda x: -x[1]["total_donated"])[:n]
    print(f"\n--- Top {n} Contributors ---")
    for rank, (email, d) in enumerate(ranked, 1):
        print(f"  {rank}. {d['name']:<20} Rs.{d['total_donated']:>10,.2f}  ({d['count']} donations)")

def monthly_summary():
    monthly = {}
    for don in donations:
        key = don["date"].strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + don["amount"]
    print("\n--- Monthly Donation Summary ---")
    for month in sorted(monthly):
        print(f"  {month}: Rs.{monthly[month]:,.2f}")

def full_report():
    print(f"\n{'='*52}")
    print("  DONATION MANAGEMENT REPORT")
    print(f"{'='*52}")
    total = sum(don["amount"] for don in donations)
    avg   = (total / len(donations)) if donations else 0
    methods = {}
    for don in donations:
        methods[don["method"]] = methods.get(don["method"], 0) + don["amount"]
    print(f"  Total Donors     : {len(donors)}")
    print(f"  Total Donations  : {len(donations)}")
    print(f"  Total Amount     : Rs.{total:,.2f}")
    print(f"  Average Donation : Rs.{avg:,.2f}")
    print(f"\n  Payment Methods:")
    for method, amt in methods.items():
        print(f"    {method:<15}: Rs.{amt:,.2f}")
    top_contributors(3)
    cause_summary()
    monthly_summary()
    print(f"{'='*52}")

def main():
    print("=== Donation Management System ===")
    register_donor("Amit Sharma",  "amit@example.com",   "9876543210")
    register_donor("Priya Verma",  "priya@example.com",  "9123456789")
    register_donor("Rahul Nair",   "rahul@example.com",  "9011223344")
    register_donor("Sunita Patel", "sunita@example.com", "9988776600")
    today = date.today()
    record_donation("amit@example.com",   5000,  "Child Education",   "Online",  today)
    record_donation("priya@example.com",  12000, "Flood Relief",      "Cheque",  today)
    record_donation("rahul@example.com",  3000,  "Child Education",   "UPI",     today)
    record_donation("sunita@example.com", 8000,  "Medical Aid",       "Online",  today)
    record_donation("amit@example.com",   2500,  "Flood Relief",      "UPI",     today)
    record_donation("priya@example.com",  15000, "Orphanage Support", "Online",  today)
    record_donation("rahul@example.com",  4000,  "Medical Aid",       "Cash",    today)
    full_report()

if __name__ == "__main__":
    main()
