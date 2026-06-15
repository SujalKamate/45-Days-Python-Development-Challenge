# Voting Booth Simulator with Candidate Statistics

import hashlib

candidates = {}
voters = {}
votes_log = []

def register_candidate(name, party):
    cid = f"C{len(candidates)+1:03d}"
    candidates[cid] = {"name": name, "party": party, "votes": 0}
    print(f"  Registered: [{cid}] {name} — {party}")
    return cid

def register_voter(name, vid):
    if vid in voters:
        print(f"  Voter ID {vid} already registered.")
        return False
    voters[vid] = {"name": name, "voted": False}
    print(f"  Voter registered: {name} | ID: {vid}")
    return True

def cast_vote(vid, cid):
    if vid not in voters:
        print("  ERROR: Invalid voter ID.")
        return False
    if voters[vid]["voted"]:
        print(f"  BLOCKED: {voters[vid]['name']} has already voted!")
        return False
    if cid not in candidates:
        print("  ERROR: Invalid candidate ID.")
        return False
    voters[vid]["voted"] = True
    candidates[cid]["votes"] += 1
    token = hashlib.md5(f"{vid}{cid}secret".encode()).hexdigest()[:8].upper()
    votes_log.append({"voter": vid, "candidate": cid, "token": token})
    print(f"  Vote cast! Receipt: {token}")
    return True

def show_candidates():
    print("\n--- Registered Candidates ---")
    for cid, info in candidates.items():
        print(f"  [{cid}] {info['name']:<20} Party: {info['party']}")

def display_results():
    total = sum(c["votes"] for c in candidates.values())
    print(f"\n{'='*45}")
    print("  ELECTION RESULTS")
    print(f"{'='*45}")
    if total == 0:
        print("  No votes recorded yet.")
        return
    ranked = sorted(candidates.items(), key=lambda x: x[1]["votes"], reverse=True)
    for rank, (cid, info) in enumerate(ranked, 1):
        pct = (info["votes"] / total) * 100
        bar = "█" * int(pct // 4)
        print(f"  {rank}. {info['name']:<18} {info['votes']:>4} votes  {pct:5.1f}%  {bar}")
    winner = ranked[0][1]
    print(f"\n  🏆 Winner: {winner['name']} ({winner['party']})")
    voted_count = sum(1 for v in voters.values() if v["voted"])
    turnout = (voted_count / len(voters) * 100) if voters else 0
    print(f"  Total Votes: {total} | Turnout: {voted_count}/{len(voters)} ({turnout:.1f}%)")
    print(f"{'='*45}")

def detect_anomalies():
    print("\n--- Security Log ---")
    duplicates = [v for v in voters.values() if not v["voted"]]
    print(f"  Voters who did NOT vote: {len(duplicates)}")
    print(f"  Total vote entries logged: {len(votes_log)}")
    for entry in votes_log:
        cname = candidates[entry["candidate"]]["name"]
        vname = voters[entry["voter"]]["name"]
        print(f"  {entry['token']} | {vname} -> {cname}")

def main():
    print("=== Voting Booth Simulator ===")
    register_candidate("Amit Sharma", "Progressive Party")
    register_candidate("Priya Verma", "National Front")
    register_candidate("Rahul Singh", "People's Alliance")
    register_candidate("Neha Joshi", "Green India")
    print()
    register_voter("Karan Mehta", "V001")
    register_voter("Sneha Patel", "V002")
    register_voter("Rohit Gupta", "V003")
    register_voter("Anjali Nair", "V004")
    register_voter("Vikram Das", "V005")
    register_voter("Meera Iyer", "V006")
    show_candidates()
    print("\n--- Casting Votes ---")
    cast_vote("V001", "C001")
    cast_vote("V002", "C002")
    cast_vote("V003", "C001")
    cast_vote("V004", "C003")
    cast_vote("V005", "C001")
    cast_vote("V006", "C004")
    cast_vote("V002", "C003")   # Duplicate — should be blocked
    cast_vote("V099", "C001")   # Invalid voter
    display_results()
    detect_anomalies()

if __name__ == "__main__":
    main()
