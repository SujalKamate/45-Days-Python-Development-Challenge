"""
Weighted Voting System Simulator with Tie-Breaking Runoff Logic
Defines candidates/voters with weights, tallies votes, handles ties with runoff.
"""

import random
from collections import defaultdict


def create_voter(name, weight=1):
    return {"name": name, "weight": weight}


def create_candidate(name, party="Independent", bio=""):
    return {"name": name, "party": party, "bio": bio}


def cast_votes(voters, candidates, voting_method="weighted"):
    """
    Returns a dict: candidate_name -> total_weight_votes
    Each voter votes for exactly one candidate (random simulation).
    """
    tally = defaultdict(float)
    vote_log = []

    for voter in voters:
        choice = random.choice(candidates)["name"]
        weight = voter.get("weight", 1) if voting_method == "weighted" else 1
        tally[choice] += weight
        vote_log.append({
            "voter": voter["name"],
            "weight": weight,
            "choice": choice
        })

    return dict(tally), vote_log


def cast_votes_from_ballot(voters, ballots):
    """
    ballots: dict of voter_name -> candidate_name (predetermined choices).
    """
    tally = defaultdict(float)
    vote_log = []
    voter_map = {v["name"]: v for v in voters}

    for voter_name, choice in ballots.items():
        voter  = voter_map.get(voter_name, {"weight": 1})
        weight = voter.get("weight", 1)
        tally[choice] += weight
        vote_log.append({"voter": voter_name, "weight": weight, "choice": choice})

    return dict(tally), vote_log


def find_winner(tally):
    if not tally:
        return None, []
    max_votes = max(tally.values())
    winners   = [c for c, v in tally.items() if v == max_votes]
    return winners[0] if len(winners) == 1 else None, winners


def runoff(voters, tied_candidates, ballots=None):
    """Run a runoff election among only the tied candidates."""
    print(f"\n  ⚡ RUNOFF between: {', '.join(tied_candidates)}")

    if ballots:
        # Filter ballots to only those who voted for tied candidates
        runoff_ballots = {v: c for v, c in ballots.items() if c in tied_candidates}
        tally, log = cast_votes_from_ballot(voters, runoff_ballots)
    else:
        tally, log = cast_votes(voters, [{"name": c} for c in tied_candidates])

    return tally, log


def print_results(tally, candidates, vote_log, title="Election Results"):
    total_weight = sum(tally.values())
    print(f"\n  {'═'*60}")
    print(f"  {title}")
    print(f"  {'═'*60}")

    # Sort by votes descending
    sorted_results = sorted(tally.items(), key=lambda x: -x[1])

    cand_map = {c["name"]: c for c in candidates}
    print(f"  {'Rank':<5} {'Candidate':<22} {'Party':<16} {'Votes':>8}  {'%':>6}  {'Bar'}")
    print(f"  {'─'*70}")

    for rank, (name, votes) in enumerate(sorted_results, 1):
        pct  = votes / total_weight * 100 if total_weight else 0
        bar  = "█" * int(pct / 3)
        party = cand_map.get(name, {}).get("party", "")
        print(f"  {rank:<5} {name:<22} {party:<16} {votes:>8.1f}  {pct:>5.1f}%  {bar}")

    print(f"  {'─'*70}")
    print(f"  Total votes cast: {total_weight:.1f}")

    winner, tied = find_winner(tally)
    if winner:
        print(f"\n  🏆 WINNER: {winner} ({tally[winner]:.1f} votes, {tally[winner]/total_weight*100:.1f}%)")
    else:
        print(f"\n  🤝 TIE between: {', '.join(tied)}")
    print(f"  {'═'*60}")
    return winner, tied


def print_vote_log(vote_log, show_all=False):
    print(f"\n  Vote Log ({len(vote_log)} votes):")
    print(f"  {'─'*45}")
    entries = vote_log if show_all else vote_log[:10]
    for e in entries:
        print(f"  {e['voter']:<20} wt={e['weight']:.1f}  → {e['choice']}")
    if not show_all and len(vote_log) > 10:
        print(f"  ... ({len(vote_log)-10} more votes not shown)")
    print(f"  {'─'*45}")


def percentage_breakdown(tally, candidates):
    total = sum(tally.values())
    print(f"\n  Vote share breakdown:")
    for c in candidates:
        name = c["name"]
        votes = tally.get(name, 0)
        pct   = votes / total * 100 if total else 0
        bar   = "▇" * int(pct / 2)
        print(f"  {name:<22} {pct:>5.1f}%  {bar}")


def simulate_election(candidates, voters, predetermined_ballots=None, title="General Election"):
    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║  {title:<36}  ║")
    print(f"  ╚══════════════════════════════════════╝")
    print(f"  Candidates : {len(candidates)}")
    print(f"  Voters     : {len(voters)} (total weight={sum(v['weight'] for v in voters):.1f})")

    if predetermined_ballots:
        tally, vote_log = cast_votes_from_ballot(voters, predetermined_ballots)
    else:
        tally, vote_log = cast_votes(voters, candidates)

    print_vote_log(vote_log)
    winner, tied = print_results(tally, candidates, vote_log, title)
    percentage_breakdown(tally, candidates)

    # Handle tie with runoff
    if not winner and tied:
        runoff_tally, runoff_log = runoff(voters, tied)
        final_cands = [c for c in candidates if c["name"] in tied]
        runoff_winner, runoff_tied = print_results(
            runoff_tally, final_cands, runoff_log, "RUNOFF Results"
        )
        if not runoff_winner:
            # Second tie — coin flip
            final = random.choice(runoff_tied)
            print(f"\n  🪙 Second tie! Coin flip winner: {final}")
            winner = final
        else:
            winner = runoff_winner

    return winner


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Weighted Voting Simulator v1.0        ║")
    print("╚══════════════════════════════════════════╝")

    # ── Demo 1: Simple weighted election ─────────────────────────────────────
    candidates1 = [
        create_candidate("Alice Sharma",  "Progressive Party", "Education & health reform"),
        create_candidate("Bob Verma",     "Conservative Party","Economic stability"),
        create_candidate("Carol Singh",   "Green Party",       "Environment & sustainability"),
        create_candidate("David Kumar",   "Liberal Party",     "Individual freedoms"),
    ]
    voters1 = (
        [create_voter(f"Citizen_{i:03d}", weight=1.0) for i in range(50)] +
        [create_voter(f"Corporate_{i:02d}", weight=2.5) for i in range(10)] +
        [create_voter(f"Elder_{i:02d}", weight=1.5) for i in range(15)]
    )
    random.seed(42)
    simulate_election(candidates1, voters1, title="City Council Election (Weighted)")

    # ── Demo 2: Tie scenario with predetermined ballots ───────────────────────
    candidates2 = [
        create_candidate("Option A", "Proposal", "Build new library"),
        create_candidate("Option B", "Proposal", "Renovate park"),
    ]
    voters2 = [create_voter(f"Member_{i}", weight=1) for i in range(10)]
    # Deliberately balanced ballots
    ballots2 = {
        "Member_0": "Option A", "Member_1": "Option B",
        "Member_2": "Option A", "Member_3": "Option B",
        "Member_4": "Option A", "Member_5": "Option B",
        "Member_6": "Option A", "Member_7": "Option B",
        "Member_8": "Option A", "Member_9": "Option B",
    }
    simulate_election(candidates2, voters2, ballots2, title="Community Referendum (Tie Scenario)")

    # ── Demo 3: Non-weighted comparison ──────────────────────────────────────
    random.seed(99)
    candidates3 = [
        create_candidate("Team Alpha",  "Tech", ""),
        create_candidate("Team Beta",   "Design", ""),
        create_candidate("Team Gamma",  "Marketing", ""),
    ]
    voters3 = [create_voter(f"Judge_{i}", weight=random.uniform(1, 5)) for i in range(20)]
    simulate_election(candidates3, voters3, title="Hackathon Judging (Weighted Judges)")


if __name__ == "__main__":
    main()
