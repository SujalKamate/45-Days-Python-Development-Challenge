# Digital Certificate Generator with Unique Verification Codes

import hashlib, random, string
from datetime import date

certificates = {}
_cert_num = 1

TEMPLATES = {
    "Completion":   "This is to certify that {name} has successfully completed the course '{course}'.",
    "Achievement":  "This is to certify that {name} has achieved excellence in '{course}'.",
    "Participation":"This is to certify that {name} participated in '{course}'.",
    "Merit":        "This is to certify that {name} has demonstrated outstanding merit in '{course}'.",
}

def generate_cert(recipient_name, course, cert_type, issuer, score=None, issue_date=None):
    global _cert_num
    if cert_type not in TEMPLATES:
        print(f"  Invalid type. Options: {list(TEMPLATES.keys())}"); return None
    d = issue_date or date.today()
    raw = f"{recipient_name}{course}{cert_type}{d}{_cert_num}"
    verification_code = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
    cert_id = f"CERT{_cert_num:06d}"; _cert_num += 1
    certificates[cert_id] = {
        "recipient": recipient_name, "course": course,
        "type": cert_type, "issuer": issuer, "score": score,
        "issued_on": d, "verification_code": verification_code, "valid": True
    }
    print(f"  [{cert_id}] {recipient_name} | {cert_type} | '{course}' | Code: {verification_code}")
    return cert_id

def verify_certificate(verification_code):
    matches = [cid for cid, c in certificates.items() if c["verification_code"] == verification_code]
    if not matches:
        print(f"  ✗ Verification FAILED: code '{verification_code}' not found.")
        return False
    cid  = matches[0]
    cert = certificates[cid]
    if not cert["valid"]:
        print(f"  ✗ Certificate {cid} has been revoked.")
        return False
    print(f"  ✔ VERIFIED: [{cid}]")
    print(f"    Recipient : {cert['recipient']}")
    print(f"    Course    : {cert['course']}")
    print(f"    Type      : {cert['type']}")
    print(f"    Issued by : {cert['issuer']} on {cert['issued_on']}")
    if cert["score"]: print(f"    Score     : {cert['score']}")
    return True

def print_certificate(cert_id):
    if cert_id not in certificates:
        print("  Certificate not found."); return
    c = certificates[cert_id]
    text = TEMPLATES[c["type"]].format(name=c["recipient"], course=c["course"])
    print(f"\n{'*'*54}")
    print(f"  {'CERTIFICATE OF ' + c['type'].upper():^50}")
    print(f"{'*'*54}")
    print(f"\n  {text}\n")
    if c["score"]: print(f"  Score Obtained: {c['score']}")
    print(f"  Issued by  : {c['issuer']}")
    print(f"  Issued on  : {c['issued_on']}")
    print(f"  Cert ID    : {cert_id}")
    print(f"  Verify at  : CODE# {c['verification_code']}")
    print(f"\n{'*'*54}")

def revoke_certificate(cert_id, reason="No reason given"):
    if cert_id not in certificates:
        print("  Certificate not found."); return
    certificates[cert_id]["valid"] = False
    print(f"  [{cert_id}] Revoked. Reason: {reason}")

def bulk_generate(names, course, cert_type, issuer, scores=None):
    print(f"\n  Bulk generating {len(names)} certificates for '{course}'...")
    ids = []
    for i, name in enumerate(names):
        score = scores[i] if scores and i < len(scores) else None
        cid = generate_cert(name, course, cert_type, issuer, score)
        ids.append(cid)
    return ids

def certificates_report():
    print(f"\n{'='*52}\n  CERTIFICATE REGISTRY REPORT\n{'='*52}")
    type_counts = {}
    for c in certificates.values():
        type_counts[c["type"]] = type_counts.get(c["type"], 0) + 1
    valid_count = sum(1 for c in certificates.values() if c["valid"])
    print(f"  Total Issued: {len(certificates)} | Valid: {valid_count} | Revoked: {len(certificates)-valid_count}")
    print("  By Type:")
    for t, count in type_counts.items():
        print(f"    {t:<15}: {count}")
    print(f"\n  Recent Certificates:")
    for cid, c in list(certificates.items())[-5:]:
        status = "Valid" if c["valid"] else "Revoked"
        print(f"  {cid} | {c['recipient']:<18} | {c['type']:<14} | {status}")
    print(f"{'='*52}")

def main():
    print("=== Digital Certificate Generator ===")
    c1 = generate_cert("Aarav Mehta",  "Python Programming", "Completion",   "Tech Academy", score="92/100")
    c2 = generate_cert("Bhavna Singh", "Data Science",       "Achievement",  "Tech Academy", score="98/100")
    c3 = generate_cert("Chetan Rao",   "Web Development",    "Merit",        "Dev Institute", score="88/100")
    c4 = generate_cert("Divya Nair",   "ML Workshop",        "Participation","AI Summit")
    names = ["Eshan Kumar","Fatima Sheikh","Gaurav Das","Hira Patel"]
    scores= ["85/100","78/100","90/100","82/100"]
    bulk_generate(names, "Cloud Computing Bootcamp", "Completion", "Cloud Academy", scores)
    print("\n--- Certificate Printing ---")
    print_certificate(c1)
    print("\n--- Verification ---")
    code = certificates[c2]["verification_code"]
    verify_certificate(code)
    verify_certificate("INVALIDCODE123")
    revoke_certificate(c4, "Participant withdrew consent")
    verify_certificate(certificates[c4]["verification_code"])
    certificates_report()

if __name__ == "__main__":
    main()
