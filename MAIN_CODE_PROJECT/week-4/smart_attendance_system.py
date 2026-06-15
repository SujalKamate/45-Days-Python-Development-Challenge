# Smart Attendance System with QR Code Simulation

import hashlib, random, string
from datetime import date, time as dtime, datetime

sessions  = {}
students  = {}
attendance= {}
_sess_id = _stud_id = 1

def register_student(name, roll_no, course):
    global _stud_id
    sid = f"STD{_stud_id:04d}"; _stud_id += 1
    students[sid] = {"name":name, "roll":roll_no, "course":course, "sessions_attended":0}
    print(f"  [{sid}] {name} | Roll:{roll_no} | {course}")
    return sid

def create_session(subject, instructor, sess_date=None, duration_mins=60):
    global _sess_id
    sess_id = f"SES{_sess_id:04d}"; _sess_id += 1
    d = sess_date or date.today()
    raw_code = f"{sess_id}{subject}{d}{random.randint(1000,9999)}"
    att_code = hashlib.md5(raw_code.encode()).hexdigest()[:8].upper()
    sessions[sess_id] = {
        "subject":subject, "instructor":instructor, "date":d,
        "duration":duration_mins, "att_code":att_code,
        "marked_students":[], "time_created":datetime.now().strftime("%H:%M:%S")
    }
    print(f"  [{sess_id}] {subject} | {instructor} | {d} | Code: {att_code}")
    return sess_id, att_code

def mark_attendance(student_id, sess_id, submitted_code):
    if student_id not in students: print("  Student not found."); return False
    if sess_id not in sessions: print("  Session not found."); return False
    sess = sessions[sess_id]
    if submitted_code.upper() != sess["att_code"]:
        print(f"  ✗ INVALID CODE for {students[student_id]['name']}. Access denied."); return False
    att_key = f"{student_id}-{sess_id}"
    if att_key in attendance:
        print(f"  ✗ DUPLICATE: {students[student_id]['name']} already marked for [{sess_id}]."); return False
    attendance[att_key] = {"student":student_id,"session":sess_id,
                           "timestamp":datetime.now().strftime("%H:%M:%S"),"date":sess["date"]}
    sess["marked_students"].append(student_id)
    students[student_id]["sessions_attended"] += 1
    print(f"  ✔ [{student_id}] {students[student_id]['name']} marked for [{sess_id}] {sess['subject']}")
    return True

def session_attendance_sheet(sess_id):
    if sess_id not in sessions: return
    sess = sessions[sess_id]
    marked = sess["marked_students"]
    all_students = list(students.keys())
    print(f"\n  Attendance Sheet — [{sess_id}] {sess['subject']} | {sess['date']}")
    print(f"  {'ID':<8} {'Name':<20} {'Roll':<8} {'Status'}")
    for sid in all_students:
        s      = students[sid]
        status = "✔ Present" if sid in marked else "✗ Absent"
        print(f"  {sid:<8} {s['name']:<20} {s['roll']:<8} {status}")
    pct = len(marked) / len(all_students) * 100 if all_students else 0
    print(f"  Present: {len(marked)}/{len(all_students)} ({pct:.0f}%)")

def student_attendance_summary(student_id):
    if student_id not in students: return
    s = students[student_id]
    total_sessions = len(sessions)
    attended = s["sessions_attended"]
    pct = (attended / total_sessions * 100) if total_sessions else 0
    print(f"\n  Summary: {s['name']} [{student_id}]")
    print(f"  Attended: {attended}/{total_sessions} sessions ({pct:.1f}%)")
    my_sessions = [att for key, att in attendance.items() if key.startswith(student_id)]
    for a in my_sessions:
        subj = sessions[a["session"]]["subject"]
        print(f"  ✔ [{a['session']}] {subj} | {a['date']} at {a['timestamp']}")

def low_attendance_alert(threshold=75):
    print(f"\n--- Low Attendance Alert (below {threshold}%) ---")
    total = len(sessions)
    if total == 0: return
    found = False
    for sid, s in students.items():
        pct = s["sessions_attended"] / total * 100
        if pct < threshold:
            print(f"  ⚠ {s['name']} [{sid}]: {pct:.1f}% ({s['sessions_attended']}/{total})")
            found = True
    if not found: print("  All students have adequate attendance.")

def attendance_report():
    print(f"\n{'='*50}\n  ATTENDANCE SYSTEM REPORT\n{'='*50}")
    print(f"  Students : {len(students)} | Sessions: {len(sessions)} | Entries: {len(attendance)}")
    print(f"\n  Session Summary:")
    for sess_id, sess in sessions.items():
        count = len(sess["marked_students"])
        total = len(students)
        pct   = count / total * 100 if total else 0
        print(f"  [{sess_id}] {sess['subject']:<20} {count}/{total} ({pct:.0f}%)")
    print(f"{'='*50}")

def main():
    print("=== Smart Attendance System ===")
    s1 = register_student("Aarav Mehta",  "CS101", "B.Tech CSE")
    s2 = register_student("Bhavna Singh", "CS102", "B.Tech CSE")
    s3 = register_student("Chetan Rao",   "CS103", "B.Tech CSE")
    s4 = register_student("Divya Nair",   "CS104", "B.Tech CSE")
    s5 = register_student("Eshan Kumar",  "CS105", "B.Tech CSE")
    sess1, code1 = create_session("Data Structures", "Dr. Gupta")
    sess2, code2 = create_session("Algorithms",      "Prof. Sharma")
    sess3, code3 = create_session("DBMS",            "Dr. Nair")
    for sid in [s1,s2,s3,s4]: mark_attendance(sid, sess1, code1)
    mark_attendance(s5, sess1, "WRONGCODE")  # wrong code
    mark_attendance(s1, sess1, code1)         # duplicate
    for sid in [s1,s3,s5]:    mark_attendance(sid, sess2, code2)
    for sid in [s1,s2,s3,s4,s5]: mark_attendance(sid, sess3, code3)
    session_attendance_sheet(sess1)
    student_attendance_summary(s1)
    low_attendance_alert(80)
    attendance_report()

if __name__ == "__main__":
    main()
