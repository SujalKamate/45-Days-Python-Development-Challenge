"""
Multi-Number Phone Book with CSV Import and Formatted Text Export
Stores multiple numbers per contact, partial name search, CSV import, text export.
"""

import csv
import os
import re
from datetime import datetime


class PhoneBook:
    def __init__(self):
        self.contacts = {}   # name_lower -> {name, numbers: [{label, number}], email, notes}

    def _key(self, name):
        return name.strip().lower()

    def add_contact(self, name, numbers=None, email="", notes=""):
        key = self._key(name)
        if key in self.contacts:
            print(f"  ✗ Contact '{name}' already exists. Use 'add_number' to add more numbers.")
            return False
        self.contacts[key] = {
            "name": name.strip(), "numbers": numbers or [],
            "email": email.strip(), "notes": notes.strip(),
            "created": datetime.now().isoformat(),
        }
        print(f"  ✓ Contact '{name}' added.")
        return True

    def add_number(self, name, number, label="Mobile"):
        key = self._key(name)
        if key not in self.contacts:
            print(f"  ✗ Contact '{name}' not found."); return
        self.contacts[key]["numbers"].append({"label": label, "number": number.strip()})
        print(f"  ✓ Added {label}: {number} to '{name}'.")

    def remove_contact(self, name):
        key = self._key(name)
        if key not in self.contacts:
            print(f"  ✗ '{name}' not found."); return
        del self.contacts[key]
        print(f"  ✓ Contact '{name}' removed.")

    def search(self, query):
        query = query.strip().lower()
        results = []
        for key, c in self.contacts.items():
            if (query in key or
                query in c.get('email', '').lower() or
                query in c.get('notes', '').lower() or
                any(query in n['number'] for n in c.get('numbers', []))):
                results.append(c)
        return results

    def update_email(self, name, email):
        key = self._key(name)
        if key not in self.contacts:
            print(f"  ✗ '{name}' not found."); return
        self.contacts[key]['email'] = email.strip()
        print(f"  ✓ Email updated for '{name}'.")

    def list_all(self, sort_by='name'):
        contacts = sorted(self.contacts.values(), key=lambda c: c['name'].lower())
        if not contacts:
            print("  Phone book is empty."); return

        print(f"\n  {'─'*65}")
        print(f"  {'Name':<25} {'Numbers':<30} {'Email'}")
        print(f"  {'─'*65}")
        for c in contacts:
            nums = ', '.join(f"{n['label']}: {n['number']}" for n in c['numbers'])
            print(f"  {c['name']:<25} {nums[:30]:<30} {c['email'][:20]}")
        print(f"  {'─'*65}")
        print(f"  Total: {len(contacts)} contact(s)\n")

    def print_contact(self, c):
        print(f"\n  ┌── {c['name']}")
        for n in c.get('numbers', []):
            print(f"  │  📞 {n['label']}: {n['number']}")
        if c.get('email'):
            print(f"  │  ✉  Email: {c['email']}")
        if c.get('notes'):
            print(f"  │  📝 Notes: {c['notes']}")
        print(f"  └── Added: {c.get('created','?')[:10]}")

    def import_csv(self, filepath):
        if not os.path.exists(filepath):
            print(f"  ✗ File '{filepath}' not found."); return 0

        imported = 0
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name  = row.get('name', row.get('Name', '')).strip()
                phone = row.get('phone', row.get('Phone', row.get('mobile', ''))).strip()
                email = row.get('email', row.get('Email', '')).strip()
                label = row.get('label', 'Mobile')
                if not name:
                    continue
                key = self._key(name)
                if key not in self.contacts:
                    self.contacts[key] = {
                        "name": name, "numbers": [], "email": email, "notes": "",
                        "created": datetime.now().isoformat(),
                    }
                if phone:
                    self.contacts[key]['numbers'].append({"label": label, "number": phone})
                imported += 1
        print(f"  ✓ Imported {imported} record(s) from '{filepath}'.")
        return imported

    def export_text(self, filepath=None):
        if not filepath:
            filepath = f"phonebook_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"PHONE BOOK EXPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 60 + "\n\n")
            for c in sorted(self.contacts.values(), key=lambda x: x['name'].lower()):
                f.write(f"Name   : {c['name']}\n")
                for n in c.get('numbers', []):
                    f.write(f"  {n['label']}: {n['number']}\n")
                if c.get('email'):
                    f.write(f"Email  : {c['email']}\n")
                if c.get('notes'):
                    f.write(f"Notes  : {c['notes']}\n")
                f.write("-" * 40 + "\n")
        print(f"  ✓ Exported {len(self.contacts)} contacts to '{filepath}'.")
        return filepath

    def export_csv(self, filepath=None):
        if not filepath:
            filepath = f"phonebook_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        rows = []
        for c in self.contacts.values():
            for n in c.get('numbers', []) or [{"label": "", "number": ""}]:
                rows.append({
                    'name': c['name'], 'label': n.get('label', ''),
                    'phone': n.get('number', ''), 'email': c.get('email', ''),
                    'notes': c.get('notes', ''),
                })
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'label', 'phone', 'email', 'notes'])
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✓ CSV exported to '{filepath}' ({len(rows)} rows).")
        return filepath


def create_demo_csv(path="sample_contacts.csv"):
    rows = [
        {"name": "Alice Sharma",  "phone": "9876543210", "email": "alice@email.com",  "label": "Mobile"},
        {"name": "Alice Sharma",  "phone": "011-23456789", "email": "",                "label": "Home"},
        {"name": "Bob Verma",     "phone": "9123456780", "email": "bob@work.com",      "label": "Mobile"},
        {"name": "Carol Singh",   "phone": "8765432100", "email": "carol@gmail.com",   "label": "Mobile"},
        {"name": "David Kumar",   "phone": "7654321009", "email": "david@company.in",  "label": "Office"},
        {"name": "Eve Patel",     "phone": "6543210987", "email": "eve@personal.com",  "label": "Mobile"},
    ]
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'phone', 'email', 'label'])
        writer.writeheader(); writer.writerows(rows)
    return path


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Multi-Number Phone Book v1.0          ║")
    print("╚══════════════════════════════════════════╝")

    pb = PhoneBook()

    # Manual adds
    pb.add_contact("Frank Nair",   [{"label": "Mobile", "number": "9988776655"}], "frank@email.com", "Colleague")
    pb.add_contact("Grace Iyer",   [{"label": "Home",   "number": "044-2233445"}], "grace@home.net")
    pb.add_number("Frank Nair", "9900112233", "Office")
    pb.update_email("Grace Iyer", "grace.iyer@work.com")

    # Import CSV
    csv_path = create_demo_csv()
    pb.import_csv(csv_path)

    pb.list_all()

    # Search
    queries = ["alice", "9876543210", "work.com"]
    for q in queries:
        results = pb.search(q)
        print(f"\n  Search '{q}' → {len(results)} result(s):")
        for c in results:
            pb.print_contact(c)

    # Export
    txt_file = pb.export_text("phonebook_export.txt")
    csv_file = pb.export_csv("phonebook_export.csv")

    # Cleanup
    for f in [csv_path, txt_file, csv_file]:
        if os.path.exists(f):
            os.remove(f)

    # Interactive
    while True:
        print("\n  [1]List [2]Search [3]Add [4]Export [5]Quit")
        choice = input("  Choice: ").strip()
        if choice == '5': break
        elif choice == '1': pb.list_all()
        elif choice == '2':
            q = input("  Search: ")
            results = pb.search(q)
            for c in results: pb.print_contact(c)
            if not results: print("  No results.")
        elif choice == '3':
            name = input("  Name: ")
            num  = input("  Number: ")
            lbl  = input("  Label (Mobile/Home/Office): ") or "Mobile"
            email= input("  Email: ")
            if name not in (c['name'] for c in pb.contacts.values()):
                pb.add_contact(name, [{"label": lbl, "number": num}], email)
            else:
                pb.add_number(name, num, lbl)
        elif choice == '4':
            pb.export_text(); pb.export_csv()
        else:
            print("  Invalid.")
    print("  Goodbye!")


if __name__ == "__main__":
    main()
