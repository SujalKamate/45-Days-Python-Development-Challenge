# Recipe Collection Manager with Ingredient Search

import json, os

recipes = {}
_rid = 1

def add_recipe(name, cuisine, ingredients, steps, prep_time):
    global _rid
    rid = f"RCP{_rid:03d}"
    _rid += 1
    recipes[rid] = {
        "name": name, "cuisine": cuisine,
        "ingredients": [i.lower() for i in ingredients],
        "steps": steps, "prep_time": prep_time
    }
    print(f"  [{rid}] Recipe '{name}' added ({cuisine}, {prep_time} mins)")
    return rid

def search_by_ingredient(keyword):
    kw = keyword.lower()
    print(f"\n--- Recipes containing '{keyword}' ---")
    found = False
    for rid, r in recipes.items():
        if any(kw in ing for ing in r["ingredients"]):
            print(f"  [{rid}] {r['name']} ({r['cuisine']})")
            found = True
    if not found:
        print("  No recipes found.")

def search_by_cuisine(cuisine):
    c = cuisine.lower()
    print(f"\n--- {cuisine} Cuisine Recipes ---")
    found = [r for r in recipes.values() if r["cuisine"].lower() == c]
    if not found:
        print("  No recipes found.")
    for r in found:
        print(f"  {r['name']} — Prep: {r['prep_time']} mins")

def display_recipe(rid):
    if rid not in recipes:
        print("  Recipe not found.")
        return
    r = recipes[rid]
    print(f"\n{'='*42}")
    print(f"  {r['name']}  [{r['cuisine']}]  ({r['prep_time']} mins)")
    print(f"{'='*42}")
    print("  Ingredients:")
    for ing in r["ingredients"]:
        print(f"    • {ing.title()}")
    print("\n  Steps:")
    for i, step in enumerate(r["steps"], 1):
        print(f"    {i}. {step}")
    print(f"{'='*42}")

def export_recipes(rids, filename="exported_recipes.txt"):
    path = os.path.join(os.getcwd(), filename)
    lines = []
    for rid in rids:
        if rid not in recipes:
            continue
        r = recipes[rid]
        lines.append(f"=== {r['name']} ===")
        lines.append(f"Cuisine: {r['cuisine']}  |  Prep Time: {r['prep_time']} mins")
        lines.append("Ingredients: " + ", ".join(r["ingredients"]))
        lines.append("Steps:")
        for i, s in enumerate(r["steps"], 1):
            lines.append(f"  {i}. {s}")
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Exported {len(rids)} recipe(s) to {filename}")

def list_all_recipes():
    print(f"\n{'='*42}")
    print("  ALL RECIPES")
    print(f"{'='*42}")
    cuisines = sorted(set(r["cuisine"] for r in recipes.values()))
    for cuisine in cuisines:
        print(f"\n  [{cuisine}]")
        for rid, r in recipes.items():
            if r["cuisine"] == cuisine:
                print(f"    [{rid}] {r['name']} — {r['prep_time']} mins")

def main():
    print("=== Recipe Collection Manager ===")
    add_recipe("Paneer Butter Masala", "Indian",
               ["paneer", "butter", "tomato", "cream", "spices"],
               ["Fry paneer cubes.", "Prepare butter-tomato gravy.", "Combine and simmer.", "Add cream."], 30)
    add_recipe("Pasta Arrabbiata", "Italian",
               ["pasta", "tomato", "garlic", "chilli", "olive oil"],
               ["Boil pasta.", "Sauté garlic and chilli.", "Add tomatoes.", "Mix with pasta."], 20)
    add_recipe("Chicken Biryani", "Indian",
               ["chicken", "basmati rice", "spices", "onion", "yoghurt"],
               ["Marinate chicken.", "Fry onions.", "Layer rice and chicken.", "Dum cook 30 mins."], 60)
    add_recipe("Margherita Pizza", "Italian",
               ["pizza dough", "tomato sauce", "mozzarella", "basil"],
               ["Roll dough.", "Spread sauce.", "Add toppings.", "Bake 220°C 12 mins."], 25)
    add_recipe("Tom Kha Soup", "Thai",
               ["coconut milk", "chicken", "galangal", "lemongrass", "mushrooms"],
               ["Boil coconut milk.", "Add galangal and lemongrass.", "Add chicken.", "Simmer 15 mins."], 25)
    list_all_recipes()
    search_by_ingredient("tomato")
    search_by_cuisine("Indian")
    display_recipe("RCP001")
    export_recipes(["RCP001", "RCP003"], "indian_recipes.txt")

if __name__ == "__main__":
    main()
