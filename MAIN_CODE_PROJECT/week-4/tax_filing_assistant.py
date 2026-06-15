# Tax Filing Assistant with Deduction Calculator
TAX_SLABS_OLD = [(250000,0),(500000,0.05),(1000000,0.20),(float('inf'),0.30)]
TAX_SLABS_NEW = [(300000,0),(700000,0.05),(1000000,0.10),(1200000,0.15),
                  (1500000,0.20),(float('inf'),0.30)]
STD_DEDUCTION = 50000
REBATE_87A    = 12500
REBATE_LIMIT  = 500000
deductions_80 = {
    "80C":  ("Life Insurance/PF/ELSS/PPF", 150000),
    "80D":  ("Medical Insurance Premium",   25000),
    "80E":  ("Education Loan Interest",     None),
    "80G":  ("Charitable Donations",        None),
    "80TTA":("Savings Account Interest",    10000),
    "NPS":  ("NPS Contribution (80CCD1B)",  50000),
}
profiles = {}
_uid = 1
def add_profile(name, pan, age, regime="New"):
    global _uid
    uid = f"TAX{_uid:04d}"; _uid += 1
    profiles[uid] = {
        "name":name, "pan":pan, "age":age, "regime":regime,
        "income":{"salary":0,"hra":0,"lta":0,"other":0,"rental":0},
        "deductions":{}
    }
    print(f"  [{uid}] {name} | PAN: {pan} | Age: {age} | Regime: {regime}")
    return uid

def set_income(uid, salary=0, hra_exempt=0, lta_exempt=0, other_income=0, rental_income=0):
    if uid not in profiles: print("  Profile not found."); return
    profiles[uid]["income"] = {"salary":salary,"hra":hra_exempt,"lta":lta_exempt,
                                "other":other_income,"rental":rental_income}
    gross = salary + other_income + rental_income
    print(f"  [{uid}] Gross Income: Rs.{gross:,} | HRA exempt: Rs.{hra_exempt:,}")

def add_deduction(uid, section, amount):
    if uid not in profiles: print("  Profile not found."); return
    if section not in deductions_80:
        print(f"  Unknown section. Available: {list(deductions_80.keys())}"); return
    limit = deductions_80[section][1]
    capped = min(amount, limit) if limit else amount
    profiles[uid]["deductions"][section] = capped
    note = f" (capped from Rs.{amount:,})" if limit and amount > limit else ""
    print(f"  [{uid}] {section} deduction: Rs.{capped:,}{note}")

def calculate_tax(gross_income, slabs, surcharge_age=0):
    tax = 0; prev = 0
    for limit, rate in slabs:
        if gross_income <= prev: break
        taxable_in_slab = min(gross_income, limit) - prev
        tax += taxable_in_slab * rate
        prev = limit
    return round(tax, 2)

def compute_liability(uid):
    if uid not in profiles: print("  Profile not found."); return
    p   = profiles[uid]
    inc = p["income"]
    gross = inc["salary"] + inc["other"] + inc["rental"]
    ded   = p["deductions"]
    regime = p["regime"]
    if regime == "Old":
        net = gross - inc["hra"] - inc["lta"] - STD_DEDUCTION
        net -= sum(ded.values())
        net  = max(net, 0)
        tax  = calculate_tax(net, TAX_SLABS_OLD)
    else:
        net = gross - STD_DEDUCTION
        net  = max(net, 0)
        tax  = calculate_tax(net, TAX_SLABS_NEW)
    rebate = REBATE_87A if net <= REBATE_LIMIT else 0
    tax    = max(tax - rebate, 0)
    cess   = round(tax * 0.04, 2)
    total  = round(tax + cess, 2)
    effective = round(total / gross * 100, 2) if gross else 0
    print(f"\n{'='*52}")
    print(f"  TAX COMPUTATION — {p['name']} [{uid}]")
    print(f"{'='*52}")
    print(f"  Regime        : {regime}")
    print(f"  Gross Income  : Rs.{gross:,}")
    if regime == "Old":
        print(f"  HRA Exempt    : Rs.{inc['hra']:,}")
        print(f"  LTA Exempt    : Rs.{inc['lta']:,}")
        print(f"  Std Deduction : Rs.{STD_DEDUCTION:,}")
        total_ded = sum(ded.values()) + STD_DEDUCTION + inc["hra"] + inc["lta"]
        print(f"  Sec 80 Deds   : Rs.{sum(ded.values()):,}")
    else:
        print(f"  Std Deduction : Rs.{STD_DEDUCTION:,}")
        total_ded = STD_DEDUCTION
    print(f"  Net Taxable   : Rs.{net:,}")
    print(f"  Tax (pre-cess): Rs.{tax:,}")
    if rebate: print(f"  Rebate (87A)  : -Rs.{rebate:,}")
    print(f"  Cess (4%)     : Rs.{cess:,}")
    print(f"  TOTAL TAX     : Rs.{total:,}")
    print(f"  Effective Rate: {effective}%")
    print(f"{'='*52}")
    return total

def compare_regimes(uid):
    if uid not in profiles: return
    old_regime = profiles[uid]["regime"]
    profiles[uid]["regime"] = "Old"; old_tax = compute_liability(uid)
    profiles[uid]["regime"] = "New"; new_tax = compute_liability(uid)
    profiles[uid]["regime"] = old_regime
    saving = old_tax - new_tax
    print(f"\n  Regime Comparison: Old Rs.{old_tax:,} vs New Rs.{new_tax:,}")
    if saving > 0:
        print(f"  ★ New Regime saves Rs.{saving:,}")
    elif saving < 0:
        print(f"  ★ Old Regime saves Rs.{-saving:,}")
    else:
        print(f"  Both regimes result in the same tax.")

def main():
    print("=== Tax Filing Assistant ===")
    u1 = add_profile("Amit Sharma", "ABCPA1234Z", 35, "Old")
    u2 = add_profile("Priya Verma", "XYZPB5678Q", 29, "New")
    set_income(u1, salary=1200000, hra_exempt=96000, lta_exempt=20000, other_income=50000)
    set_income(u2, salary=800000,  other_income=30000)
    add_deduction(u1,"80C",  150000)
    add_deduction(u1,"80D",  20000)
    add_deduction(u1,"NPS",  50000)
    add_deduction(u1,"80TTA",8000)
    compute_liability(u1)
    compute_liability(u2)
    compare_regimes(u1)

if __name__ == "__main__":
    main()
