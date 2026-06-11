"""
Regex-Based Multi-Field Form Validator with Detailed Error Reporting
Validates email, phone, postal code, password, and date formats.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ValidationResult:
    field: str
    value: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# ── Email Validation ──────────────────────────────────────────────────────────
DISPOSABLE_DOMAINS = {'mailinator.com', 'trashmail.com', 'guerrillamail.com', '10minutemail.com'}
COMMON_TYPOS = {'gmali.com': 'gmail.com', 'yahooo.com': 'yahoo.com', 'hotmial.com': 'hotmail.com'}

def validate_email(email: str) -> ValidationResult:
    r = ValidationResult('Email', email, True)
    email = email.strip()

    if not email:
        r.is_valid = False; r.errors.append("Email cannot be empty."); return r

    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        r.is_valid = False; r.errors.append("Invalid email format. Expected: user@domain.tld")

    if email.count('@') != 1:
        r.is_valid = False; r.errors.append("Must contain exactly one '@' character.")

    parts = email.split('@')
    if len(parts) == 2:
        local, domain = parts
        if len(local) > 64:
            r.errors.append("Local part (before @) exceeds 64 characters.")
        if domain in DISPOSABLE_DOMAINS:
            r.warnings.append(f"'{domain}' is a disposable email provider.")
        if domain in COMMON_TYPOS:
            r.suggestions.append(f"Did you mean '{COMMON_TYPOS[domain]}'?")
        if '..' in email:
            r.is_valid = False; r.errors.append("Consecutive dots are not allowed.")

    if len(email) > 254:
        r.is_valid = False; r.errors.append("Email exceeds maximum length of 254 characters.")

    return r


# ── Phone Validation ──────────────────────────────────────────────────────────
def validate_phone(phone: str, country: str = 'IN') -> ValidationResult:
    r = ValidationResult('Phone', phone, True)
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone.strip())

    if not cleaned:
        r.is_valid = False; r.errors.append("Phone number cannot be empty."); return r

    patterns = {
        'IN': (r'^[6-9]\d{9}$', 10, "Indian mobile: 10 digits starting with 6-9"),
        'US': (r'^[2-9]\d{2}[2-9]\d{6}$', 10, "US format: 10 digits (area code + number)"),
        'UK': (r'^(07\d{9}|0[1-9]\d{8,9})$', None, "UK: starts with 07 (mobile) or 0x (landline)"),
        'INTL': (r'^\d{7,15}$', None, "International: 7-15 digits"),
    }

    pat, expected_len, hint = patterns.get(country.upper(), patterns['INTL'])
    if expected_len and len(cleaned) != expected_len:
        r.is_valid = False
        r.errors.append(f"Expected {expected_len} digits for {country}, got {len(cleaned)}.")
    if not re.match(pat, cleaned):
        r.is_valid = False; r.errors.append(f"Invalid format for {country}. Hint: {hint}")

    if re.match(r'^(\d)\1+$', cleaned):
        r.warnings.append("Number contains all identical digits.")

    return r


# ── Postal Code Validation ────────────────────────────────────────────────────
def validate_postal(code: str, country: str = 'IN') -> ValidationResult:
    r = ValidationResult('Postal Code', code, True)
    code = code.strip().upper()

    patterns = {
        'IN': (r'^\d{6}$', "6 digits"),
        'US': (r'^\d{5}(-\d{4})?$', "5 digits or ZIP+4"),
        'UK': (r'^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$', "UK postcode format"),
        'CA': (r'^[A-Z]\d[A-Z] ?\d[A-Z]\d$', "Canadian A1A 1A1 format"),
    }

    pat, hint = patterns.get(country.upper(), (r'^\w{3,10}$', "3-10 alphanumeric"))
    if not re.match(pat, code):
        r.is_valid = False; r.errors.append(f"Invalid postal code for {country}. Format: {hint}")

    return r


# ── Password Validation ───────────────────────────────────────────────────────
def validate_password(pwd: str) -> ValidationResult:
    r = ValidationResult('Password', '*' * len(pwd), True)

    rules = [
        (len(pwd) >= 8,               "At least 8 characters"),
        (len(pwd) >= 12,              "At least 12 characters (recommended)"),
        (bool(re.search(r'[A-Z]', pwd)), "At least one uppercase letter"),
        (bool(re.search(r'[a-z]', pwd)), "At least one lowercase letter"),
        (bool(re.search(r'\d', pwd)),    "At least one digit"),
        (bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:,.<>?]', pwd)), "At least one special character"),
    ]

    for ok, rule in rules:
        if not ok:
            if rule.startswith("At least 12"):
                r.warnings.append(f"Recommendation: {rule}")
            else:
                r.is_valid = False; r.errors.append(f"Missing: {rule}")

    if re.search(r'(.)\1{2,}', pwd):
        r.warnings.append("Contains 3+ repeated consecutive characters.")
    if re.search(r'(012|123|234|345|456|567|678|789|890|abc|bcd|cde|qwe|asd)', pwd.lower()):
        r.warnings.append("Contains sequential pattern (e.g. 123, abc).")

    return r


# ── Date Validation ───────────────────────────────────────────────────────────
DATE_FORMATS = [
    (r'^\d{4}-\d{2}-\d{2}$',              'YYYY-MM-DD (ISO 8601)'),
    (r'^\d{2}/\d{2}/\d{4}$',              'DD/MM/YYYY'),
    (r'^\d{2}-\d{2}-\d{4}$',              'DD-MM-YYYY'),
    (r'^\d{2}\.\d{2}\.\d{4}$',            'DD.MM.YYYY'),
    (r'^\w+ \d{1,2},? \d{4}$',            'Month DD, YYYY'),
    (r'^\d{1,2} \w+ \d{4}$',              'DD Month YYYY'),
]

def validate_date(date_str: str) -> ValidationResult:
    r = ValidationResult('Date', date_str, True)
    date_str = date_str.strip()

    matched_fmt = None
    for pattern, fmt in DATE_FORMATS:
        if re.match(pattern, date_str, re.IGNORECASE):
            matched_fmt = fmt
            break

    if not matched_fmt:
        r.is_valid = False
        r.errors.append("Date does not match any recognized format.")
        r.suggestions.append("Try: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, etc.")
        return r

    r.suggestions.append(f"Detected format: {matched_fmt}")

    nums = re.findall(r'\d+', date_str)
    if len(nums) >= 3:
        parts = list(map(int, nums[:3]))
        if 'YYYY' in matched_fmt and matched_fmt.startswith('YYYY'):
            y, m, d = parts[0], parts[1], parts[2]
        else:
            d, m, y = parts[0], parts[1], parts[2]

        month_days = [0,31,29,31,30,31,30,31,31,30,31,30,31]
        if not (1 <= m <= 12):
            r.is_valid = False; r.errors.append(f"Month {m} is invalid (must be 1-12).")
        elif not (1 <= d <= month_days[m]):
            r.is_valid = False; r.errors.append(f"Day {d} is invalid for month {m}.")
        if y < 1900 or y > 2100:
            r.warnings.append(f"Year {y} seems unusual.")

    return r


def validate_form(data: Dict) -> Dict:
    results = {}
    if 'email'    in data: results['email']    = validate_email(data['email'])
    if 'phone'    in data: results['phone']    = validate_phone(data['phone'], data.get('country', 'IN'))
    if 'postal'   in data: results['postal']   = validate_postal(data['postal'], data.get('country', 'IN'))
    if 'password' in data: results['password'] = validate_password(data['password'])
    if 'date'     in data: results['date']     = validate_date(data['date'])
    return results


def print_validation_results(results: Dict):
    print(f"\n  {'═'*60}")
    all_valid = all(r.is_valid for r in results.values())
    status = "✓ ALL VALID" if all_valid else "✗ VALIDATION FAILED"
    print(f"  Form Validation: {status}")
    print(f"  {'═'*60}")

    for field_name, r in results.items():
        icon = "✓" if r.is_valid else "✗"
        print(f"\n  {icon} {r.field}: '{r.value}'")
        for err in r.errors:
            print(f"     ✗ ERROR   : {err}")
        for warn in r.warnings:
            print(f"     ⚠ WARNING : {warn}")
        for sug in r.suggestions:
            print(f"     💡 INFO    : {sug}")

    print(f"\n  {'═'*60}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Multi-Field Form Validator v1.0       ║")
    print("╚══════════════════════════════════════════╝")

    test_cases = [
        {"email": "alice@gmail.com",        "phone": "9876543210",   "postal": "110001",
         "password": "MyP@ssw0rd123!",      "date": "2024-11-15",    "country": "IN"},
        {"email": "invalid.email@",         "phone": "12345",         "postal": "ABCDEF",
         "password": "weak",                "date": "32/13/2024",     "country": "IN"},
        {"email": "user@mailinator.com",    "phone": "+44 7911123456","postal": "SW1A 1AA",
         "password": "Password1",           "date": "November 15, 2024", "country": "UK"},
        {"email": "test@gmali.com",         "phone": "2025551234",    "postal": "10001-5678",
         "password": "Tr0ub4dor&3!",       "date": "15.11.2024",     "country": "US"},
    ]

    for i, form in enumerate(test_cases, 1):
        print(f"\n  ── Test Case {i} ──")
        results = validate_form(form)
        print_validation_results(results)

    print("\n  ── Interactive Validation ──")
    while True:
        choice = input("\n  Validate [1]Email [2]Phone [3]Postal [4]Password [5]Date [6]Quit: ").strip()
        if choice == '6': break
        field_map = {'1': 'email', '2': 'phone', '3': 'postal', '4': 'password', '5': 'date'}
        if choice in field_map:
            val = input(f"  Enter {field_map[choice]}: ").strip()
            data = {field_map[choice]: val}
            if choice in ('2', '3'):
                data['country'] = input("  Country code (IN/US/UK/CA): ").strip().upper() or 'IN'
            results = validate_form(data)
            print_validation_results(results)


if __name__ == "__main__":
    main()
