# Weather Data Logger with Historical Trend Analysis

from datetime import date, timedelta
import statistics

weather_log = []

def log_weather(city, log_date, temp_max, temp_min, humidity, rainfall_mm, condition):
    if temp_min > temp_max:
        print("  Min temp cannot exceed max temp.")
        return None
    entry = {
        "city": city, "date": log_date,
        "temp_max": temp_max, "temp_min": temp_min,
        "temp_avg": round((temp_max + temp_min) / 2, 1),
        "humidity": humidity, "rainfall": rainfall_mm,
        "condition": condition
    }
    weather_log.append(entry)
    print(f"  [{log_date}] {city} | Max:{temp_max}°C Min:{temp_min}°C Hum:{humidity}% Rain:{rainfall_mm}mm | {condition}")
    return entry

def city_summary(city, start_date=None, end_date=None):
    entries = [e for e in weather_log if e["city"] == city]
    if start_date:
        entries = [e for e in entries if e["date"] >= start_date]
    if end_date:
        entries = [e for e in entries if e["date"] <= end_date]
    if not entries:
        print(f"  No data for {city}.")
        return
    temps_max  = [e["temp_max"] for e in entries]
    temps_min  = [e["temp_min"] for e in entries]
    rainfalls  = [e["rainfall"] for e in entries]
    humidities = [e["humidity"] for e in entries]
    print(f"\n  Weather Summary — {city}")
    print(f"  Period  : {entries[0]['date']} to {entries[-1]['date']} ({len(entries)} days)")
    print(f"  Temp Max: avg {round(statistics.mean(temps_max),1)}°C | high {max(temps_max)}°C | low {min(temps_max)}°C")
    print(f"  Temp Min: avg {round(statistics.mean(temps_min),1)}°C | high {max(temps_min)}°C | low {min(temps_min)}°C")
    print(f"  Humidity: avg {round(statistics.mean(humidities),1)}%")
    print(f"  Rainfall: total {sum(rainfalls):.1f} mm | max day {max(rainfalls)} mm")
    rainy_days = sum(1 for r in rainfalls if r > 0)
    print(f"  Rainy Days: {rainy_days}/{len(entries)}")

def extremes(city):
    entries = [e for e in weather_log if e["city"] == city]
    if not entries:
        return
    hottest  = max(entries, key=lambda x: x["temp_max"])
    coldest  = min(entries, key=lambda x: x["temp_min"])
    rainiest = max(entries, key=lambda x: x["rainfall"])
    most_hum = max(entries, key=lambda x: x["humidity"])
    print(f"\n  Extremes — {city}")
    print(f"  Hottest  : {hottest['date']}  {hottest['temp_max']}°C ({hottest['condition']})")
    print(f"  Coldest  : {coldest['date']}  {coldest['temp_min']}°C ({coldest['condition']})")
    print(f"  Rainiest : {rainiest['date']} {rainiest['rainfall']} mm")
    print(f"  Most Humid: {most_hum['date']} {most_hum['humidity']}%")

def monthly_comparison(city):
    entries = [e for e in weather_log if e["city"] == city]
    monthly = {}
    for e in entries:
        key = e["date"].strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = []
        monthly[key].append(e)
    print(f"\n  Monthly Comparison — {city}")
    print(f"  {'Month':<10} {'AvgMax':>8} {'AvgMin':>8} {'Rain(mm)':>10} {'Condition'}")
    for month in sorted(monthly):
        es = monthly[month]
        avg_max  = round(statistics.mean(e["temp_max"] for e in es), 1)
        avg_min  = round(statistics.mean(e["temp_min"] for e in es), 1)
        rain_tot = sum(e["rainfall"] for e in es)
        conditions = [e["condition"] for e in es]
        common_cond = max(set(conditions), key=conditions.count)
        print(f"  {month:<10} {avg_max:>7}°C {avg_min:>7}°C {rain_tot:>9.1f}  {common_cond}")

def main():
    print("=== Weather Data Logger ===")
    city = "Chandigarh"
    base = date(2025, 6, 1)
    data = [
        (38, 26, 60,  0,   "Sunny"),   (40, 27, 55,  0,   "Hot"),
        (37, 25, 65,  5,   "Partly Cloudy"), (35, 24, 75, 22, "Rainy"),
        (33, 23, 80, 18,   "Thunderstorm"),  (36, 25, 70,  0, "Sunny"),
        (39, 27, 58,  0,   "Hot"),     (41, 28, 52,  0,   "Sunny"),
        (34, 22, 82, 30,   "Heavy Rain"),    (32, 21, 88, 45, "Heavy Rain"),
        (31, 20, 90, 50,   "Thunderstorm"), (33, 22, 78, 12, "Rainy"),
        (36, 24, 68,  0,   "Partly Cloudy"),(38, 26, 60,  0, "Sunny"),
    ]
    for i, (mx, mn, hum, rain, cond) in enumerate(data):
        log_weather(city, base + timedelta(days=i), mx, mn, hum, rain, cond)
    city_summary(city)
    extremes(city)
    monthly_comparison(city)

if __name__ == "__main__":
    main()
