"""
Persistent Contact Book with Full CRUD and JSON Storage
Stores contacts with name, phone, email, address; supports search, sort, and file persistence.
"""

import json
import os
from datetime import datetime

DATA_FILE = "contacts.json"


def load_contacts():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_contacts(contacts):
    with open(DATA_FILE, 'w') as f:
        json.dump(contacts, f, indent=2)
    print(f"  ✓ Contacts saved to '{DATA_FILE}'.")


def new_contact(name, phone, email="", address=""):
    return {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "name": name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "address": address.strip(),
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }


def add_contact(contacts):
    print("\n  ── Add New Contact ──")
    name = input("  Name    : ").strip()
    if not name:
        print("  ✗ Name cannot be empty.")
        return
    phone = input("  Phone   : ").strip()
    email = input("  Email   : ").strip()
    address = input("  Address : ").strip()
    contact = new_contact(name, phone, email, address)
    contacts.append(contact)
    save_contacts(contacts)
    print(f"  ✓ Contact '{name}' added.")


def list_contacts(contacts):
    if not contacts:
        print("\n  No contacts found.")
        return
    sorted_c = sorted(contacts, key=lambda c: c['name'].lower())
    print(f"\n  {'#':<4} {'Name':<22} {'Phone':<15} {'Email':<25} {'Address'}")
    print(f"  {'─'*82}")
    for i, c in enumerate(sorted_c, 1):
        print(f"  {i:<4} {c['name']:<22} {c['phone']:<15} {c['email']:<25} {c['address'][:20]}")
    print(f"  {'─'*82}")
    print(f"  Total: {len(contacts)} contact(s)\n")


def search_contacts(contacts):
    query = input("  Search query: ").strip().lower()
    if not query:
        return
    results = [
        c for c in contacts
        if query in c['name'].lower()
        or query in c['phone']
        or query in c['email'].lower()
        or query in c['address'].lower()
    ]
    if not results:
        print(f"  No contacts matching '{query}'.")
    else:
        print(f"\n  Found {len(results)} result(s):")
        for c in results:
            print_contact(c)


def print_contact(c):
    print(f"\n  ┌─ Contact ID: {c['id']}")
    print(f"  │  Name    : {c['name']}")
    print(f"  │  Phone   : {c['phone']}")
    print(f"  │  Email   : {c['email']}")
    print(f"  │  Address : {c['address']}")
    print(f"  │  Created : {c['created'][:19]}")
    print(f"  └  Updated : {c['updated'][:19]}")


def update_contact(contacts):
    query = input("  Enter name to update: ").strip().lower()
    matches = [c for c in contacts if query in c['name'].lower()]
    if not matches:
        print("  ✗ No matching contact found.")
        return
    contact = matches[0]
    print_contact(contact)
    print("\n  (Leave blank to keep existing value)")
    name = input(f"  New Name    [{contact['name']}]: ").strip()
    phone = input(f"  New Phone   [{contact['phone']}]: ").strip()
    email = input(f"  New Email   [{contact['email']}]: ").strip()
    address = input(f"  New Address [{contact['address']}]: ").strip()

    if name:
        contact['name'] = name
    if phone:
        contact['phone'] = phone
    if email:
        contact['email'] = email
    if address:
        contact['address'] = address
    contact['updated'] = datetime.now().isoformat()
    save_contacts(contacts)
    print(f"  ✓ Contact updated.")


def delete_contact(contacts):
    query = input("  Enter name to delete: ").strip().lower()
    original_len = len(contacts)
    to_remove = [c for c in contacts if query in c['name'].lower()]
    if not to_remove:
        print("  ✗ No matching contact.")
        return
    for c in to_remove:
        print_contact(c)
    confirm = input(f"\n  Delete {len(to_remove)} contact(s)? (y/n): ").strip().lower()
    if confirm == 'y':
        contacts[:] = [c for c in contacts if query not in c['name'].lower()]
        save_contacts(contacts)
        print(f"  ✓ Deleted {original_len - len(contacts)} contact(s).")


def main():
    contacts = load_contacts()
    print("╔══════════════════════════════════════╗")
    print("║   Persistent Contact Book v1.0       ║")
    print("╚══════════════════════════════════════╝")
    print(f"  Loaded {len(contacts)} contact(s) from storage.")

    menu = {
        '1': ("Add Contact", add_contact),
        '2': ("List Contacts", list_contacts),
        '3': ("Search Contacts", search_contacts),
        '4': ("Update Contact", update_contact),
        '5': ("Delete Contact", delete_contact),
        '6': ("Quit", None),
    }

    while True:
        print("\n  ── Menu ──")
        for k, (label, _) in menu.items():
            print(f"  [{k}] {label}")
        choice = input("  Choice: ").strip()
        if choice == '6':
            print("  Goodbye!")
            break
        if choice in menu:
            menu[choice][1](contacts)
        else:
            print("  ✗ Invalid choice.")


if __name__ == "__main__":
    main()
