# Customer Feedback Dashboard with Satisfaction Metrics

from datetime import date

feedbacks = []
_fid = 1

SENTIMENTS  = {"Positive": (4, 5), "Neutral": (3, 3), "Negative": (1, 2)}
CATEGORIES  = ["Product Quality","Delivery","Customer Support","Pricing","Website","App"]

def submit_feedback(customer, category, rating, comment, channel="Website", fb_date=None):
    global _fid
    if category not in CATEGORIES:
        print(f"  Invalid category. Options: {CATEGORIES}"); return None
    if not (1 <= rating <= 5):
        print("  Rating must be 1-5."); return None
    fid = f"FB{_fid:05d}"; _fid += 1
    d   = fb_date or date.today()
    sentiment = next(s for s, (lo, hi) in SENTIMENTS.items() if lo <= rating <= hi)
    feedbacks.append({"id":fid, "customer":customer, "category":category,
                      "rating":rating, "comment":comment, "channel":channel,
                      "date":d, "sentiment":sentiment, "resolved":False})
    stars = "★" * rating + "☆" * (5 - rating)
    print(f"  [{fid}] {customer} | {category} | {stars} | {sentiment}")
    return fid

def resolve_feedback(fid):
    fb = next((f for f in feedbacks if f["id"] == fid), None)
    if not fb: print("  Feedback not found."); return
    fb["resolved"] = True
    print(f"  [{fid}] Marked as resolved.")

def category_analysis():
    print("\n--- Category-wise Analysis ---")
    for cat in CATEGORIES:
        cat_fbs = [f for f in feedbacks if f["category"] == cat]
        if not cat_fbs: continue
        avg = round(sum(f["rating"] for f in cat_fbs) / len(cat_fbs), 2)
        pos = sum(1 for f in cat_fbs if f["sentiment"] == "Positive")
        neg = sum(1 for f in cat_fbs if f["sentiment"] == "Negative")
        bar = "★" * int(avg)
        print(f"  {cat:<22} Avg:{avg:.1f} {bar} | Pos:{pos} Neg:{neg} | Total:{len(cat_fbs)}")

def sentiment_breakdown():
    print("\n--- Sentiment Breakdown ---")
    total = len(feedbacks)
    for sentiment in SENTIMENTS:
        count = sum(1 for f in feedbacks if f["sentiment"] == sentiment)
        pct   = count / total * 100 if total else 0
        bar   = "█" * int(pct // 5)
        print(f"  {sentiment:<12}: {count:>4} ({pct:5.1f}%) {bar}")

def nps_score():
    if not feedbacks: return 0
    promoters  = sum(1 for f in feedbacks if f["rating"] >= 4)
    detractors = sum(1 for f in feedbacks if f["rating"] <= 2)
    total      = len(feedbacks)
    nps = round((promoters - detractors) / total * 100, 1)
    print(f"\n  NPS Score: {nps} (Promoters:{promoters} Detractors:{detractors} Neutral:{total-promoters-detractors})")
    return nps

def channel_report():
    print("\n--- Feedback by Channel ---")
    channels = sorted(set(f["channel"] for f in feedbacks))
    for ch in channels:
        ch_fbs = [f for f in feedbacks if f["channel"] == ch]
        avg    = round(sum(f["rating"] for f in ch_fbs) / len(ch_fbs), 2)
        print(f"  {ch:<15}: {len(ch_fbs):>4} feedback(s) | Avg Rating: {avg}")

def low_rating_alerts(threshold=2):
    alerts = [f for f in feedbacks if f["rating"] <= threshold and not f["resolved"]]
    print(f"\n--- Low Rating Alerts (≤{threshold} stars) ---")
    if not alerts: print("  No critical alerts."); return
    for f in sorted(alerts, key=lambda x: x["rating"]):
        print(f"  [{f['id']}] {f['customer']:<18} {'★'*f['rating']:<5} {f['category']:<22} '{f['comment'][:40]}'")

def dashboard_summary():
    if not feedbacks: print("  No feedback data."); return
    total = len(feedbacks)
    avg   = round(sum(f["rating"] for f in feedbacks) / total, 2)
    resolved = sum(1 for f in feedbacks if f["resolved"])
    print(f"\n{'='*52}\n  CUSTOMER FEEDBACK DASHBOARD\n{'='*52}")
    print(f"  Total Feedback  : {total}")
    print(f"  Avg Rating      : {avg}/5.0  {'★'*int(avg)}")
    print(f"  Resolved        : {resolved}/{total}")
    category_analysis()
    sentiment_breakdown()
    nps_score()
    channel_report()
    low_rating_alerts()
    print(f"{'='*52}")

def main():
    print("=== Customer Feedback Dashboard ===")
    submit_feedback("Amit Sharma",  "Product Quality", 5, "Excellent build quality!", "Website")
    submit_feedback("Priya Nair",   "Delivery",        2, "Arrived 5 days late.",      "App")
    submit_feedback("Rahul Gupta",  "Customer Support",4, "Agent was very helpful.",   "Phone")
    submit_feedback("Sunita Patel", "Pricing",         3, "Prices are fair.",          "Website")
    submit_feedback("Kiran Rao",    "App",             1, "App crashes frequently.",   "App")
    submit_feedback("Meera Iyer",   "Product Quality", 5, "Love the new packaging.",   "Email")
    submit_feedback("Vijay Kumar",  "Delivery",        4, "Fast delivery, well packed.","Website")
    submit_feedback("Deepa Reddy",  "Customer Support",1, "No response for 3 days.",  "App")
    submit_feedback("Ankit Das",    "Pricing",         5, "Great value for money!",   "Website")
    submit_feedback("Kavya Singh",  "Website",         3, "Could be more intuitive.", "Website")
    resolve_feedback("FB00002")
    resolve_feedback("FB00005")
    dashboard_summary()

if __name__ == "__main__":
    main()
