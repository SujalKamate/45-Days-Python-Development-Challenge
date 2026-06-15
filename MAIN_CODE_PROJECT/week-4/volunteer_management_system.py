# Volunteer Management System with Participation Analytics

from datetime import date

volunteers = {}
events     = {}
participation = []
_vid = _eid = 1

def register_volunteer(name, email, skills, city):
    global _vid
    vid = f"VOL{_vid:04d}"; _vid += 1
    volunteers[vid] = {"name":name, "email":email, "skills":[s.lower() for s in skills],
                       "city":city, "events_attended":0, "total_hours":0, "active":True}
    print(f"  [{vid}] {name} | {city} | Skills: {skills}")
    return vid

def create_event(title, event_date, location, required_skills, max_volunteers, hours):
    global _eid
    eid = f"EVT{_eid:04d}"; _eid += 1
    events[eid] = {"title":title, "date":event_date, "location":location,
                   "required_skills":[s.lower() for s in required_skills],
                   "max_volunteers":max_volunteers, "hours":hours,
                   "registered":[], "attended":[]}
    print(f"  [{eid}] {title} | {event_date} | {location} | Max: {max_volunteers} volunteers")
    return eid

def register_for_event(vid, eid):
    if vid not in volunteers: print("  Volunteer not found."); return False
    if eid not in events: print("  Event not found."); return False
    ev = events[eid]; vol = volunteers[vid]
    if vid in ev["registered"]: print(f"  {vol['name']} already registered."); return False
    if len(ev["registered"]) >= ev["max_volunteers"]:
        print(f"  Event [{eid}] is full."); return False
    skill_match = any(s in vol["skills"] for s in ev["required_skills"])
    ev["registered"].append(vid)
    print(f"  [{vid}] {vol['name']} registered for [{eid}] {ev['title']}" +
          (" (skills match)" if skill_match else " (no skill match)"))
    return True

def mark_attendance(vid, eid):
    if vid not in volunteers or eid not in events:
        print("  Invalid IDs."); return
    ev = events[eid]
    if vid not in ev["registered"]: print(f"  {volunteers[vid]['name']} not registered."); return
    if vid in ev["attended"]: print("  Already marked."); return
    ev["attended"].append(vid)
    volunteers[vid]["events_attended"] += 1
    volunteers[vid]["total_hours"]     += ev["hours"]
    participation.append({"vid":vid,"eid":eid,"date":ev["date"],"hours":ev["hours"]})
    print(f"  [{vid}] {volunteers[vid]['name']} marked present for [{eid}] ({ev['hours']}h)")

def volunteer_profile(vid):
    if vid not in volunteers: return
    v = volunteers[vid]
    vol_events = [p for p in participation if p["vid"] == vid]
    print(f"\n  Profile: {v['name']} [{vid}]")
    print(f"  City     : {v['city']}  |  Email: {v['email']}")
    print(f"  Skills   : {', '.join(v['skills'])}")
    print(f"  Events   : {v['events_attended']}  |  Total Hours: {v['total_hours']}")
    for p in vol_events:
        ename = events[p["eid"]]["title"]
        print(f"    [{p['eid']}] {ename} | {p['date']} | {p['hours']}h")

def event_summary(eid):
    if eid not in events: return
    ev = events[eid]
    reg  = len(ev["registered"])
    att  = len(ev["attended"])
    rate = (att / reg * 100) if reg else 0
    print(f"\n  Event [{eid}]: {ev['title']}")
    print(f"  Date     : {ev['date']} | Location: {ev['location']}")
    print(f"  Registered: {reg}/{ev['max_volunteers']} | Attended: {att} ({rate:.0f}%)")
    for vid in ev["attended"]:
        print(f"    ✔ {volunteers[vid]['name']}")

def analytics_report():
    print(f"\n{'='*52}\n  VOLUNTEER ANALYTICS REPORT\n{'='*52}")
    total_hours = sum(v["total_hours"] for v in volunteers.values())
    top_vols = sorted(volunteers.items(), key=lambda x: -x[1]["total_hours"])[:3]
    print(f"  Total Volunteers : {len(volunteers)}")
    print(f"  Total Events     : {len(events)}")
    print(f"  Total Hours      : {total_hours}")
    total_participations = len(participation)
    print(f"  Total Part. Entries: {total_participations}")
    print("\n  Top Contributors:")
    for rank, (vid, v) in enumerate(top_vols, 1):
        print(f"  {rank}. {v['name']:<20} {v['events_attended']} events | {v['total_hours']}h")
    skill_freq = {}
    for v in volunteers.values():
        for s in v["skills"]:
            skill_freq[s] = skill_freq.get(s, 0) + 1
    top_skill = max(skill_freq, key=skill_freq.get) if skill_freq else "N/A"
    print(f"\n  Most Common Skill: {top_skill}")
    print(f"{'='*52}")

def main():
    print("=== Volunteer Management System ===")
    v1 = register_volunteer("Aarav Mehta",  "aarav@mail.com",  ["Teaching","Coding"],  "Delhi")
    v2 = register_volunteer("Bhavna Singh", "bhavna@mail.com", ["Medical","First Aid"], "Mumbai")
    v3 = register_volunteer("Chetan Rao",   "chetan@mail.com", ["Teaching","Sports"],  "Bangalore")
    v4 = register_volunteer("Divya Nair",   "divya@mail.com",  ["Cooking","Logistics"],"Chennai")
    v5 = register_volunteer("Eshan Kumar",  "eshan@mail.com",  ["Coding","Teaching"],  "Delhi")
    e1 = create_event("Tree Plantation Drive", date(2025,8,15), "Delhi Park",   ["Logistics"],      30, 4)
    e2 = create_event("Free Health Camp",       date(2025,8,20), "Community Hall",["Medical","First Aid"],15, 6)
    e3 = create_event("Code for Kids",          date(2025,9,5),  "City Library", ["Teaching","Coding"],  20, 3)
    for vid in [v1,v2,v3,v4,v5]: register_for_event(vid, e1)
    for vid in [v2,v3,v5]:       register_for_event(vid, e2)
    for vid in [v1,v3,v5]:       register_for_event(vid, e3)
    for vid in [v1,v2,v3,v4]:    mark_attendance(vid, e1)
    for vid in [v2,v5]:           mark_attendance(vid, e2)
    for vid in [v1,v3,v5]:        mark_attendance(vid, e3)
    volunteer_profile(v1)
    event_summary(e1)
    analytics_report()

if __name__ == "__main__":
    main()
