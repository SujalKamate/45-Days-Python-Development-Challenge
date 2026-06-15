# Restaurant Order Processing System with Bill Splitting

menu = {
    "Burger": 120, "Pizza": 250, "Pasta": 180, "Salad": 90,
    "Fries": 60,   "Cold Drink": 40, "Ice Cream": 80,
    "Soup": 70,    "Sandwich": 110,  "Noodles": 150
}
TAX_RATE = 0.08
orders = {}

def display_menu():
    print("\n===== MENU =====")
    for item, price in menu.items():
        print(f"  {item:<15} Rs.{price}")
    print("================")

def take_order(customer_name):
    if customer_name not in orders:
        orders[customer_name] = []
    display_menu()
    print(f"\nTaking order for: {customer_name}")
    while True:
        item = input("Enter item (or 'done' to finish): ").strip().title()
        if item.lower() == "done":
            break
        if item in menu:
            qty = int(input(f"  Quantity for {item}: "))
            orders[customer_name].append((item, qty, menu[item]))
            print(f"  Added {qty}x {item}")
        else:
            print("  Item not on menu. Try again.")

def calculate_total(customer_name):
    items = orders.get(customer_name, [])
    subtotal = sum(qty * price for _, qty, price in items)
    tax = round(subtotal * TAX_RATE, 2)
    return subtotal, tax, round(subtotal + tax, 2)

def split_bill(customer_names):
    combined = 0
    for name in customer_names:
        sub, _, _ = calculate_total(name)
        combined += sub
    tax = round(combined * TAX_RATE, 2)
    total = round(combined + tax, 2)
    return total, round(total / len(customer_names), 2)

def print_summary(customer_name):
    items = orders.get(customer_name, [])
    sub, tax, total = calculate_total(customer_name)
    print(f"\n{'='*40}")
    print(f"  ORDER SUMMARY — {customer_name}")
    print(f"{'='*40}")
    for item, qty, price in items:
        print(f"  {item:<18} x{qty}  Rs.{qty * price}")
    print(f"  {'Subtotal':<22} Rs.{sub:.2f}")
    print(f"  {'Tax (8%)':<22} Rs.{tax:.2f}")
    print(f"  {'TOTAL':<22} Rs.{total:.2f}")
    print(f"{'='*40}")

def main():
    print("=== Restaurant Order Processing System ===")
    num = int(input("Number of customers: "))
    customer_names = []
    for i in range(num):
        name = input(f"Name of customer {i+1}: ").strip()
        customer_names.append(name)
        take_order(name)
    print("\n--- Individual Bills ---")
    for name in customer_names:
        print_summary(name)
    if num > 1:
        choice = input("\nSplit bill equally among all? (yes/no): ").strip().lower()
        if choice == "yes":
            total, per_person = split_bill(customer_names)
            print(f"\n  Grand Total  : Rs.{total:.2f}")
            print(f"  Per Person   : Rs.{per_person:.2f}")
    print("\nThank you for dining with us!")

if __name__ == "__main__":
    main()
