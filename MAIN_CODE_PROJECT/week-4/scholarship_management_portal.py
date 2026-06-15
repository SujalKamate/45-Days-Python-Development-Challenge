# Scholarship Management Portal with Eligibility Screening

from datetime import date

scholarships = {}
applicants   = {}
applications = {}
_said = _apid = 1

def create_scholarship(name, sponsor, amount, criteria, seats, deadline):
    global _said
    said = f"SCH{_said:03d}"; _said += 1
    scholarships[said] = {"name":name,"sponsor":sponsor,"amount":amount,
                          "criteria":criteria,"seats":seats,"deadline":deadline,
                          "applicants":[],"awarded":[]}
    print(f"  [{said}] {name} | Rs.{amount:,}/yr | Seats:{seats} | Deadline:{deadline}")
    return said

def register_applicant(name, dob_str, income, marks_pct, category, course, institution):
    global _apid
    apid = f"APP{_apid:05d}"; _apid += 1
    dob  = date.fromisoformat(dob_str)
    age  = (date.today() - dob).days // 365
    applicants[apid] = {
        "name":name, "dob":dob, "age":age, "income":income,
        "marks":marks_pct, "category":category,
        "course":course, "institution":institution,
        "applied_to":[]
    }
    print(f"  [{apid}] {name} | {age}yrs | Marks:{marks_pct}% | Income:Rs.{income:,} | {category}")
    return apid

def check_eligibility(apid, said):
    if apid not in applicants or said not in scholarships:
        return False, ["Invalid IDs"]
    app = applicants[apid]
    sch = scholarships[said]
    crit = sch["criteria"]
    issues = []
    if "min_marks" in crit and app["marks"] < crit["min_marks"]:
        issues.append(f"Marks {app['marks']}% < required {crit['min_marks']}%")
    if "max_income" in crit and app["income"] > crit["max_income"]:
        issues.append(f"Income Rs.{app['income']:,} > limit Rs.{crit['max_income']:,}")
    if "max_age" in crit and app["age"] > crit["max_age"]:
        issues.append(f"Age {app['age']} > limit {crit['max_age']}")
    if "categories" in crit and app["category"] not in crit["categories"]:
        issues.append(f"Category '{app['category']}' not in {crit['categories']}")
    if "courses" in crit and app["course"] not in crit["courses"]:
        issues.append(f"Course '{app['course']}' not eligible")
    return len(issues) == 0, issues

def apply_scholarship(apid, said):
    if apid not in applicants or said not in scholarships:
        print("  Invalid IDs."); return False
    sch = scholarships[said]
    if date.today() > sch["deadline"]:
        print(f"  [{said}] Application deadline passed."); return False
    key = f"{apid}-{said}"
    if key in applications:
        print("  Already applied."); return False
    eligible, issues = check_eligibility(apid, said)
    score = applicants[apid]["marks"] - (applicants[apid]["income"] / 100000)
    applications[key] = {"apid":apid,"said":said,"eligible":eligible,
                          "issues":issues,"score":round(score,2),"status":"Pending"}
    scholarships[said]["applicants"].append(apid)
    applicants[apid]["applied_to"].append(said)
    if eligible:
        print(f"  [{apid}] {applicants[apid]['name']} → [{said}] ELIGIBLE | Score:{score:.2f}")
    else:
        print(f"  [{apid}] {applicants[apid]['name']} → [{said}] INELIGIBLE: {'; '.join(issues)}")
    return eligible

def select_awardees(said, top_n=None):
    if said not in scholarships: return
    sch    = scholarships[said]
    n      = top_n or sch["seats"]
    eligible_apps = [(k,a) for k,a in applications.items()
                     if a["said"]==said and a["eligible"] and a["status"]=="Pending"]
    ranked = sorted(eligible_apps, key=lambda x: -x[1]["score"])
    print(f"\n  Selection for [{said}] {sch['name']} (top {n}):")
    for rank, (key, app) in enumerate(ranked[:n], 1):
        apid    = app["apid"]
        aname   = applicants[apid]["name"]
        applications[key]["status"] = "Awarded"
        sch["awarded"].append(apid)
        print(f"  {rank}. [{apid}] {aname:<20} Score:{app['score']:.2f} | Rs.{sch['amount']:,} awarded")
    for key, app in ranked[n:]:
        applications[key]["status"] = "Waitlisted"

def selection_report():
    print(f"\n{'='*54}\n  SCHOLARSHIP SELECTION REPORT\n{'='*54}")
    for said, sch in scholarships.items():
        awarded = len(sch["awarded"])
        total   = len(sch["applicants"])
        total_disbursed = awarded * sch["amount"]
        print(f"  [{said}] {sch['name']:<30}")
        print(f"    Applied:{total} | Awarded:{awarded}/{sch['seats']} | Disbursed:Rs.{total_disbursed:,}")
    total_amount = sum(len(s["awarded"])*s["amount"] for s in scholarships.values())
    total_awarded = sum(len(s["awarded"]) for s in scholarships.values())
    print(f"\n  Total Recipients: {total_awarded}")
    print(f"  Total Aid Amount: Rs.{total_amount:,}")
    print(f"{'='*54}")

def main():
    print("=== Scholarship Management Portal ===")
    today = date.today()
    from datetime import timedelta
    s1 = create_scholarship("Merit Excellence Award","Govt of India",50000,
                            {"min_marks":85,"max_income":600000,"max_age":25},5,today+timedelta(days=30))
    s2 = create_scholarship("SC/ST Empowerment Fund","Ministry of Welfare",40000,
                            {"min_marks":60,"max_income":300000,"categories":["SC","ST"]},10,today+timedelta(days=45))
    s3 = create_scholarship("STEM Scholar Grant",   "Tech Foundation",   75000,
                            {"min_marks":80,"courses":["B.Tech","M.Tech","B.Sc"]},3,today+timedelta(days=20))
    a1 = register_applicant("Aarav Mehta","2002-05-15",450000,88,"General","B.Tech","IIT Delhi")
    a2 = register_applicant("Bhavna Singh","2003-08-22",250000,72,"SC",    "BCA",   "DU")
    a3 = register_applicant("Chetan Rao",  "2001-11-01",550000,91,"OBC",   "B.Tech","NIT")
    a4 = register_applicant("Divya Nair",  "2003-03-30",200000,65,"ST",    "B.Sc",  "State Univ")
    a5 = register_applicant("Eshan Kumar", "2002-07-10",380000,79,"General","M.Tech","IIT Bombay")
    apply_scholarship(a1, s1); apply_scholarship(a3, s1); apply_scholarship(a5, s1)
    apply_scholarship(a2, s2); apply_scholarship(a4, s2)
    apply_scholarship(a1, s3); apply_scholarship(a3, s3); apply_scholarship(a5, s3)
    apply_scholarship(a2, s3)  # ineligible course
    select_awardees(s1, 2)
    select_awardees(s2, 3)
    select_awardees(s3, 2)
    selection_report()

if __name__ == "__main__":
    main()
