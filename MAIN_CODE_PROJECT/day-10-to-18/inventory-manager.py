"""
Store Inventory Management System with Low-Stock Alerts and Valuation
Add/update/remove products, low-stock alerts, total value, JSON persistence.
"""

import json
import os
from datetime import datetime

DATA_FILE = "inventory.json"
LOW_STOCK_THRESHOLD = 10


def load_inventory():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_inventory(inventory):
    with open(DATA_FILE, 'w') as f:
        json.dump(inventory, f, indent=2)


def new_product(pid, name, price, quantity, category="General", reorder_level=10):
    return {
        "id": pid, "name": name, "price": round(float(price), 2),
        "quantity": int(quantity), "category": category,
        "reorder_level": reorder_level,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }


def add_product(inventory):
    print("\n  ── Add Product ──")
    pid = input("  Product ID  : ").strip().upper()
    if pid in inventory:
        print(f"  ✗ Product '{pid}' already exists. Use 'update' to modify.")
        return
    name     = input("  Name        : ").strip()
    price    = float(input("  Price (₹)   : "))
    quantity = int(input("  Quantity    : "))
    category = input("  Category    : ").strip() or "General"
    reorder  = int(input(f"  Reorder Lvl (default {LOW_STOCK_THRESHOLD}): ") or LOW_STOCK_THRESHOLD)

    inventory[pid] = new_product(pid, name, price, quantity, category, reorder)
    save_inventory(inventory)
    print(f"  ✓ Product '{name}' added with ID '{pid}'.")


def update_product(inventory):
    pid = input("  Product ID to update: ").strip().upper()
    if pid not in inventory:
        print(f"  ✗ Product '{pid}' not found."); return
    p = inventory[pid]
    print(f"  Updating: {p['name']} | Price: ₹{p['price']} | Qty: {p['quantity']}")
    print("  (Leave blank to keep current value)")
    name     = input(f"  New Name     [{p['name']}]: ").strip()
    price    = input(f"  New Price    [{p['price']}]: ").strip()
    quantity = input(f"  New Quantity [{p['quantity']}]: ").strip()
    reorder  = input(f"  Reorder Lvl  [{p['reorder_level']}]: ").strip()

    if name:     p['name'] = name
    if price:    p['price'] = round(float(price), 2)
    if quantity: p['quantity'] = int(quantity)
    if reorder:  p['reorder_level'] = int(reorder)
    p['updated'] = datetime.now().isoformat()
    save_inventory(inventory)
    print(f"  ✓ Product updated.")


def remove_product(inventory):
    pid = input("  Product ID to remove: ").strip().upper()
    if pid not in inventory:
        print(f"  ✗ Product '{pid}' not found."); return
    name = inventory[pid]['name']
    confirm = input(f"  Remove '{name}' (ID:{pid})? (y/n): ").strip().lower()
    if confirm == 'y':
        del inventory[pid]
        save_inventory(inventory)
        print(f"  ✓ Product '{name}' removed.")


def restock(inventory):
    pid = input("  Product ID to restock: ").strip().upper()
    if pid not in inventory:
        print(f"  ✗ Product '{pid}' not found."); return
    amount = int(input("  Quantity to add: "))
    inventory[pid]['quantity'] += amount
    inventory[pid]['updated'] = datetime.now().isoformat()
    save_inventory(inventory)
    print(f"  ✓ Restocked {inventory[pid]['name']}: new qty = {inventory[pid]['quantity']}")


def sell(inventory):
    pid = input("  Product ID to sell: ").strip().upper()
    if pid not in inventory:
        print(f"  ✗ Product '{pid}' not found."); return
    p = inventory[pid]
    amount = int(input(f"  Quantity to sell (available: {p['quantity']}): "))
    if amount > p['quantity']:
        print(f"  ✗ Insufficient stock. Only {p['quantity']} available."); return
    p['quantity'] -= amount
    p['updated'] = datetime.now().isoformat()
    revenue = amount * p['price']
    save_inventory(inventory)
    print(f"  ✓ Sold {amount}× {p['name']} for ₹{revenue:.2f}.")
    if p['quantity'] <= p['reorder_level']:
        print(f"  ⚠  LOW STOCK ALERT: '{p['name']}' has only {p['quantity']} units left!")


def print_inventory(inventory, filter_cat=None):
    items = list(inventory.values())
    if filter_cat:
        items = [p for p in items if p['category'].lower() == filter_cat.lower()]
    if not items:
        print("  No products found."); return

    items.sort(key=lambda x: x['name'])
    print(f"\n  {'═'*75}")
    print(f"  {'INVENTORY':^73}")
    print(f"  {'═'*75}")
    print(f"  {'ID':<8} {'Name':<25} {'Category':<12} {'Price':>8} {'Qty':>6} {'Value':>10}  {'Status'}")
    print(f"  {'─'*75}")

    for p in items:
        value = p['price'] * p['quantity']
        alert = " ⚠LOW" if p['quantity'] <= p['reorder_level'] else ""
        print(f"  {p['id']:<8} {p['name']:<25} {p['category']:<12} ₹{p['price']:>7.2f} {p['quantity']:>6} ₹{value:>9.2f}{alert}")

    total_value = sum(p['price'] * p['quantity'] for p in items)
    total_items = sum(p['quantity'] for p in items)
    print(f"  {'─'*75}")
    print(f"  {'TOTAL':<46} {total_items:>6} ₹{total_value:>9.2f}")
    print(f"  {'═'*75}\n")


def low_stock_report(inventory):
    low = [p for p in inventory.values() if p['quantity'] <= p['reorder_level']]
    if not low:
        print("  ✓ No low stock items."); return
    print(f"\n  ⚠  LOW STOCK ALERT ({len(low)} items):")
    print(f"  {'─'*55}")
    for p in sorted(low, key=lambda x: x['quantity']):
        needed = p['reorder_level'] * 2 - p['quantity']
        print(f"  [{p['id']}] {p['name']:<25} Qty: {p['quantity']:>5}  (reorder: {p['reorder_level']})  Suggest order: {needed}")
    print(f"  {'─'*55}")


def valuation_report(inventory):
    cats = {}
    for p in inventory.values():
        c = p['category']
        cats.setdefault(c, {'items': 0, 'units': 0, 'value': 0})
        cats[c]['items'] += 1
        cats[c]['units'] += p['quantity']
        cats[c]['value'] += p['price'] * p['quantity']

    print(f"\n  {'═'*50}")
    print(f"  VALUATION BY CATEGORY")
    print(f"  {'─'*50}")
    print(f"  {'Category':<20} {'Items':>6} {'Units':>7} {'Value':>12}")
    print(f"  {'─'*50}")
    for cat, data in sorted(cats.items()):
        print(f"  {cat:<20} {data['items']:>6} {data['units']:>7} ₹{data['value']:>11.2f}")
    total_val = sum(d['value'] for d in cats.values())
    print(f"  {'─'*50}")
    print(f"  {'TOTAL':<20} {'':>6} {'':>7} ₹{total_val:>11.2f}")
    print(f"  {'═'*50}\n")


def seed_demo(inventory):
    samples = [
        ("P001", "Laptop",          45000, 25, "Electronics", 5),
        ("P002", "Wireless Mouse",   1200,  8,  "Electronics", 10),
        ("P003", "USB-C Cable",       299, 50,  "Accessories", 15),
        ("P004", "Notebook A4",        80, 200, "Stationery",  20),
        ("P005", "Ballpoint Pen",       15, 500, "Stationery", 50),
        ("P006", "Coffee Mug",         350,  6,  "Kitchen",    10),
        ("P007", "Hand Sanitizer",      99, 80,  "Health",     20),
        ("P008", "LED Desk Lamp",      799,  3,  "Furniture",   5),
    ]
    for args in samples:
        pid = args[0]
        if pid not in inventory:
            inventory[pid] = new_product(*args)
    save_inventory(inventory)


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Store Inventory System v1.0            ║")
    print("╚══════════════════════════════════════════╝")
    inventory = load_inventory()
    if not inventory:
        print("  Loading demo data...")
        seed_demo(inventory)

    menu = {
        '1': ("View Inventory",   lambda: print_inventory(inventory)),
        '2': ("Add Product",      lambda: add_product(inventory)),
        '3': ("Update Product",   lambda: update_product(inventory)),
        '4': ("Remove Product",   lambda: remove_product(inventory)),
        '5': ("Restock",          lambda: restock(inventory)),
        '6': ("Sell",             lambda: sell(inventory)),
        '7': ("Low Stock Alert",  lambda: low_stock_report(inventory)),
        '8': ("Valuation Report", lambda: valuation_report(inventory)),
        '9': ("Quit",             None),
    }

    while True:
        print("\n  ── Menu ──")
        for k, (label, _) in menu.items():
            print(f"  [{k}] {label}")
        choice = input("  Choice: ").strip()
        if choice == '9':
            print("  Goodbye!")
            break
        if choice in menu and menu[choice][1]:
            menu[choice][1]()
        else:
            print("  Invalid choice.")

    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)


if __name__ == "__main__":
    main()
