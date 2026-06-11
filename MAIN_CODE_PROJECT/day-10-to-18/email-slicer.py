"""
Email Address Slicer, Provider Identifier and Header Component Parser
Extracts username/domain, identifies provider, validates, parses raw headers.
"""

import re
from collections import OrderedDict


KNOWN_PROVIDERS = {
    'gmail.com':      ('Google Gmail',      'https://mail.google.com'),
    'yahoo.com':      ('Yahoo Mail',         'https://mail.yahoo.com'),
    'yahoo.in':       ('Yahoo India',        'https://mail.yahoo.com'),
    'outlook.com':    ('Microsoft Outlook',  'https://outlook.live.com'),
    'hotmail.com':    ('Microsoft Hotmail',  'https://outlook.live.com'),
    'live.com':       ('Microsoft Live',     'https://outlook.live.com'),
    'icloud.com':     ('Apple iCloud',       'https://icloud.com/mail'),
    'me.com':         ('Apple Me',           'https://icloud.com/mail'),
    'protonmail.com': ('ProtonMail',         'https://protonmail.com'),
    'zoho.com':       ('Zoho Mail',          'https://zoho.com/mail'),
    'aol.com':        ('AOL Mail',           'https://mail.aol.com'),
    'rediffmail.com': ('Rediff Mail',        'https://mail.rediff.com'),
    'yandex.com':     ('Yandex Mail',        'https://mail.yandex.com'),
    'tutanota.com':   ('Tutanota',           'https://tutanota.com'),
}

DISPOSABLE = {'mailinator.com', 'trashmail.com', 'guerrillamail.com',
              '10minutemail.com', 'tempmail.com', 'throwam.com'}

EMAIL_REGEX = re.compile(
    r'^(?P<local>[a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,62}[a-zA-Z0-9]?)'
    r'@(?P<domain>[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$'
)


def slice_email(email):
    email = email.strip()
    if '@' not in email:
        return None
    parts = email.rsplit('@', 1)
    return {'local': parts[0], 'domain': parts[1].lower(), 'full': email}


def validate_email(email):
    email = email.strip()
    issues = []
    if not email:
        return False, ["Email is empty"]
    if email.count('@') != 1:
        issues.append("Must contain exactly one '@'")
    if '..' in email:
        issues.append("Consecutive dots not allowed")
    m = EMAIL_REGEX.match(email)
    if not m:
        issues.append("Fails RFC-5322 basic pattern check")
    local = email.split('@')[0] if '@' in email else email
    if local.startswith('.') or local.endswith('.'):
        issues.append("Local part cannot start or end with a dot")
    if len(email) > 254:
        issues.append("Exceeds maximum length of 254 characters")
    return len(issues) == 0, issues


def identify_provider(domain):
    domain = domain.lower()
    if domain in KNOWN_PROVIDERS:
        name, url = KNOWN_PROVIDERS[domain]
        return {'name': name, 'url': url, 'disposable': domain in DISPOSABLE, 'known': True}
    # Check TLD patterns
    tld = domain.split('.')[-1]
    if domain in DISPOSABLE:
        return {'name': 'Disposable Email Provider', 'url': '', 'disposable': True, 'known': False}
    org_map = {'edu': 'Educational Institution', 'gov': 'Government', 'ac': 'Academic',
               'mil': 'Military', 'int': 'International Organization'}
    if tld in org_map:
        return {'name': org_map[tld], 'url': '', 'disposable': False, 'known': False}
    return {'name': 'Unknown/Custom Provider', 'url': '', 'disposable': False, 'known': False}


def parse_raw_header(raw_header):
    """Parse a raw email header string into structured components."""
    fields = OrderedDict()
    lines = raw_header.strip().splitlines()
    current_field = None
    current_value = []

    for line in lines:
        # Header folding: continuation lines start with whitespace
        if line and line[0] in (' ', '\t') and current_field:
            current_value.append(line.strip())
        else:
            if current_field:
                fields[current_field] = ' '.join(current_value)
            if ':' in line:
                idx = line.index(':')
                current_field = line[:idx].strip()
                current_value = [line[idx+1:].strip()]
            else:
                current_field = None
                current_value = []

    if current_field:
        fields[current_field] = ' '.join(current_value)

    return fields


def extract_addresses_from_header(header_value):
    """Extract all email addresses from a header field like To:, CC:, etc."""
    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    return re.findall(pattern, header_value)


def analyze_email(email):
    print(f"\n  {'═'*60}")
    print(f"  Analyzing: {email}")
    print(f"  {'─'*60}")

    sliced = slice_email(email)
    if not sliced:
        print("  ✗ Could not parse — missing '@'"); return

    is_valid, issues = validate_email(email)
    provider = identify_provider(sliced['domain'])

    print(f"  Local Part   : {sliced['local']}")
    print(f"  Domain       : {sliced['domain']}")
    print(f"  Valid        : {'✓ Yes' if is_valid else '✗ No'}")

    if not is_valid:
        for issue in issues:
            print(f"    ✗ {issue}")

    print(f"\n  Provider     : {provider['name']}")
    if provider['url']:
        print(f"  Webmail URL  : {provider['url']}")
    print(f"  Known        : {'Yes' if provider['known'] else 'No (custom domain)'}")
    if provider['disposable']:
        print(f"  ⚠  DISPOSABLE EMAIL PROVIDER")

    # Username hints
    local = sliced['local']
    if re.match(r'^[a-z]+\.[a-z]+$', local):
        print(f"\n  Pattern: Likely 'firstname.lastname'")
    elif re.match(r'^[a-z]+\d+$', local):
        print(f"\n  Pattern: Name + numbers (possibly auto-generated)")
    elif re.match(r'^[a-z]{1,3}\d{4,}$', local):
        print(f"\n  Pattern: Possibly initials + employee ID")

    print(f"  Local Length : {len(local)} chars")
    print(f"  {'═'*60}")


SAMPLE_HEADER = """\
From: Alice Sharma <alice.sharma@gmail.com>
To: Bob Verma <bob.verma@outlook.com>, carol@yahoo.com
CC: team@company.co.in
Date: Mon, 15 Nov 2024 10:30:00 +0530
Subject: Project Update - Q4 Report
Message-ID: <20241115103000.abc123@gmail.com>
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
X-Mailer: Gmail
Received: from mail.gmail.com (mail.gmail.com [209.85.220.41])
    by mx.company.com with ESMTP id abc123
    for <bob.verma@outlook.com>; Mon, 15 Nov 2024 10:30:05 +0530
"""


def demo_header_parsing():
    print(f"\n  {'═'*60}")
    print(f"  Raw Email Header Parsing")
    print(f"  {'═'*60}")

    parsed = parse_raw_header(SAMPLE_HEADER)

    print(f"\n  Parsed Fields ({len(parsed)}):")
    for field, value in parsed.items():
        print(f"  {field:<15}: {value[:65]}")

    print(f"\n  Extracted Addresses:")
    for field in ['From', 'To', 'CC']:
        if field in parsed:
            addrs = extract_addresses_from_header(parsed[field])
            for addr in addrs:
                sliced = slice_email(addr)
                if sliced:
                    prov = identify_provider(sliced['domain'])
                    print(f"  [{field}] {addr}  →  {prov['name']}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Email Slicer & Header Parser v1.0     ║")
    print("╚══════════════════════════════════════════╝")

    test_emails = [
        "alice.sharma@gmail.com",
        "bob123@yahoo.in",
        "carol@outlook.com",
        "test@mailinator.com",
        "invalid@@email.com",
        "user@rediffmail.com",
        "admin@iitb.ac.in",
        "employee001@company.co.in",
        "x@",
        "frank.nair@protonmail.com",
    ]

    for email in test_emails:
        analyze_email(email)

    demo_header_parsing()

    print("\n  ── Interactive Mode ──")
    while True:
        email = input("\n  Enter email (or 'q'): ").strip()
        if email.lower() == 'q': break
        analyze_email(email)


if __name__ == "__main__":
    main()
