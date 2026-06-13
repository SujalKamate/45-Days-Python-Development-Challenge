# Time Zone Converter with World Clock Support

from datetime import datetime, timezone, timedelta

ZONES = {
    "New York":  ("EST", -5),  "London":    ("GMT",  0),
    "Paris":     ("CET",  1),  "Dubai":     ("GST",  4),
    "Mumbai":    ("IST",  5.5),"Bangkok":   ("ICT",  7),
    "Singapore": ("SGT",  8),  "Tokyo":     ("JST",  9),
    "Sydney":    ("AEDT",11),  "Auckland":  ("NZST",12),
    "Los Angeles":("PST",-8),  "Chicago":   ("CST", -6),
}
favourites = []

def get_city_time(city, ref_utc=None):
    if city not in ZONES:
        return None
    _, offset = ZONES[city]
    utc = ref_utc or datetime.now(timezone.utc)
    delta = timedelta(hours=offset)
    city_time = utc + delta
    return city_time

def world_clock(cities=None):
    cities = cities or list(ZONES.keys())
    utc_now = datetime.now(timezone.utc)
    print(f"\n--- World Clock (UTC: {utc_now.strftime('%Y-%m-%d %H:%M')}) ---")
    for city in cities:
        if city not in ZONES:
            print(f"  {city:<15} — Unknown city")
            continue
        abbr, offset = ZONES[city]
        t = get_city_time(city, utc_now)
        sign = "+" if offset >= 0 else ""
        print(f"  {city:<15} [{abbr} UTC{sign}{offset}]  {t.strftime('%Y-%m-%d  %H:%M:%S')}")

def convert_time(from_city, to_city, hour, minute=0, year=None, month=None, day=None):
    if from_city not in ZONES or to_city not in ZONES:
        print("  One or both cities not found.")
        return
    _, from_offset = ZONES[from_city]
    _, to_offset   = ZONES[to_city]
    now = datetime.now(timezone.utc)
    y, mo, d = year or now.year, month or now.month, day or now.day
    from_dt = datetime(y, mo, d, int(hour), minute) - timedelta(hours=from_offset)
    to_dt   = from_dt + timedelta(hours=to_offset)
    diff    = to_offset - from_offset
    sign    = "+" if diff >= 0 else ""
    print(f"\n  {from_city} ({ZONES[from_city][0]}): {hour:02d}:{minute:02d}  {y}-{mo:02d}-{d:02d}")
    print(f"  {to_city}   ({ZONES[to_city][0]}):   {to_dt.strftime('%H:%M  %Y-%m-%d')}")
    print(f"  Difference: {sign}{diff} hour(s)")

def add_favourite(city):
    if city not in ZONES:
        print(f"  '{city}' not in zone database.")
        return
    if city not in favourites:
        favourites.append(city)
        print(f"  '{city}' added to favourites.")
    else:
        print(f"  '{city}' already in favourites.")

def show_favourites():
    if not favourites:
        print("  No favourite cities saved.")
        return
    print("\n--- Favourite Cities ---")
    world_clock(favourites)

def list_available_cities():
    print("\n--- Available Cities ---")
    for city, (abbr, offset) in ZONES.items():
        sign = "+" if offset >= 0 else ""
        print(f"  {city:<16} {abbr}  (UTC{sign}{offset})")

def date_line_check(city1, city2):
    t1 = get_city_time(city1)
    t2 = get_city_time(city2)
    if t1 and t2:
        if t1.date() != t2.date():
            print(f"\n  ⚠ Date differs! {city1}: {t1.strftime('%b %d')}  vs  {city2}: {t2.strftime('%b %d')}")
        else:
            print(f"\n  Same date in both cities: {t1.strftime('%b %d, %Y')}")

def main():
    print("=== Time Zone Converter with World Clock ===")
    list_available_cities()
    world_clock(["Mumbai", "London", "New York", "Tokyo", "Sydney"])
    convert_time("Mumbai", "New York", 9, 30)
    convert_time("London", "Tokyo", 14, 0)
    convert_time("Los Angeles", "Dubai", 23, 45)
    add_favourite("Mumbai")
    add_favourite("London")
    add_favourite("Tokyo")
    add_favourite("Unknown City")
    show_favourites()
    date_line_check("Los Angeles", "Auckland")

if __name__ == "__main__":
    main()
