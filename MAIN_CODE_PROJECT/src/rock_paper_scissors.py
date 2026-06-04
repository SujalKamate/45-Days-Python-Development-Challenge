"""Create an Interactive Rock Paper Scissors Gaming System with Score Persistence

Generated for the 45-day Python development challenge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
import json
import random
import time

@dataclass
class RockPaperScissorsAppState:
    history: List[str] = field(default_factory=list)
    records: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    runs: int = 0
    errors: int = 0

# ---------------- APP ----------------

class RockPaperScissorsApp:
    def __init__(self) -> None:
        self.stats = {
            "wins": 0,
            "losses": 0,
            "draws": 0
            }
        self.player_history = []
        self.state = RockPaperScissorsAppState()
        self.output_dir = Path('outputs')
        self.output_dir.mkdir(exist_ok=True)
        
    def ai_predict_move(self, player_history: List[str]) -> str:
        """
        Adaptive AI:
        - Learns frequency of player moves
        - Adds randomness to avoid predictability
        """
        if not player_history:
            return random.choice(['rock', 'paper', 'scissors'])
        
        freq = {'rock': 0, 'paper': 0, 'scissors': 0}
        
        for move in player_history:
            if move in freq:
                freq[move] += 1
                
        most_common = max(freq, key=freq.get)
            
         # counter logic
            
        if random.random() < 0.2:
            return random.choice(['rock', 'paper', 'scissors'])
        
        counter = {
            'rock': 'paper',
            'paper': 'scissors',
            'scissors': 'rock'
            }
        
        return counter[most_common]
    
    def format_kv(self, k: str, v: Any) -> str:
        return f"{k:<20} : {v}"
    
    def log(self, message: str) -> None:
        stamp = datetime.now().strftime('%H:%M:%S')
        entry = f'[{stamp}] {message}'
        self.state.history.append(entry)
        print(entry)

    def section(self, title: str) -> None:
        print()
        print('=' * 70)
        print(title)
        print('=' * 70)

    def non_empty(self, value: Any) -> bool:
        return bool(str(value).strip())

    def safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def normalize_text(self, value: str) -> str:
        return ' '.join(str(value).strip().split())

    def normalize_key(self, value: str) -> str:
        return self.normalize_text(value).lower().replace(' ', '_')

    def split_words(self, value: str) -> List[str]:
        cleaned = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in value)
        return [part for part in cleaned.split() if part]

    def chunk(self, items: List[Any], size: int) -> List[List[Any]]:
        size = max(1, size)
        return [items[i:i + size] for i in range(0, len(items), size)]

    def format_kv(self, key: str, value: Any) -> str:
        return f'{key:<20} : {value}'

    def render_table(self, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return '(empty)'
        keys = list(dict.fromkeys(k for row in rows for k in row))
        widths = {k: max(len(k), max(len(str(row.get(k, ''))) for row in rows)) for k in keys}
        header = ' | '.join(k.ljust(widths[k]) for k in keys)
        lines = [header, '-+-'.join('-' * widths[k] for k in keys)]
        for row in rows:
            lines.append(' | '.join(str(row.get(k, '')).ljust(widths[k]) for k in keys))
        return '\n'.join(lines)

    def save_json(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.output_dir / name
        path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
        return path

    def load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save_text(self, name: str, content: str) -> Path:
        path = self.output_dir / name
        path.write_text(content, encoding='utf-8')
        return path

    def load_text(self, path: Path) -> str:
        if not path.exists():
            return ''
        return path.read_text(encoding='utf-8')

    def record(self, key: str, value: Any) -> None:
        self.state.records[key] = value

    def toggle(self, key: str, default: bool = False) -> bool:
        current = self.state.flags.get(key, default)
        self.state.flags[key] = not current
        return self.state.flags[key]

    def summarize_list(self, values: List[float]) -> Dict[str, Any]:
        if not values:
            return {'count': 0, 'min': 0, 'max': 0, 'avg': 0}
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': round(sum(values) / len(values), 4),
        }

    def history_tail(self, count: int = 5) -> List[str]:
        return self.state.history[-count:]

    def export_state(self) -> Path:
        payload = {
            'created_at': self.state.created_at,
            'runs': self.state.runs,
            'errors': self.state.errors,
            'records': self.state.records,
            'flags': self.state.flags,
            'history': self.state.history,
        }
        return self.save_json(f'{self.__class__.__name__}_state.json', payload)

    def display_report(self) -> None:
        self.section('Summary')
        print(self.format_kv('Runs', self.state.runs))
        print(self.format_kv('Errors', self.state.errors))
        print(self.format_kv('Records', len(self.state.records)))
        print(self.format_kv('Flags', len(self.state.flags)))
        print(self.format_kv('History entries', len(self.state.history)))
        self.log(f'Exported to {self.export_state()}')

    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'player_move': 'rock', 'computer_move': 'scissors'},
            {'player_move': 'paper', 'computer_move': 'rock'},
            {'player_move': 'scissors', 'computer_move': 'scissors'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        rounds = []
        player_wins = 0
        computer_wins = 0
        draws = 0
        for r in items:
            pm = r.get('player_move')
            cm = r.get('computer_move')
            if pm == cm:
                res = 'draw'
                draws += 1
            elif (pm == 'rock' and cm == 'scissors') or (pm == 'paper' and cm == 'rock') or (pm == 'scissors' and cm == 'paper'):
                res = 'player'
                player_wins += 1
            else:
                res = 'computer'
                computer_wins += 1
            rounds.append({'player': pm, 'computer': cm, 'winner': res})
        return {
            'total_rounds': len(items),
            'player_wins': player_wins,
            'computer_wins': computer_wins,
            'draws': draws,
            'rounds': rounds
        }

 # ---------------- GAME ENGINE ----------------
    def run(self) -> None:
        self.state.runs += 1
        self.section('Rock-Paper-Scissors: 5 Rounds')
        #player_moves = ['rock', 'paper', 'scissors', 'rock', 'paper']
        player_score = 0
        computer_score = 0
        draws = 0
        round_results = []
        while True:
            n = int(input("Enter Best-of-N rounds (odd number): "))
            if n > 0 and n % 2 == 1:
                break 
            print("Please enter a positive odd number.")
        needed = (n // 2) + 1
        i = 0
        while player_score < needed and computer_score < needed and i < n:           
            player = input("Choose rock/paper/scissors: ").strip().lower()
            while player not in ["rock", "paper", "scissors"]:
                player = input("Invalid choice. Enter rock/paper/scissors: ").strip().lower()
            self.player_history.append(player)
            computer = self.ai_predict_move(self.player_history)
            if player == computer:
                result = 'draw'
                draws += 1
            elif (player == 'rock' and computer == 'scissors') or (player == 'scissors' and computer == 'paper') or (player == 'paper' and computer == 'rock'):
                result = 'player'
                player_score += 1               
            else:
                result = 'computer'
                computer_score += 1
            print(self.format_kv(f'Round {i+1}', f'Player: {player} vs Computer: {computer} -> {result}'))
            round_results.append({'round': i+1, 'player': player, 'computer': computer, 'result': result})
            i += 1 
            
        # AFTER LOOP
        if player_score > computer_score:
            winner = 'Player'
        elif computer_score > player_score:
            winner = 'Computer'
        else:
            winner = 'Draw'  
                
        # FINAL STATS CALCULATION (ADD HERE)
        self.stats["wins"] = player_score
        self.stats["losses"] = computer_score
        self.stats["draws"] = draws        
        print(self.format_kv('Final', f'Player {player_score} - {computer_score} Computer'))
        print(self.format_kv('Winner', winner))
        print(self.format_kv("Stats Wins", self.stats["wins"]))
        print(self.format_kv("Stats Losses", self.stats["losses"]))
        print(self.format_kv("Stats Draws", self.stats["draws"]))
        self.record('rounds', round_results)
        self.record('scores', {'player': player_score, 'computer': computer_score, 'winner': winner})       
        self.display_report()
        
    def finalize(self) -> None:
        self.export_state()
        self.log('Finalized successfully')
 
def main() -> None:
    app = RockPaperScissorsApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()












