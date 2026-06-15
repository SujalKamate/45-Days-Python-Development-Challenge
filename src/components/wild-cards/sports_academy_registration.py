# Sports Academy Registration System with Batch Allocation

from datetime import date

SPORTS = ["Cricket", "Football", "Badminton", "Swimming", "Tennis", "Athletics", "Basketball"]
BATCHES = {
    "Morning":   {"time": "06:00-08:00", "capacity": 20},
    "Afternoon": {"time": "14:00-16:00", "capacity": 15},
    "Evening":   {"time": "17:00-19:00", "capacity": 25},
}
FEE_PER_MONTH = {"Cricket":2000,"Football":1800,"Badminton":1500,"Swimming":2500,
                 "Tennis":2200,"Athletics":1200,"Basketball":1600}

students = {}
batches  = {f"{s}-{b}": {"sport":s,"batch":b,"enrolled":[]} for s in SPORTS for b in BATCHES}
attendance= {}
_sid = 1

def register_student(name, age, sport, batch, join_date=None):
    global _sid
    if sport not in SPORTS: print(f"  Invalid sport."); return None
    if batch not in BATCHES: print(f"  Invalid batch."); return None
    batch_key = f"{sport}-{batch}"
    cap = BATCHES[batch]["capacity"]
    enrolled = len(batches[batch_key]["enrolled"])
    if enrolled >= cap: print(f"  {sport} {batch} batch is full ({cap}/{cap})."); return None
    sid = f"SPA{_sid:04d}"; _sid += 1
    join = join_date or date.today()
    fee  = FEE_PER_MONTH[sport]
    students[sid] = {"name":name, "age":age, "sport":sport, "batch":batch,
                     "join_date":join, "monthly_fee":fee, "active":True, "attendance":[]}
    batches[batch_key]["enrolled"].append(sid)
    print(f"  [{sid}] {name} | {sport} | {batch} ({BATCHES[batch]['time']}) | Rs.{fee}/mo")
    return sid

def mark_attendance(sid, session_date=None):
    if sid not in students: print("  Student not found."); return
    d = session_date or date.today()
    if d in students[sid]["attendance"]:
        print(f"  [{sid}] Already marked for {d}.")
        return
    students[sid]["attendance"].append(d)
    print(f"  [{sid}] {students[sid]['name']} — Attendance marked for {d}")

def transfer_batch(sid, new_batch):
    if sid not in students: print("  Not found."); return
    if new_batch not in BATCHES: print("  Invalid batch."); return
    s = students[sid]
    old_key = f"{s['sport']}-{s['batch']}"
    new_key = f"{s['sport']}-{new_batch}"
    if len(batches[new_key]["enrolled"]) >= BATCHES[new_batch]["capacity"]:
        print(f"  {new_batch} batch is full."); return
    batches[old_key]["enrolled"].remove(sid)
    batches[new_key]["enrolled"].append(sid)
    old = s["batch"]; s["batch"] = new_batch
    print(f"  [{sid}] {s['name']} transferred: {old} → {new_batch}")

def attendance_report(sid):
    if sid not in students: return
    s = students[sid]
    total = len(s["attendance"])
    print(f"\n  Attendance: {s['name']} [{sid}]")
    print(f"  Sessions attended: {total}")
    for d in sorted(s["attendance"]):
        print(f"    ✔ {d}")

def batch_roster(sport, batch):
    key = f"{sport}-{batch}"
    if key not in batches: print("  Invalid combination."); return
    enrolled_ids = batches[key]["enrolled"]
    cap = BATCHES[batch]["capacity"]
    print(f"\n  Roster: {sport} — {batch} ({BATCHES[batch]['time']}) [{len(enrolled_ids)}/{cap}]")
    for sid in enrolled_ids:
        s = students[sid]
        att = len(s["attendance"])
        print(f"  {sid} | {s['name']:<20} | Age:{s['age']} | Joined:{s['join_date']} | Sessions:{att}")

def participant_report():
    print(f"\n{'='*52}\n  SPORTS ACADEMY PARTICIPANT REPORT\n{'='*52}")
    sport_counts = {s: 0 for s in SPORTS}
    batch_counts = {b: 0 for b in BATCHES}
    total_revenue = 0
    for s in students.values():
        if s["active"]:
            sport_counts[s["sport"]] += 1
            batch_counts[s["batch"]] += 1
            total_revenue += s["monthly_fee"]
    print("  By Sport:")
    for sport, count in sorted(sport_counts.items(), key=lambda x: -x[1]):
        if count: print(f"    {sport:<14}: {count} student(s)  Rs.{count*FEE_PER_MONTH[sport]:,}/mo")
    print("\n  By Batch:")
    for batch, count in batch_counts.items():
        cap = BATCHES[batch]["capacity"]
        print(f"    {batch:<12}: {count}/{cap}")
    print(f"\n  Total Students : {len(students)}")
    print(f"  Monthly Revenue: Rs.{total_revenue:,}")
    print(f"{'='*52}")

def main():
    print("=== Sports Academy Registration System ===")
    s1 = register_student("Aarav Mehta",   16, "Cricket",    "Morning")
    s2 = register_student("Bhavna Singh",  14, "Badminton",  "Evening")
    s3 = register_student("Chetan Rao",    17, "Cricket",    "Morning")
    s4 = register_student("Divya Nair",    15, "Swimming",   "Afternoon")
    s5 = register_student("Eshan Kumar",   18, "Football",   "Evening")
    s6 = register_student("Fatima Sheikh", 13, "Tennis",     "Morning")
    s7 = register_student("Gaurav Das",    16, "Cricket",    "Evening")
    s8 = register_student("Hira Patel",    14, "Athletics",  "Morning")
    today = date.today()
    for sid in [s1, s2, s3, s4]:
        mark_attendance(sid, today)
    mark_attendance(s1, today)  # duplicate
    transfer_batch(s3, "Evening")
    batch_roster("Cricket", "Morning")
    attendance_report(s1)
    participant_report()

if __name__ == "__main__":
    main()
