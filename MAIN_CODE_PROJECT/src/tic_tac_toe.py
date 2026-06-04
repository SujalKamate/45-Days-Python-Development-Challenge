"""Build an Interactive Tic Tac Toe Gaming Application with Winner Detection Logic

Generated for the 45-day Python development challenge.
"""
from base_app import BaseApp, BaseAppState
from typing import Any, Dict, List, Optional, Tuple
import json
import time

class TicTacToeApp(BaseApp):
        def check_winner(b: List[str]) -> Optional[str]:
            win_indices = [
                (0, 1, 2), (3, 4, 5), (6, 7, 8),
                (0, 3, 6), (1, 4, 7), (2, 5, 8),
                (0, 4, 8), (2, 4, 6)
            ]

            for x, y, z in win_indices:
                if b[x] and b[x] == b[y] == b[z]:
                    return b[x]

            if all(cell != '' for cell in b):
                return 'Draw'

            return None

        results = []

        for game in items:
            board = game.get('board', [''] * 9)
            winner = check_winner(board)

            results.append({
                'board_state': board,
                'winner_status': winner if winner else 'In Progress'
            })

        return {
            'games_analyzed': len(items),
            'results': results
        }

    def run(self) -> None:
        self.state.runs += 1
        self.section('Processing')
        items = self.dataset()
        result = self.process_dataset(items)
        self.record('result', result)
        print(json.dumps(result, indent=2))
        self.display_report()
    def tic_tac_toe_utility_1(self, value: Any) -> Any:
        """Utility routine 1 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_2(self, value: Any) -> Any:
        """Utility routine 2 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_3(self, value: Any) -> Any:
        """Utility routine 3 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_4(self, value: Any) -> Any:
        """Utility routine 4 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_5(self, value: Any) -> Any:
        """Utility routine 5 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_6(self, value: Any) -> Any:
        """Utility routine 6 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def tic_tac_toe_utility_7(self, value: Any) -> Any:
        """Utility routine 7 tuned for tic_tac_toe."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

def main() -> None:
    app = TicTacToeApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()


