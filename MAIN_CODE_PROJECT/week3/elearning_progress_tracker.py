# E-Learning Progress Tracker with Course Analytics

courses = {}
students = {}
progress = {}

def add_course(cid, title, modules, instructor):
    courses[cid] = {"title": title, "modules": modules,
                    "total_modules": len(modules), "instructor": instructor}
    print(f"  [{cid}] {title} | {len(modules)} modules | Instructor: {instructor}")

def enroll_student(sid, name, course_ids):
    students[sid] = {"name": name, "enrolled": course_ids}
    for cid in course_ids:
        key = f"{sid}-{cid}"
        if cid in courses:
            progress[key] = {"completed_modules": [], "score": None, "certificate": None}
    enrolled_names = [courses[c]["title"] for c in course_ids if c in courses]
    print(f"  [{sid}] {name} enrolled in: {', '.join(enrolled_names)}")

def complete_module(sid, cid, module_name):
    key = f"{sid}-{cid}"
    if key not in progress:
        print("  Enrollment not found.")
        return
    if cid not in courses or module_name not in courses[cid]["modules"]:
        print(f"  Module '{module_name}' not found in course.")
        return
    if module_name in progress[key]["completed_modules"]:
        print(f"  Module already completed.")
        return
    progress[key]["completed_modules"].append(module_name)
    completed = len(progress[key]["completed_modules"])
    total     = courses[cid]["total_modules"]
    pct       = round(completed / total * 100, 1)
    print(f"  [{sid}] {students[sid]['name']} — '{module_name}' done | Progress: {pct}%")

def submit_assessment(sid, cid, score):
    key = f"{sid}-{cid}"
    if key not in progress:
        print("  Enrollment not found.")
        return
    progress[key]["score"] = score
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "F"
    if score >= 60:
        cert_id = f"CERT-{sid}-{cid}"
        progress[key]["certificate"] = cert_id
        print(f"  [{sid}] {cid} Assessment: {score}/100 Grade:{grade} | Certificate: {cert_id}")
    else:
        print(f"  [{sid}] {cid} Assessment: {score}/100 Grade:{grade} | Failed — No certificate")

def student_dashboard(sid):
    if sid not in students:
        print("  Student not found.")
        return
    s = students[sid]
    print(f"\n{'='*52}")
    print(f"  Dashboard — {s['name']} [{sid}]")
    print(f"{'='*52}")
    for cid in s["enrolled"]:
        if cid not in courses:
            continue
        key  = f"{sid}-{cid}"
        prog = progress.get(key, {})
        comp = len(prog.get("completed_modules", []))
        total= courses[cid]["total_modules"]
        pct  = round(comp/total*100, 1) if total else 0
        bar  = "█" * int(pct//10) + "░" * (10 - int(pct//10))
        score = prog.get("score")
        cert  = prog.get("certificate", "—")
        print(f"  {courses[cid]['title'][:28]:<28} {pct:>5}% [{bar}]")
        print(f"    Completed: {comp}/{total} | Score: {score or 'N/A'} | Cert: {cert}")
    print(f"{'='*52}")

def course_analytics(cid):
    if cid not in courses:
        print("  Course not found.")
        return
    enrolled_keys = [k for k in progress if k.endswith(f"-{cid}")]
    if not enrolled_keys:
        print("  No students enrolled.")
        return
    completions = [len(progress[k]["completed_modules"]) for k in enrolled_keys]
    total = courses[cid]["total_modules"]
    scores= [progress[k]["score"] for k in enrolled_keys if progress[k]["score"] is not None]
    avg_progress = round(sum(completions)/len(completions)/total*100, 1) if total else 0
    avg_score    = round(sum(scores)/len(scores), 1) if scores else "N/A"
    certs_issued = sum(1 for k in enrolled_keys if progress[k].get("certificate"))
    print(f"\n  Analytics — {courses[cid]['title']}")
    print(f"  Enrolled    : {len(enrolled_keys)}")
    print(f"  Avg Progress: {avg_progress}%")
    print(f"  Avg Score   : {avg_score}")
    print(f"  Certs Issued: {certs_issued}")
    ranked = sorted(enrolled_keys, key=lambda k: len(progress[k]["completed_modules"]), reverse=True)
    print("  Top Learners:")
    for rank, key in enumerate(ranked[:3], 1):
        sid_part = key.split("-")[0]
        name = students.get(sid_part, {}).get("name", "?")
        print(f"    {rank}. {name} — {len(progress[key]['completed_modules'])}/{total} modules")

def main():
    print("=== E-Learning Progress Tracker ===")
    add_course("PY101", "Python Basics",
               ["Variables","Loops","Functions","Files","OOP"], "Dr. Gupta")
    add_course("DS201", "Data Science Fundamentals",
               ["Pandas","NumPy","Matplotlib","Statistics","ML Intro"], "Prof. Sharma")
    enroll_student("ST001", "Aarav Mehta",  ["PY101","DS201"])
    enroll_student("ST002", "Bhavna Rao",   ["PY101"])
    enroll_student("ST003", "Chetan Singh", ["PY101","DS201"])
    for m in ["Variables","Loops","Functions","Files","OOP"]:
        complete_module("ST001","PY101",m)
    complete_module("ST002","PY101","Variables")
    complete_module("ST002","PY101","Loops")
    for m in ["Variables","Loops","Functions"]:
        complete_module("ST003","PY101",m)
    for m in ["Pandas","NumPy","Matplotlib"]:
        complete_module("ST001","DS201",m)
    submit_assessment("ST001","PY101",92)
    submit_assessment("ST002","PY101",55)
    submit_assessment("ST003","PY101",78)
    submit_assessment("ST001","DS201",85)
    student_dashboard("ST001")
    student_dashboard("ST002")
    course_analytics("PY101")

if __name__ == "__main__":
    main()
