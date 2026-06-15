# Job Application Tracker with Status Monitoring

from datetime import date, timedelta

STAGES = ["Applied", "Screening", "Technical Round", "HR Interview", "Offer", "Rejected", "Withdrawn"]

applications = {}
interviews   = {}
_aid = 1

def add_application(company, role, location, salary_range, source, apply_date=None):
    global _aid
    aid = f"JOB{_aid:04d}"
    _aid += 1
    applications[aid] = {
        "company": company, "role": role, "location": location,
        "salary": salary_range, "source": source,
        "applied_date": apply_date or date.today(),
        "stage": "Applied", "notes": [], "interviews": []
    }
    print(f"  [{aid}] {role} @ {company} | {location} | {salary_range} | via {source}")
    return aid

def update_stage(aid, new_stage, note=""):
    if aid not in applications:
        print("  Application not found.")
        return
    if new_stage not in STAGES:
        print(f"  Invalid stage. Options: {STAGES}")
        return
    applications[aid]["stage"] = new_stage
    if note:
        applications[aid]["notes"].append(f"[{date.today()}] {new_stage}: {note}")
    print(f"  [{aid}] {applications[aid]['company']} → Stage: {new_stage}")

def schedule_interview(aid, round_name, interview_date, mode, interviewer=""):
    if aid not in applications:
        print("  Application not found.")
        return
    entry = {
        "round": round_name, "date": interview_date,
        "mode": mode, "interviewer": interviewer, "result": "Pending"
    }
    applications[aid]["interviews"].append(entry)
    ikey = f"{aid}-{round_name}"
    interviews[ikey] = entry
    print(f"  [{aid}] Interview: {round_name} | {interview_date} | {mode}" +
          (f" | {interviewer}" if interviewer else ""))

def mark_interview_result(aid, round_name, result, feedback=""):
    ikey = f"{aid}-{round_name}"
    if ikey not in interviews:
        print("  Interview record not found.")
        return
    interviews[ikey]["result"]   = result
    interviews[ikey]["feedback"] = feedback
    print(f"  [{aid}] {round_name}: {result}" + (f" — {feedback}" if feedback else ""))

def view_application(aid):
    if aid not in applications:
        print("  Application not found.")
        return
    a = applications[aid]
    print(f"\n{'='*52}")
    print(f"  [{aid}] {a['role']} at {a['company']}")
    print(f"  Location : {a['location']} | Salary: {a['salary']}")
    print(f"  Source   : {a['source']}   | Applied: {a['applied_date']}")
    print(f"  Status   : {a['stage']}")
    if a["interviews"]:
        print("  Interviews:")
        for iv in a["interviews"]:
            print(f"    {iv['round']:<20} {iv['date']}  {iv['mode']:<12} Result: {iv['result']}")
    if a["notes"]:
        print("  Notes:")
        for n in a["notes"]:
            print(f"    {n}")
    print(f"{'='*52}")

def pipeline_summary():
    print(f"\n{'='*50}")
    print("  JOB APPLICATION PIPELINE")
    print(f"{'='*50}")
    stage_counts = {s: 0 for s in STAGES}
    for a in applications.values():
        stage_counts[a["stage"]] += 1
    for stage, count in stage_counts.items():
        if count:
            bar = "█" * count
            print(f"  {stage:<20}: {count:>3}  {bar}")
    active = sum(1 for a in applications.values() if a["stage"] not in ["Rejected","Withdrawn"])
    offers = stage_counts.get("Offer", 0)
    print(f"\n  Total   : {len(applications)} | Active: {active} | Offers: {offers}")
    print(f"{'='*50}")

def main():
    print("=== Job Application Tracker ===")
    today = date.today()
    a1 = add_application("Google",    "SDE II",         "Bangalore", "30-40 LPA", "LinkedIn",  today-timedelta(days=20))
    a2 = add_application("Microsoft", "Cloud Engineer", "Hyderabad", "25-35 LPA", "Referral",  today-timedelta(days=15))
    a3 = add_application("Flipkart",  "Backend Dev",    "Bangalore", "20-28 LPA", "Company Site",today-timedelta(days=10))
    a4 = add_application("Startup Co","Full Stack Dev", "Remote",    "18-25 LPA", "AngelList", today-timedelta(days=5))
    a5 = add_application("Amazon",    "SDE I",          "Pune",      "22-30 LPA", "LinkedIn",  today)
    update_stage(a1, "Technical Round", "Cleared screening call")
    update_stage(a2, "HR Interview", "Good technical round")
    update_stage(a3, "Rejected", "Overqualified per HR")
    update_stage(a4, "Screening")
    update_stage(a2, "Offer", "Offer letter expected in 3 days")
    schedule_interview(a1, "Technical Round 1", today+timedelta(days=2), "Video Call", "Eng Manager")
    mark_interview_result(a1, "Technical Round 1", "Cleared", "Strong in DSA")
    schedule_interview(a2, "HR Discussion", today+timedelta(days=1), "Phone")
    view_application(a2)
    pipeline_summary()

if __name__ == "__main__":
    main()
