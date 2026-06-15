# Movie Ticket Booking System with Seat Map Visualization

import random, string

ROWS = 5
COLS = 8
TICKET_PRICE = 200
movies = ["Inception", "Avengers: Endgame", "RRR", "KGF Chapter 2", "Pathaan"]
seats = {f"{chr(65+r)}{c+1}": None for r in range(ROWS) for c in range(COLS)}
bookings = {}

def display_seat_map():
    print("\n     " + "  ".join(f"{i+1:02}" for i in range(COLS)))
    for r in range(ROWS):
        row_label = chr(65 + r)
        row_cells = []
        for c in range(COLS):
            sid = f"{row_label}{c+1}"
            row_cells.append("[X]" if seats[sid] else "[ ]")
        print(f"  {row_label}  " + " ".join(row_cells))
    print("\n  [ ] = Available    [X] = Booked")

def select_movie():
    print("\n  Available Movies:")
    for i, m in enumerate(movies, 1):
        print(f"    {i}. {m}")
    ch = int(input("  Select number: "))
    return movies[ch - 1] if 1 <= ch <= len(movies) else None

def book_ticket(name, movie):
    display_seat_map()
    sid = input("  Enter seat (e.g. B3): ").strip().upper()
    if sid not in seats:
        print("  Invalid seat ID.")
        return None
    if seats[sid]:
        print(f"  Seat {sid} is already booked!")
        return None
    tid = "TKT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    seats[sid] = {"customer": name, "movie": movie, "ticket": tid}
    bookings[tid] = {"seat": sid, "customer": name, "movie": movie}
    print(f"\n  ✔ Booking Confirmed!")
    print(f"  Name      : {name}")
    print(f"  Movie     : {movie}")
    print(f"  Seat      : {sid}")
    print(f"  Amount    : Rs.{TICKET_PRICE}")
    print(f"  Ticket ID : {tid}")
    return tid

def cancel_ticket(tid):
    if tid not in bookings:
        print("  Ticket not found.")
        return False
    info = bookings.pop(tid)
    seats[info["seat"]] = None
    print(f"  Cancelled: {tid} | Seat {info['seat']} freed | Movie: {info['movie']}")
    return True

def booking_summary():
    print(f"\n{'='*45}")
    print("  BOOKING SUMMARY")
    print(f"{'='*45}")
    if not bookings:
        print("  No active bookings.")
        return
    for tid, info in bookings.items():
        print(f"  {tid} | {info['customer']:<15} | Seat {info['seat']} | {info['movie']}")
    total_rev = len(bookings) * TICKET_PRICE
    available = sum(1 for v in seats.values() if v is None)
    print(f"\n  Booked Seats   : {len(bookings)}")
    print(f"  Available Seats: {available}")
    print(f"  Total Revenue  : Rs.{total_rev}")
    print(f"{'='*45}")

def main():
    print("=== Movie Ticket Booking System ===")
    while True:
        print("\n  1. Book Ticket\n  2. Cancel Ticket\n  3. View Seat Map\n  4. Summary\n  5. Exit")
        ch = input("  Choice: ").strip()
        if ch == "1":
            name = input("  Customer Name: ").strip()
            movie = select_movie()
            if movie:
                book_ticket(name, movie)
        elif ch == "2":
            tid = input("  Ticket ID: ").strip().upper()
            cancel_ticket(tid)
        elif ch == "3":
            display_seat_map()
        elif ch == "4":
            booking_summary()
        elif ch == "5":
            print("  Goodbye!")
            break
        else:
            print("  Invalid option.")

if __name__ == "__main__":
    main()
