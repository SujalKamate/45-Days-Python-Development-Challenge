# Museum Artifact Catalog System with Search Filters

artifacts = {}
_aid = 1

PERIODS = ["Ancient", "Medieval", "Renaissance", "Modern", "Contemporary"]
CATEGORIES = ["Sculpture", "Painting", "Manuscript", "Jewelry", "Pottery", "Weapon", "Textile", "Coin"]
LOCATIONS = ["Hall A", "Hall B", "Hall C", "Storage", "On Loan"]

def add_artifact(name, period, category, origin, year_approx, description, location="Storage"):
    global _aid
    if period not in PERIODS:
        print(f"  Invalid period. Options: {PERIODS}")
        return None
    if category not in CATEGORIES:
        print(f"  Invalid category. Options: {CATEGORIES}")
        return None
    aid = f"ART{_aid:04d}"
    _aid += 1
    artifacts[aid] = {
        "name": name, "period": period, "category": category,
        "origin": origin, "year": year_approx,
        "description": description, "location": location, "on_display": location != "Storage"
    }
    print(f"  [{aid}] {name} | {period} | {category} | {origin} ({year_approx}) | {location}")
    return aid

def search_by_period(period):
    results = [(aid, a) for aid, a in artifacts.items() if a["period"].lower() == period.lower()]
    print(f"\n  [{period} Period] — {len(results)} artifact(s) found:")
    for aid, a in results:
        print(f"  {aid} | {a['name']:<30} {a['category']:<12} | {a['origin']}")
    return results

def search_by_category(category):
    results = [(aid, a) for aid, a in artifacts.items() if a["category"].lower() == category.lower()]
    print(f"\n  [{category}] — {len(results)} artifact(s):")
    for aid, a in results:
        print(f"  {aid} | {a['name']:<30} {a['period']:<14} | {a['location']}")

def search_by_origin(origin_keyword):
    kw = origin_keyword.lower()
    results = [(aid, a) for aid, a in artifacts.items() if kw in a["origin"].lower()]
    print(f"\n  Origin search '{origin_keyword}' — {len(results)} result(s):")
    for aid, a in results:
        print(f"  {aid} | {a['name']:<30} | {a['period']} {a['year']}")

def move_artifact(aid, new_location):
    if aid not in artifacts:
        print("  Artifact not found.")
        return
    if new_location not in LOCATIONS:
        print(f"  Invalid location. Options: {LOCATIONS}")
        return
    old = artifacts[aid]["location"]
    artifacts[aid]["location"]   = new_location
    artifacts[aid]["on_display"] = new_location not in ["Storage", "On Loan"]
    print(f"  [{aid}] '{artifacts[aid]['name']}' moved: {old} → {new_location}")

def artifact_detail(aid):
    if aid not in artifacts:
        print("  Artifact not found.")
        return
    a = artifacts[aid]
    print(f"\n{'='*50}")
    print(f"  [{aid}] {a['name']}")
    print(f"  Period      : {a['period']}  ({a['year']})")
    print(f"  Category    : {a['category']}")
    print(f"  Origin      : {a['origin']}")
    print(f"  Location    : {a['location']}")
    print(f"  On Display  : {'Yes' if a['on_display'] else 'No'}")
    print(f"  Description : {a['description']}")
    print(f"{'='*50}")

def catalog_report():
    print(f"\n{'='*52}")
    print("  MUSEUM CATALOG REPORT")
    print(f"{'='*52}")
    on_display = sum(1 for a in artifacts.values() if a["on_display"])
    print(f"  Total Artifacts : {len(artifacts)}")
    print(f"  On Display      : {on_display}")
    print(f"  In Storage      : {sum(1 for a in artifacts.values() if a['location']=='Storage')}")
    print(f"  On Loan         : {sum(1 for a in artifacts.values() if a['location']=='On Loan')}")
    print("\n  By Period:")
    for period in PERIODS:
        count = sum(1 for a in artifacts.values() if a["period"] == period)
        if count:
            print(f"    {period:<16}: {count}")
    print("\n  By Category:")
    for cat in CATEGORIES:
        count = sum(1 for a in artifacts.values() if a["category"] == cat)
        if count:
            print(f"    {cat:<16}: {count}")
    print(f"{'='*52}")

def main():
    print("=== Museum Artifact Catalog System ===")
    add_artifact("Mohenjo-daro Dancer",  "Ancient",      "Sculpture", "Indus Valley", "2500 BCE",
                 "Bronze dancing girl from Indus Valley Civilisation.", "Hall A")
    add_artifact("Ajanta Cave Painting", "Ancient",      "Painting",  "India",        "200 BCE",
                 "Buddhist fresco depicting Jataka tales.", "Hall B")
    add_artifact("Mughal Miniature",     "Medieval",     "Painting",  "Mughal India", "1600 CE",
                 "Intricate court scene from Akbar's era.", "Hall A")
    add_artifact("Iron Sword",           "Medieval",     "Weapon",    "Rajputana",    "1200 CE",
                 "Ceremonial sword with ornate hilt.", "Hall C")
    add_artifact("Silk Tapestry",        "Renaissance",  "Textile",   "China",        "1450 CE",
                 "Embroidered silk depicting imperial court.", "Storage")
    add_artifact("Roman Coin Set",       "Ancient",      "Coin",      "Rome",         "100 CE",
                 "Silver denarii from Emperor Trajan's reign.", "On Loan")
    search_by_period("Ancient")
    search_by_category("Painting")
    search_by_origin("India")
    move_artifact("ART0005", "Hall C")
    artifact_detail("ART0001")
    catalog_report()

if __name__ == "__main__":
    main()
