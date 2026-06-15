# Inventory Demand Forecast Simulator with Trend-Based Predictions

import statistics
from datetime import date

products    = {}
sales_data  = {}
forecasts   = {}
_pid = 1

def add_product(name, category, unit_cost, reorder_point, lead_time_days):
    global _pid
    pid = f"PRD{_pid:04d}"; _pid += 1
    products[pid] = {"name":name,"category":category,"unit_cost":unit_cost,
                     "reorder_point":reorder_point,"lead_time":lead_time_days,
                     "current_stock":0}
    sales_data[pid] = []
    print(f"  [{pid}] {name} | Category:{category} | Cost:Rs.{unit_cost} | Reorder@{reorder_point}")
    return pid

def set_stock(pid, qty):
    if pid not in products: return
    products[pid]["current_stock"] = qty
    print(f"  [{pid}] Stock set to {qty} units")

def record_sales(pid, monthly_sales_list):
    if pid not in products: print("  Product not found."); return
    sales_data[pid].extend(monthly_sales_list)
    print(f"  [{pid}] {products[pid]['name']}: {len(monthly_sales_list)} months of data recorded.")

def moving_average(pid, window=3):
    data = sales_data.get(pid, [])
    if len(data) < window: return None
    return round(sum(data[-window:]) / window, 2)

def trend_slope(pid):
    data = sales_data.get(pid, [])
    if len(data) < 3: return 0
    n  = len(data)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(data) / n
    num = sum((xs[i] - x_mean) * (data[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return round(num / den, 2) if den else 0

def forecast_demand(pid, months_ahead=3):
    if pid not in products: print("  Not found."); return None
    data  = sales_data.get(pid, [])
    if len(data) < 3: print(f"  [{pid}] Insufficient data (need ≥3 months)."); return None
    slope = trend_slope(pid)
    base  = moving_average(pid)
    predictions = []
    for i in range(1, months_ahead + 1):
        pred = max(0, round(base + slope * i, 0))
        predictions.append(int(pred))
    forecasts[pid] = predictions
    avg_pred = round(sum(predictions) / len(predictions), 1)
    print(f"  [{pid}] {products[pid]['name']} | Forecast {months_ahead}mo: {predictions} | Avg:{avg_pred}")
    return predictions

def reorder_recommendations():
    print(f"\n--- Reorder Recommendations ---")
    today = date.today()
    found = False
    for pid, p in products.items():
        pred  = forecasts.get(pid, [0])
        monthly_demand = pred[0] if pred else moving_average(pid) or 0
        stock = p["current_stock"]
        rp    = p["reorder_point"]
        coverage = (stock / monthly_demand * 30) if monthly_demand else float('inf')
        if stock <= rp:
            reorder_qty = max(monthly_demand * 2, rp * 2) - stock
            found = True
            print(f"  ⚠ [{pid}] {p['name']:<22} Stock:{stock:>5} | Reorder:{int(reorder_qty)} | Coverage:{coverage:.0f} days")
        elif coverage < p["lead_time"] + 7:
            found = True
            print(f"  ⚠ [{pid}] {p['name']:<22} Stock:{stock:>5} | Only {coverage:.0f} days coverage (Lead:{p['lead_time']}d)")
    if not found: print("  All products adequately stocked.")

def demand_analysis(pid):
    if pid not in sales_data or not sales_data[pid]: return
    data = sales_data[pid]
    slope = trend_slope(pid)
    trend_desc = "📈 Growing" if slope > 2 else ("📉 Declining" if slope < -2 else "➡ Stable")
    print(f"\n  Demand Analysis [{pid}] {products[pid]['name']}:")
    print(f"  Historical (months): {data}")
    print(f"  Avg Monthly Demand : {round(statistics.mean(data),1)}")
    print(f"  Std Deviation      : {round(statistics.stdev(data),1)}" if len(data)>1 else "")
    print(f"  Peak Month         : {max(data)} units")
    print(f"  Low Month          : {min(data)} units")
    print(f"  Trend Slope        : {slope} ({trend_desc})")
    if pid in forecasts:
        print(f"  Forecast           : {forecasts[pid]}")

def forecasting_report():
    print(f"\n{'='*56}\n  INVENTORY DEMAND FORECAST REPORT\n{'='*56}")
    print(f"  {'ID':<8} {'Product':<22} {'Stock':>7} {'Avg Dem':>9} {'Slope':>7} {'Forecast'}")
    for pid, p in products.items():
        data  = sales_data.get(pid,[])
        avg   = round(statistics.mean(data),1) if data else 0
        slope = trend_slope(pid)
        pred  = str(forecasts.get(pid,["N/A"]))[:18]
        print(f"  {pid:<8} {p['name']:<22} {p['current_stock']:>7} {avg:>9} {slope:>7} {pred}")
    print(f"{'='*56}")

def main():
    print("=== Inventory Demand Forecast Simulator ===")
    p1 = add_product("Paracetamol 500mg","Pharma",    2.5,  500, 7)
    p2 = add_product("Hand Sanitizer 1L","Healthcare",45.0, 200, 5)
    p3 = add_product("N95 Masks (box)", "Safety",    180.0, 100, 10)
    p4 = add_product("Vitamin C Tablets","Supplement", 6.0,  300, 7)
    set_stock(p1, 800); set_stock(p2, 180); set_stock(p3, 90); set_stock(p4, 350)
    record_sales(p1, [420,450,480,510,490,520,550,530,560,580,600,590])
    record_sales(p2, [150,160,180,200,220,240,210,230,250,260,280,300])
    record_sales(p3, [80, 90, 100,120,110,130,105,115,125,118,130,140])
    record_sales(p4, [280,260,270,290,300,310,295,285,305,315,325,310])
    for pid in [p1, p2, p3, p4]:
        forecast_demand(pid, months_ahead=3)
    demand_analysis(p1)
    demand_analysis(p2)
    reorder_recommendations()
    forecasting_report()

if __name__ == "__main__":
    main()
