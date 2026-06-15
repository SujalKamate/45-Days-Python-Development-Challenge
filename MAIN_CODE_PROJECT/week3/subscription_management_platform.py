# Subscription Management Platform with Renewal Forecasting

from datetime import date, timedelta

PLANS = {
    "Basic":       {"price": 299,  "days": 30,  "features": ["5 Users", "10 GB"]},
    "Professional":{"price": 799,  "days": 30,  "features": ["25 Users", "50 GB", "API"]},
    "Enterprise":  {"price": 2499, "days": 30,  "features": ["Unlimited Users", "500 GB", "API", "SLA"]},
    "Annual Basic":{"price": 2999, "days": 365, "features": ["5 Users", "10 GB"]},
}
ALERT_DAYS = 10
subscribers = {}
transactions = []
_sid = 1

def subscribe(company, contact_email, plan, start_date=None):
    global _sid
    if plan not in PLANS:
        print(f"  Unknown plan. Available: {list(PLANS.keys())}")
        return None
    start  = start_date or date.today()
    expiry = start + timedelta(days=PLANS[plan]["days"])
    sid    = f"SUB{_sid:05d}"
    _sid  += 1
    subscribers[sid] = {
        "company": company, "email": contact_email, "plan": plan,
        "start": start, "expiry": expiry, "active": True, "renewals": 0
    }
    transactions.append({"sid": sid, "plan": plan, "amount": PLANS[plan]["price"], "date": start})
    print(f"  [{sid}] {company} | {plan} | Rs.{PLANS[plan]['price']} | Expires: {expiry}")
    return sid

def renew_subscription(sid, new_plan=None):
    if sid not in subscribers:
        print("  Subscriber not found.")
        return
    s = subscribers[sid]
    plan = new_plan or s["plan"]
    if plan not in PLANS:
        print("  Invalid plan.")
        return
    today = date.today()
    base  = max(today, s["expiry"])
    s["expiry"]   = base + timedelta(days=PLANS[plan]["days"])
    s["plan"]     = plan
    s["active"]   = True
    s["renewals"] += 1
    transactions.append({"sid": sid, "plan": plan, "amount": PLANS[plan]["price"], "date": today})
    print(f"  [{sid}] {s['company']} renewed to {plan} | New Expiry: {s['expiry']}")

def renewal_forecast(days=30):
    today = date.today()
    cutoff = today + timedelta(days=days)
    due = [(sid, s) for sid, s in subscribers.items()
           if s["active"] and today <= s["expiry"] <= cutoff]
    print(f"\n--- Renewal Forecast (next {days} days) ---")
    if not due:
        print("  No renewals forecast.")
    for sid, s in sorted(due, key=lambda x: x[1]["expiry"]):
        days_left = (s["expiry"] - today).days
        revenue   = PLANS[s["plan"]]["price"]
        print(f"  [{sid}] {s['company']:<20} | {s['plan']:<15} | in {days_left:>3} days | Rs.{revenue}")
    expected_rev = sum(PLANS[s["plan"]]["price"] for _, s in due)
    print(f"  Forecast Revenue: Rs.{expected_rev:,.2f} from {len(due)} renewal(s)")

def cancel_subscription(sid):
    if sid not in subscribers:
        print("  Subscriber not found.")
        return
    subscribers[sid]["active"] = False
    print(f"  [{sid}] {subscribers[sid]['company']} subscription cancelled.")

def subscriber_report():
    print(f"\n{'='*55}")
    print("  SUBSCRIPTION REPORT")
    print(f"{'='*55}")
    today = date.today()
    active   = [s for s in subscribers.values() if s["active"]]
    expired  = [s for s in subscribers.values() if s["expiry"] < today]
    plan_counts = {p: 0 for p in PLANS}
    for s in subscribers.values():
        plan_counts[s["plan"]] = plan_counts.get(s["plan"], 0) + 1
    mrr = sum(PLANS[s["plan"]]["price"] for s in active
              if PLANS[s["plan"]]["days"] <= 31)
    total_rev = sum(t["amount"] for t in transactions)
    print(f"  Total Subscribers  : {len(subscribers)}")
    print(f"  Active             : {len(active)}")
    print(f"  Expired/Cancelled  : {len(subscribers) - len(active)}")
    print(f"  MRR (est.)         : Rs.{mrr:,.2f}")
    print(f"  Total Revenue      : Rs.{total_rev:,.2f}")
    print(f"\n  Plan Distribution:")
    for plan, count in plan_counts.items():
        if count:
            print(f"    {plan:<20}: {count}")
    print(f"{'='*55}")

def main():
    print("=== Subscription Management Platform ===")
    today = date.today()
    s1 = subscribe("TechCorp",      "tech@corp.com",   "Professional")
    s2 = subscribe("StartupXYZ",    "hello@xyz.com",   "Basic", today - timedelta(days=25))
    s3 = subscribe("GlobalMedia",   "info@global.com", "Enterprise")
    s4 = subscribe("DevStudio",     "dev@studio.com",  "Annual Basic")
    s5 = subscribe("SmallBiz",      "biz@small.com",   "Basic", today - timedelta(days=28))
    s6 = subscribe("FinanceHub",    "admin@fin.com",   "Professional", today - timedelta(days=8))
    renewal_forecast(15)
    renew_subscription(s2, "Professional")
    cancel_subscription(s5)
    subscriber_report()

if __name__ == "__main__":
    main()
