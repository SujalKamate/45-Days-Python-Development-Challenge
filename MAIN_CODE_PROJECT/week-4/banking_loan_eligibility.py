# Banking Loan Eligibility Checker with EMI Calculator

import math

LOAN_TYPES = {
    "Home":     {"min_income":30000, "max_multiplier":60, "rate":8.5,  "max_years":30},
    "Car":      {"min_income":15000, "max_multiplier":20, "rate":9.5,  "max_years":7},
    "Personal": {"min_income":10000, "max_multiplier":10, "rate":12.0, "max_years":5},
    "Education":{"min_income":0,     "max_multiplier":50, "rate":7.5,  "max_years":15},
    "Business": {"min_income":50000, "max_multiplier":40, "rate":10.5, "max_years":10},
}
applicants = {}
_aid = 1

def calculate_emi(principal, annual_rate, years):
    r = annual_rate / (12 * 100)
    n = years * 12
    if r == 0: return round(principal / n, 2)
    emi = principal * r * (1 + r)**n / ((1 + r)**n - 1)
    return round(emi, 2)

def credit_score_rating(score):
    if score >= 750: return "Excellent", 0.0
    elif score >= 700: return "Good", 0.5
    elif score >= 650: return "Fair", 1.0
    elif score >= 600: return "Poor", 1.5
    else: return "Very Poor", None   # None = ineligible

def check_eligibility(name, monthly_income, loan_type, loan_amount, tenure_years,
                      credit_score, existing_emi=0):
    global _aid
    if loan_type not in LOAN_TYPES:
        print(f"  Invalid loan type. Options: {list(LOAN_TYPES.keys())}"); return None
    lt  = LOAN_TYPES[loan_type]
    aid = f"APP{_aid:04d}"; _aid += 1
    rating, rate_adj = credit_score_rating(credit_score)
    issues = []
    eligible = True
    if rate_adj is None:
        issues.append(f"Credit score {credit_score} too low (min 600 required)")
        eligible = False
    if monthly_income < lt["min_income"]:
        issues.append(f"Income Rs.{monthly_income:,} below minimum Rs.{lt['min_income']:,}")
        eligible = False
    max_loan = monthly_income * lt["max_multiplier"]
    if loan_amount > max_loan:
        issues.append(f"Loan Rs.{loan_amount:,} exceeds max Rs.{max_loan:,} (income-based)")
        eligible = False
    if tenure_years > lt["max_years"]:
        issues.append(f"Tenure {tenure_years}yr exceeds max {lt['max_years']}yr")
        eligible = False
    effective_rate = lt["rate"] + (rate_adj or 0)
    emi = calculate_emi(loan_amount, effective_rate, tenure_years)
    foir = (emi + existing_emi) / monthly_income
    if foir > 0.5:
        issues.append(f"FOIR {foir:.1%} exceeds 50% (EMI+existing burdens income)")
        eligible = False
    total_payable = emi * tenure_years * 12
    total_interest = round(total_payable - loan_amount, 2)
    applicants[aid] = {
        "name":name, "income":monthly_income, "loan_type":loan_type,
        "amount":loan_amount, "tenure":tenure_years, "credit_score":credit_score,
        "rating":rating, "emi":emi, "rate":effective_rate,
        "eligible":eligible, "issues":issues, "foir":round(foir,4)
    }
    print(f"\n{'='*52}")
    print(f"  LOAN ELIGIBILITY REPORT — {aid}")
    print(f"  Applicant     : {name}")
    print(f"  Loan Type     : {loan_type} | Amount: Rs.{loan_amount:,}")
    print(f"  Tenure        : {tenure_years} years | Rate: {effective_rate:.1f}%")
    print(f"  Monthly Income: Rs.{monthly_income:,}")
    print(f"  Credit Score  : {credit_score} ({rating})")
    print(f"  EMI           : Rs.{emi:,}")
    print(f"  FOIR          : {foir:.1%}")
    print(f"  Total Payable : Rs.{total_payable:,.0f} (Interest: Rs.{total_interest:,.0f})")
    if eligible:
        print(f"  Status        : ✔ ELIGIBLE")
    else:
        print(f"  Status        : ✗ NOT ELIGIBLE")
        for issue in issues:
            print(f"    • {issue}")
    print(f"{'='*52}")
    return aid

def emi_schedule(aid, months=6):
    if aid not in applicants: return
    a = applicants[aid]
    if not a["eligible"]: print("  Not eligible — no schedule."); return
    r = a["rate"] / (12 * 100); balance = a["amount"]
    print(f"\n  EMI Schedule (first {months} months) — {a['name']}")
    print(f"  {'Month':<7} {'EMI':>10} {'Interest':>11} {'Principal':>11} {'Balance':>13}")
    for month in range(1, months + 1):
        interest  = round(balance * r, 2)
        principal = round(a["emi"] - interest, 2)
        balance   = round(balance - principal, 2)
        print(f"  {month:<7} Rs.{a['emi']:>8,.2f} Rs.{interest:>9,.2f} Rs.{principal:>9,.2f} Rs.{balance:>11,.2f}")

def main():
    print("=== Banking Loan Eligibility Checker ===")
    a1 = check_eligibility("Amit Sharma",  50000, "Home",     3000000, 20, 740, 5000)
    a2 = check_eligibility("Priya Verma",  20000, "Car",       600000,  5, 680, 2000)
    a3 = check_eligibility("Rahul Nair",    8000, "Personal",  100000,  3, 720, 0)
    a4 = check_eligibility("Sunita Patel", 80000, "Business", 2000000,  7, 580, 0)
    a5 = check_eligibility("Kiran Rao",    35000, "Education", 800000, 10, 700, 0)
    emi_schedule(a1, months=6)
    emi_schedule(a5, months=4)

if __name__ == "__main__":
    main()
