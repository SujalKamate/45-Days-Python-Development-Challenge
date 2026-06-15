# Hotel Booking Management System with Room Categories

from datetime import date, timedelta

ROOM_CATEGORIES = {
    "Standard":  {"price": 2000, "capacity": 2},
    "Deluxe":    {"price": 3500, "capacity": 2},
    "Suite":     {"price": 6000, "capacity": 4},
    "Executive": {"price": 5000, "capacity": 3},
}
rooms = {}
bookings = {}
_bid = 1

def setup_rooms():
    config = [("Standard",10),("Deluxe",8),("Suite",4),("Executive",6)]
    for cat, count in config:
        for i in range(1, count+1):
            rid = f"{cat[:3].upper()}{i:02d}"
            rooms[rid] = {"category": cat, "booked": False, "booking_id": None}
    print(f"  {len(rooms)} rooms initialized.")

def available_rooms(category=None):
    avail = {rid: r for rid, r in rooms.items()
             if not r["booked"] and (category is None or r["category"] == category)}
    return avail

def book_room(guest_name, category, check_in_str, check_out_str):
    global _bid
    avail = available_rooms(category)
    if not avail:
        print(f"  No available {category} rooms.")
        return None
    check_in  = date.fromisoformat(check_in_str)
    check_out = date.fromisoformat(check_out_str)
    nights = (check_out - check_in).days
    if nights <= 0:
        print("  Check-out must be after check-in.")
        return None
    rid = next(iter(avail))
    price_per_night = ROOM_CATEGORIES[category]["price"]
    total = price_per_night * nights
    bid = f"BKG{_bid:04d}"
    _bid += 1
    rooms[rid]["booked"] = True
    rooms[rid]["booking_id"] = bid
    bookings[bid] = {
        "guest": guest_name, "room": rid, "category": category,
        "check_in": check_in, "check_out": check_out,
        "nights": nights, "total": total, "status": "Active"
    }
    print(f"  [{bid}] {guest_name} | Room {rid} ({category}) | {check_in} → {check_out} | Rs.{total}")
    return bid

def cancel_booking(bid):
    if bid not in bookings:
        print("  Booking not found.")
        return
    b = bookings[bid]
    if b["status"] == "Cancelled":
        print("  Already cancelled.")
        return
    rooms[b["room"]]["booked"] = False
    rooms[b["room"]]["booking_id"] = None
    b["status"] = "Cancelled"
    print(f"  [{bid}] Cancelled | Room {b['room']} now available.")

def checkout(bid):
    if bid not in bookings:
        print("  Booking not found.")
        return
    b = bookings[bid]
    b["status"] = "Checked Out"
    rooms[b["room"]]["booked"] = False
    rooms[b["room"]]["booking_id"] = None
    print(f"  [{bid}] Checked out | Guest: {b['guest']} | Room {b['room']} freed.")

def occupancy_report():
    print(f"\n{'='*50}")
    print("  OCCUPANCY REPORT")
    print(f"{'='*50}")
    for cat in ROOM_CATEGORIES:
        total = sum(1 for r in rooms.values() if r["category"] == cat)
        occupied = sum(1 for r in rooms.values() if r["category"] == cat and r["booked"])
        pct = (occupied / total * 100) if total else 0
        bar = "█" * int(pct // 10)
        print(f"  {cat:<12}: {occupied:>2}/{total} occupied  {pct:5.1f}%  {bar}")
    active_rev = sum(b["total"] for b in bookings.values() if b["status"] == "Active")
    total_rev  = sum(b["total"] for b in bookings.values() if b["status"] != "Cancelled")
    print(f"\n  Active Bookings Revenue : Rs.{active_rev:,.0f}")
    print(f"  Total Revenue (all)     : Rs.{total_rev:,.0f}")
    print(f"{'='*50}")

def main():
    print("=== Hotel Booking Management System ===")
    setup_rooms()
    today = date.today()
    book_room("Amit Verma",  "Standard",  str(today), str(today + timedelta(days=3)))
    book_room("Priya Kapoor","Deluxe",    str(today), str(today + timedelta(days=2)))
    book_room("Raj Malhotra","Suite",     str(today), str(today + timedelta(days=5)))
    book_room("Nisha Roy",   "Executive", str(today), str(today + timedelta(days=1)))
    book_room("Suresh B",    "Deluxe",    str(today), str(today + timedelta(days=4)))
    cancel_booking("BKG0004")
    checkout("BKG0001")
    occupancy_report()

if __name__ == "__main__":
    main()
