# Fleet Management System with Fuel and Maintenance Tracking

from datetime import date, timedelta

vehicles = {}
fuel_logs = []
maintenance_logs = []
_vid = 1

def add_vehicle(reg_no, make, model, year, fuel_type="Diesel"):
    vehicles[reg_no] = {
        "make": make, "model": model, "year": year,
        "fuel_type": fuel_type, "total_km": 0,
        "total_fuel_litres": 0, "last_service_km": 0,
        "next_service_km": 5000
    }
    print(f"  [{reg_no}] {year} {make} {model} | Fuel: {fuel_type}")

def log_fuel(reg_no, litres, cost_per_litre, km_reading, log_date=None):
    if reg_no not in vehicles:
        print("  Vehicle not found.")
        return
    d = log_date or date.today()
    total_cost = round(litres * cost_per_litre, 2)
    vehicles[reg_no]["total_fuel_litres"] += litres
    prev_km = vehicles[reg_no]["total_km"]
    if km_reading > prev_km:
        vehicles[reg_no]["total_km"] = km_reading
    fuel_logs.append({
        "reg": reg_no, "litres": litres, "cost_per_litre": cost_per_litre,
        "total_cost": total_cost, "km": km_reading, "date": d
    })
    print(f"  [{reg_no}] Fuel: {litres}L @ Rs.{cost_per_litre} = Rs.{total_cost} | KM: {km_reading}")

def schedule_maintenance(reg_no, task, scheduled_date, estimated_cost):
    if reg_no not in vehicles:
        print("  Vehicle not found.")
        return
    maintenance_logs.append({
        "reg": reg_no, "task": task,
        "scheduled": scheduled_date, "cost": estimated_cost,
        "status": "Scheduled"
    })
    print(f"  [{reg_no}] Maintenance: {task} | Date: {scheduled_date} | Est. Rs.{estimated_cost}")

def complete_maintenance(reg_no, task):
    for m in maintenance_logs:
        if m["reg"] == reg_no and m["task"] == task and m["status"] == "Scheduled":
            m["status"] = "Completed"
            vehicles[reg_no]["last_service_km"] = vehicles[reg_no]["total_km"]
            vehicles[reg_no]["next_service_km"] = vehicles[reg_no]["total_km"] + 5000
            print(f"  [{reg_no}] '{task}' completed. Next service at {vehicles[reg_no]['next_service_km']} km")
            return
    print(f"  Scheduled maintenance '{task}' not found for {reg_no}.")

def fuel_efficiency(reg_no):
    if reg_no not in vehicles:
        print("  Vehicle not found.")
        return
    v = vehicles[reg_no]
    logs = [f for f in fuel_logs if f["reg"] == reg_no]
    if len(logs) < 2:
        print(f"  [{reg_no}] Insufficient fuel logs for efficiency calc.")
        return
    km_span = logs[-1]["km"] - logs[0]["km"]
    total_litres = sum(f["litres"] for f in logs[1:])
    if total_litres == 0:
        return
    kmpl = round(km_span / total_litres, 2)
    print(f"  [{reg_no}] Fuel Efficiency: {kmpl} km/L over {km_span} km")
    return kmpl

def fleet_report():
    print(f"\n{'='*60}")
    print("  FLEET PERFORMANCE REPORT")
    print(f"{'='*60}")
    total_fuel_cost = sum(f["total_cost"] for f in fuel_logs)
    total_maint     = sum(m["cost"] for m in maintenance_logs if m["status"] == "Completed")
    print(f"  {'Reg No':<12} {'Vehicle':<22} {'KM':>8} {'Fuel(L)':>9} {'Eff.(km/L)':>11}")
    for reg, v in vehicles.items():
        logs = [f for f in fuel_logs if f["reg"] == reg]
        eff = "N/A"
        if len(logs) >= 2:
            km_span = logs[-1]["km"] - logs[0]["km"]
            litres  = sum(f["litres"] for f in logs[1:])
            if litres:
                eff = f"{km_span/litres:.1f}"
        print(f"  {reg:<12} {v['make']+' '+v['model']:<22} {v['total_km']:>8} {v['total_fuel_litres']:>9.1f} {eff:>11}")
    print(f"\n  Total Fuel Cost   : Rs.{total_fuel_cost:,.2f}")
    print(f"  Total Maint Cost  : Rs.{total_maint:,.2f}")
    upcoming = [m for m in maintenance_logs if m["status"] == "Scheduled"]
    print(f"  Upcoming Services : {len(upcoming)}")
    for m in upcoming:
        print(f"    [{m['reg']}] {m['task']} on {m['scheduled']}")
    print(f"{'='*60}")

def main():
    print("=== Fleet Management System ===")
    add_vehicle("MH12AB1234", "Tata",   "Ace",    2020)
    add_vehicle("DL05CD5678", "Ashok",  "Leyland",2019)
    add_vehicle("KA03EF9012", "Toyota", "Innova", 2022, "Petrol")
    today = date.today()
    log_fuel("MH12AB1234", 40, 92.3, 15000, today)
    log_fuel("MH12AB1234", 45, 92.5, 15600, today)
    log_fuel("DL05CD5678", 60, 92.0, 22000, today)
    log_fuel("DL05CD5678", 55, 92.1, 22800, today)
    log_fuel("KA03EF9012", 35, 106.5,8000, today)
    schedule_maintenance("MH12AB1234","Oil Change",  str(today + timedelta(days=7)),  2500)
    schedule_maintenance("DL05CD5678","Tyre Rotation",str(today + timedelta(days=3)),1800)
    complete_maintenance("MH12AB1234","Oil Change")
    fuel_efficiency("MH12AB1234")
    fuel_efficiency("DL05CD5678")
    fleet_report()

if __name__ == "__main__":
    main()
