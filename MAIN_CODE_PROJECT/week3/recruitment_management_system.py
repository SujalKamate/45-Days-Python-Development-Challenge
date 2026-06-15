# Recruitment Management System with Candidate Ranking

from datetime import date

CRITERIA = {
    "experience_years": 30,
    "education_score":  20,
    "technical_score":  30,
    "communication":    10,
    "aptitude_score":   10,
}
job_postings = {}
candidates   = {}
applications = {}
_jid = 1
_cid = 1

def post_job(title, department, min_experience, required_skills):
    global _jid
    jid = f"JOB{_jid:03d}"
    _jid += 1
    job_postings[jid] = {
        "title": title, "department": department,
        "min_exp": min_experience, "skills": required_skills,
        "applicants": []
    }
    print(f"  [{jid}] {title} | {department} | Min Exp: {min_experience}yr | Skills: {required_skills}")
    return jid

def register_candidate(name, email, experience, education, skills):
    global _cid
    cid = f"CND{_cid:04d}"
    _cid += 1
    edu_map = {"PhD":100,"Masters":85,"BTech":75,"BSc":65,"Diploma":50,"12th":40}
    candidates[cid] = {
        "name": name, "email": email, "experience": experience,
        "education": education, "edu_score": edu_map.get(education, 50),
        "skills": [s.lower() for s in skills]
    }
    print(f"  [{cid}] {name} | {education} | {experience} yr exp")
    return cid

def apply(cid, jid, technical_score, communication, aptitude):
    if cid not in candidates or jid not in job_postings:
        print("  Invalid candidate or job ID.")
        return
    key = f"{cid}-{jid}"
    if key in applications:
        print("  Already applied.")
        return
    c   = candidates[cid]
    job = job_postings[jid]
    skill_match = sum(1 for s in c["skills"] if any(s in js.lower() for js in job["skills"]))
    exp_norm = min(c["experience"] / max(job["min_exp"], 1), 2.0) * 50
    score = round(
        (exp_norm       / 100) * CRITERIA["experience_years"] +
        (c["edu_score"] / 100) * CRITERIA["education_score"]  +
        (technical_score/ 100) * CRITERIA["technical_score"]  +
        (communication  / 100) * CRITERIA["communication"]    +
        (aptitude       / 100) * CRITERIA["aptitude_score"],
        2
    )
    applications[key] = {
        "candidate": cid, "job": jid, "score": score,
        "skill_match": skill_match, "technical": technical_score,
        "communication": communication, "aptitude": aptitude,
        "applied_date": date.today(), "status": "Under Review"
    }
    job_postings[jid]["applicants"].append(key)
    print(f"  [{cid}] {c['name']} applied to [{jid}] | Score: {score:.2f} | Skills matched: {skill_match}")

def shortlist(jid, top_n=3):
    applicant_keys = job_postings[jid]["applicants"]
    ranked = sorted(applicant_keys, key=lambda k: applications[k]["score"], reverse=True)
    print(f"\n  Shortlist for [{jid}] {job_postings[jid]['title']} (Top {top_n}):")
    print(f"  {'Rank':<5} {'Name':<20} {'Score':>7} {'Tech':>6} {'Comm':>6} {'Apt':>6} {'Skills':>7}")
    for rank, key in enumerate(ranked[:top_n], 1):
        app  = applications[key]
        name = candidates[app["candidate"]]["name"]
        app["status"] = "Shortlisted"
        print(f"  {rank:<5} {name:<20} {app['score']:>7.2f} {app['technical']:>6} {app['communication']:>6} {app['aptitude']:>6} {app['skill_match']:>7}")
    for key in ranked[top_n:]:
        applications[key]["status"] = "Not Shortlisted"

def recruitment_report():
    print(f"\n{'='*52}")
    print("  RECRUITMENT REPORT")
    print(f"{'='*52}")
    for jid, job in job_postings.items():
        total = len(job["applicants"])
        shortlisted = sum(1 for k in job["applicants"] if applications[k]["status"] == "Shortlisted")
        avg_score = round(sum(applications[k]["score"] for k in job["applicants"]) / total, 2) if total else 0
        print(f"  [{jid}] {job['title']:<25} | Applied: {total} | Shortlisted: {shortlisted} | AvgScore: {avg_score}")
    print(f"\n  Total Jobs     : {len(job_postings)}")
    print(f"  Total Applicants: {len(set(a['candidate'] for a in applications.values()))}")
    print(f"{'='*52}")

def main():
    print("=== Recruitment Management System ===")
    j1 = post_job("Python Developer",    "Engineering", 2, ["Python","Django","REST API"])
    j2 = post_job("Data Analyst",        "Analytics",   1, ["Python","SQL","Excel","Tableau"])
    c1 = register_candidate("Aarav Mehta",  "aarav@mail.com",  3, "BTech",  ["Python","Django","REST API","Git"])
    c2 = register_candidate("Bhavna Singh", "bhavna@mail.com", 1, "Masters",["Python","SQL","Tableau","Excel"])
    c3 = register_candidate("Chetan Rao",   "chetan@mail.com", 5, "BTech",  ["Java","Python","REST API"])
    c4 = register_candidate("Divya Nair",   "divya@mail.com",  2, "BSc",    ["Python","SQL","Excel"])
    c5 = register_candidate("Eshan Das",    "eshan@mail.com",  0, "BTech",  ["Python","Django"])
    apply(c1, j1, 85, 78, 80); apply(c3, j1, 90, 72, 88); apply(c5, j1, 65, 60, 70)
    apply(c2, j2, 88, 82, 85); apply(c4, j2, 75, 80, 78); apply(c1, j2, 80, 78, 80)
    shortlist(j1, top_n=2)
    shortlist(j2, top_n=2)
    recruitment_report()

if __name__ == "__main__":
    main()
