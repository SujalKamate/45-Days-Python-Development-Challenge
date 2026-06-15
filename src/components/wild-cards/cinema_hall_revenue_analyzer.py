# Cinema Hall Revenue Analyzer with Ticket Sales Tracking

from datetime import date, timedelta

HALLS = {
    "Hall 1": {"capacity": 200, "seat_types": {"Gold":80, "Silver":100, "Bronze":20}},
    "Hall 2": {"capacity": 150, "seat_types": {"Gold":60, "Silver":70,  "Bronze":20}},
    "Hall 3": {"capacity": 100, "seat_types": {"Gold":40, "Silver":50,  "Bronze":10}},
}
PRICES = {"Gold": 350, "Silver": 250, "Bronze": 150}
shows   = {}
sales   = []
_show_id = 1

def add_show(movie, hall, show_time, show_date=None):
    global _show_id
    if hall not in HALLS: print(f"  Invalid hall."); return None
    sid  = f"SHW{_show_id:04d}"; _show_id += 1
    d    = show_date or date.today()
    seat_avail = dict(HALLS[hall]["seat_types"])
    shows[sid] = {"movie":movie, "hall":hall, "time":show_time,
                  "date":d, "seats_sold":{k:0 for k in PRICES},
                  "seats_avail":seat_avail, "revenue":0}
    print(f"  [{sid}] {movie} | {hall} | {show_time} | {d}")
    return sid

def sell_tickets(show_id, seat_type, qty):
    if show_id not in shows: print("  Show not found."); return False
    if seat_type not in PRICES: print("  Invalid seat type."); return False
    sh = shows[show_id]
    if sh["seats_avail"][seat_type] < qty:
        print(f"  Only {sh['seats_avail'][seat_type]} {seat_type} seats available.")
        return False
    amount = qty * PRICES[seat_type]
    sh["seats_avail"][seat_type] -= qty
    sh["seats_sold"][seat_type]  += qty
    sh["revenue"] += amount
    sales.append({"show_id":show_id,"movie":sh["movie"],"hall":sh["hall"],
                  "type":seat_type,"qty":qty,"amount":amount,"date":sh["date"]})
    total_sold = sum(sh["seats_sold"].values())
    total_cap  = sum(HALLS[sh["hall"]]["seat_types"].values())
    occ = total_sold / total_cap * 100
    print(f"  [{show_id}] {qty}x {seat_type} = Rs.{amount} | Occupancy: {occ:.1f}%")
    return True

def show_report(show_id):
    if show_id not in shows: return
    sh = shows[show_id]
    total_cap  = sum(HALLS[sh["hall"]]["seat_types"].values())
    total_sold = sum(sh["seats_sold"].values())
    occ = total_sold / total_cap * 100
    print(f"\n  Show Report [{show_id}] — {sh['movie']}")
    print(f"  Hall: {sh['hall']} | {sh['date']} {sh['time']}")
    print(f"  {'Type':<10} {'Avail':>7} {'Sold':>6} {'Price':>7} {'Revenue':>10}")
    for stype in PRICES:
        rev = sh["seats_sold"][stype] * PRICES[stype]
        print(f"  {stype:<10} {sh['seats_avail'][stype]:>7} {sh['seats_sold'][stype]:>6} Rs.{PRICES[stype]:>5} Rs.{rev:>8}")
    print(f"  Occupancy: {total_sold}/{total_cap} ({occ:.1f}%) | Revenue: Rs.{sh['revenue']:,}")

def daily_revenue(report_date=None):
    d = report_date or date.today()
    day_shows   = {sid:sh for sid,sh in shows.items() if sh["date"] == d}
    day_sales   = [s for s in sales if s["date"] == d]
    total_rev   = sum(s["amount"] for s in day_sales)
    total_tickets = sum(s["qty"] for s in day_sales)
    print(f"\n{'='*50}\n  DAILY REVENUE — {d}\n{'='*50}")
    print(f"  Shows      : {len(day_shows)}")
    print(f"  Tickets    : {total_tickets}")
    print(f"  Revenue    : Rs.{total_rev:,}")
    for sid, sh in day_shows.items():
        cap  = sum(HALLS[sh["hall"]]["seat_types"].values())
        sold = sum(sh["seats_sold"].values())
        print(f"  [{sid}] {sh['movie']:<20} {sh['hall']} | {sold}/{cap} | Rs.{sh['revenue']:,}")

def revenue_by_hall():
    print(f"\n  Revenue by Hall:")
    for hall in HALLS:
        hall_rev  = sum(sh["revenue"] for sh in shows.values() if sh["hall"] == hall)
        hall_shows= sum(1 for sh in shows.values() if sh["hall"] == hall)
        print(f"  {hall:<10}: {hall_shows} shows | Rs.{hall_rev:,}")

def top_movies():
    movie_rev = {}
    for sh in shows.values():
        movie_rev[sh["movie"]] = movie_rev.get(sh["movie"], 0) + sh["revenue"]
    print("\n  Top Movies by Revenue:")
    for rank, (movie, rev) in enumerate(sorted(movie_rev.items(), key=lambda x:-x[1]), 1):
        print(f"  {rank}. {movie:<25} Rs.{rev:,}")

def main():
    print("=== Cinema Hall Revenue Analyzer ===")
    today = date.today()
    s1 = add_show("Avengers: Secret Wars", "Hall 1", "10:00 AM", today)
    s2 = add_show("Avengers: Secret Wars", "Hall 1", "02:00 PM", today)
    s3 = add_show("Pushpa 3",              "Hall 2", "11:00 AM", today)
    s4 = add_show("Pushpa 3",              "Hall 2", "07:00 PM", today)
    s5 = add_show("Dunki Returns",          "Hall 3", "04:00 PM", today)
    sell_tickets(s1, "Gold",   60); sell_tickets(s1, "Silver", 90); sell_tickets(s1, "Bronze", 15)
    sell_tickets(s2, "Gold",   45); sell_tickets(s2, "Silver", 70)
    sell_tickets(s3, "Gold",   55); sell_tickets(s3, "Silver", 65); sell_tickets(s3, "Bronze", 18)
    sell_tickets(s4, "Gold",   58); sell_tickets(s4, "Silver", 68)
    sell_tickets(s5, "Gold",   35); sell_tickets(s5, "Silver", 48)
    sell_tickets(s1, "Gold",   90)  # exceeds available
    show_report(s1)
    daily_revenue(today)
    revenue_by_hall()
    top_movies()

if __name__ == "__main__":
    main()
