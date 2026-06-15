# University Course Registration System with Prerequisite Validation

courses = {}
students = {}
enrollments = {}

def add_course(code, name, credits, prerequisites=None, max_seats=30):
    courses[code] = {
        "name": name, "credits": credits,
        "prerequisites": prerequisites or [],
        "max_seats": max_seats, "enrolled": 0
    }
    prereqs = ", ".join(prerequisites) if prerequisites else "None"
    print(f"  [{code}] {name} | {credits} credits | Prereqs: {prereqs} | Seats: {max_seats}")

def add_student(sid, name, completed_courses=None):
    students[sid] = {
        "name": name,
        "completed": completed_courses or [],
        "enrolled_in": []
    }
    print(f"  [{sid}] {name} registered")

def check_prerequisites(sid, course_code):
    if course_code not in courses:
        return False, "Course not found"
    course = courses[course_code]
    if not course["prerequisites"]:
        return True, "No prerequisites"
    student = students.get(sid)
    if not student:
        return False, "Student not found"
    missing = [p for p in course["prerequisites"] if p not in student["completed"]]
    if missing:
        return False, f"Missing prerequisites: {', '.join(missing)}"
    return True, "Prerequisites met"

def register_course(sid, course_code):
    if sid not in students:
        print("  Student not found.")
        return False
    if course_code not in courses:
        print("  Course not found.")
        return False
    student = students[sid]
    course  = courses[course_code]
    if course_code in student["enrolled_in"]:
        print(f"  {student['name']} is already enrolled in {course_code}.")
        return False
    if course["enrolled"] >= course["max_seats"]:
        print(f"  Course {course_code} is full.")
        return False
    ok, msg = check_prerequisites(sid, course_code)
    if not ok:
        print(f"  Registration denied for {student['name']} in {course_code}: {msg}")
        return False
    student["enrolled_in"].append(course_code)
    course["enrolled"] += 1
    key = f"{sid}-{course_code}"
    enrollments[key] = {"student": sid, "course": course_code, "status": "Enrolled"}
    print(f"  ✔ {student['name']} enrolled in [{course_code}] {course['name']}")
    return True
def drop_course(sid, course_code):
    if sid not in students:
        print("  Student not found.")
        return
    student = students[sid]
    if course_code not in student["enrolled_in"]:
        print(f"  {student['name']} is not enrolled in {course_code}.")
        return
    student["enrolled_in"].remove(course_code)
    courses[course_code]["enrolled"] -= 1
    key = f"{sid}-{course_code}"
    if key in enrollments:
        enrollments[key]["status"] = "Dropped"
    print(f"  {student['name']} dropped {course_code}.")

def student_schedule(sid):
    if sid not in students:
        print("  Student not found.")
        return
    s = students[sid]
    total_credits = sum(courses[c]["credits"] for c in s["enrolled_in"] if c in courses)
    print(f"\n  Schedule — {s['name']} [{sid}]")
    print(f"  {'Code':<10} {'Course Name':<30} {'Credits'}")
    for code in s["enrolled_in"]:
        c = courses.get(code, {})
        print(f"  {code:<10} {c.get('name','?'):<30} {c.get('credits','?')}")
    print(f"  Total Credits: {total_credits}")

def enrollment_report():
    print(f"\n{'='*52}")
    print("  ENROLLMENT REPORT")
    print(f"{'='*52}")
    print(f"  {'Code':<10} {'Course':<28} {'Enrolled':>8} {'Max':>5} {'Fill%':>7}")
    for code, c in courses.items():
        pct = (c["enrolled"] / c["max_seats"] * 100) if c["max_seats"] else 0
        bar = "█" * int(pct // 10)
        print(f"  {code:<10} {c['name']:<28} {c['enrolled']:>8} {c['max_seats']:>5} {pct:>6.0f}% {bar}")
    total_enrol = sum(c["enrolled"] for c in courses.values())
    print(f"\n  Total Active Enrollments: {total_enrol}")
    print(f"{'='*52}")

def main():
    print("=== University Course Registration System ===")
    add_course("CS101", "Intro to Programming",   3)
    add_course("CS102", "Data Structures",         3, ["CS101"])
    add_course("CS201", "Algorithms",              4, ["CS102"])
    add_course("CS301", "Machine Learning",        4, ["CS201", "MATH101"])
    add_course("MATH101","Linear Algebra",         3)
    add_course("PHYS101","Physics I",              3)
    add_student("S001", "Aarav Mehta",  completed_courses=["CS101","CS102","MATH101"])
    add_student("S002", "Bhavna Rao",   completed_courses=["CS101"])
    add_student("S003", "Chetan Nair",  completed_courses=[])
    add_student("S004", "Divya Sharma", completed_courses=["CS101","CS102","CS201","MATH101"])
    print("\n--- Registrations ---")
    register_course("S001", "CS201")
    register_course("S002", "CS102")
    register_course("S003", "CS102")     # Missing prereq
    register_course("S004", "CS301")
    register_course("S001", "CS201")     # Duplicate
    register_course("S002", "PHYS101")
    print("\n--- Dropping a Course ---")
    drop_course("S002", "PHYS101")
    student_schedule("S001")
    student_schedule("S004")
    enrollment_report()

if __name__ == "__main__":
    main()
