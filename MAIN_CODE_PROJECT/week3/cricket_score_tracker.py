# Cricket Score Tracker with Match Summary Generator

match = {
    "team1": "", "team2": "",
    "innings": {1: {"team": "", "runs": 0, "wickets": 0, "overs": 0.0, "balls": 0,
                    "batsmen": {}, "bowlers": {}, "extras": 0, "history": []},
                2: {"team": "", "runs": 0, "wickets": 0, "overs": 0.0, "balls": 0,
                    "batsmen": {}, "bowlers": {}, "extras": 0, "history": []}},
    "target": 0, "current_innings": 1, "result": ""
}

def start_match(team1, team2):
    match["team1"] = team1
    match["team2"] = team2
    match["innings"][1]["team"] = team1
    match["innings"][2]["team"] = team2
    print(f"  Match started: {team1} vs {team2}")

def add_batsman(innings_num, name):
    match["innings"][innings_num]["batsmen"][name] = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0}

def add_bowler(innings_num, name):
    match["innings"][innings_num]["bowlers"][name] = {"overs": 0, "balls": 0, "runs": 0, "wickets": 0}

def update_ball(innings_num, batsman, bowler, runs, extra=0, wicket=False):
    inn = match["innings"][innings_num]
    inn["runs"] += runs + extra
    inn["extras"] += extra
    inn["balls"] += 1
    if inn["balls"] % 6 == 0:
        inn["overs"] = int(inn["balls"] / 6)
    else:
        inn["overs"] = int(inn["balls"] / 6) + (inn["balls"] % 6) / 10
    if batsman in inn["batsmen"]:
        inn["batsmen"][batsman]["balls"] += 1
        inn["batsmen"][batsman]["runs"] += runs
        if runs == 4: inn["batsmen"][batsman]["fours"] += 1
        if runs == 6: inn["batsmen"][batsman]["sixes"] += 1
    if bowler in inn["bowlers"]:
        inn["bowlers"][bowler]["balls"] += 1
        inn["bowlers"][bowler]["runs"] += runs
        if wicket:
            inn["bowlers"][bowler]["wickets"] += 1
    if wicket:
        inn["wickets"] += 1

def run_rate(innings_num):
    inn = match["innings"][innings_num]
    overs = inn["balls"] / 6
    if overs == 0:
        return 0.0
    return round(inn["runs"] / overs, 2)

def live_score(innings_num):
    inn = match["innings"][innings_num]
    rr = run_rate(innings_num)
    print(f"\n  [{inn['team']} — Innings {innings_num}]")
    print(f"  Score: {inn['runs']}/{inn['wickets']}  Overs: {inn['overs']}  Run Rate: {rr}")
    if innings_num == 2 and match["target"]:
        needed = match["target"] - inn["runs"]
        balls_left = max(0, 120 - inn["balls"])
        print(f"  Target: {match['target']}  Needed: {needed}  Balls Left: {balls_left}")

def scorecard(innings_num):
    inn = match["innings"][innings_num]
    print(f"\n{'='*48}")
    print(f"  SCORECARD — {inn['team']} (Innings {innings_num})")
    print(f"{'='*48}")
    print(f"  {'Batsman':<18} {'R':>4} {'B':>4} {'4s':>4} {'6s':>4}")
    for name, s in inn["batsmen"].items():
        sr = round(s["runs"] / s["balls"] * 100, 1) if s["balls"] else 0
        print(f"  {name:<18} {s['runs']:>4} {s['balls']:>4} {s['fours']:>4} {s['sixes']:>4}  SR:{sr}")
    print(f"\n  {'Bowler':<18} {'O':>4} {'R':>4} {'W':>4}")
    for name, b in inn["bowlers"].items():
        overs = f"{b['balls']//6}.{b['balls']%6}"
        print(f"  {name:<18} {overs:>4} {b['runs']:>4} {b['wickets']:>4}")
    print(f"\n  Total: {inn['runs']}/{inn['wickets']}  Extras: {inn['extras']}  Overs: {inn['overs']}")
    print(f"  Run Rate: {run_rate(innings_num)}")
    print(f"{'='*48}")

def match_summary():
    t1 = match["innings"][1]
    t2 = match["innings"][2]
    print(f"\n{'='*48}")
    print(f"  MATCH SUMMARY: {match['team1']} vs {match['team2']}")
    print(f"{'='*48}")
    print(f"  {match['team1']:<20}: {t1['runs']}/{t1['wickets']} in {t1['overs']} overs")
    print(f"  {match['team2']:<20}: {t2['runs']}/{t2['wickets']} in {t2['overs']} overs")
    if t1["runs"] > t2["runs"]:
        margin = t1["runs"] - t2["runs"]
        print(f"\n  Result: {match['team1']} won by {margin} runs")
    elif t2["runs"] > t1["runs"]:
        wkts_left = 10 - t2["wickets"]
        print(f"\n  Result: {match['team2']} won by {wkts_left} wickets")
    else:
        print("\n  Result: Match Tied!")
    print(f"{'='*48}")

def main():
    print("=== Cricket Score Tracker ===")
    start_match("India", "Australia")
    add_batsman(1, "Rohit")
    add_batsman(1, "Virat")
    add_bowler(1, "Starc")
    add_bowler(1, "Hazlewood")
    for ball in [(1,"Rohit","Starc",4,0,False),(2,"Rohit","Starc",0,0,False),
                 (3,"Virat","Starc",6,0,False),(4,"Virat","Hazlewood",1,0,False),
                 (5,"Rohit","Hazlewood",4,0,False),(6,"Virat","Hazlewood",0,0,True)]:
        update_ball(1, *ball)
    live_score(1)
    match["innings"][1]["runs"] = 185
    match["innings"][1]["wickets"] = 7
    match["target"] = 186
    add_batsman(2, "Warner")
    add_batsman(2, "Smith")
    add_bowler(2, "Bumrah")
    for ball in [(1,"Warner","Bumrah",6,0,False),(2,"Smith","Bumrah",4,0,False),
                 (3,"Warner","Bumrah",0,0,True),(4,"Smith","Bumrah",2,0,False)]:
        update_ball(2, *ball)
    match["innings"][2]["runs"] = 172
    match["innings"][2]["wickets"] = 9
    scorecard(1)
    scorecard(2)
    match_summary()

if __name__ == "__main__":
    main()
