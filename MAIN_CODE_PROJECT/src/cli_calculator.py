"""Build an Interactive Command-Line Calculator with Advanced Arithmetic Operations and Input Validation

Generated for the 45-day Python development challenge.
"""
from base_app import BaseApp, BaseAppState
from typing import Any, Dict, List, Optional, Tuple
import json
import time
import logging
from .log_setup import setup_logger

class CliCalculatorApp(BaseApp):
    def parse_expression(self, text: str) -> Tuple[float, str, float]:
        parts = text.split()
        if len(parts) != 3:
            raise ValueError('format: number operator number')
        return float(parts[0]), parts[1], float(parts[2])

    def compute(self, a: float, op: str, b: float) -> float:
        operations = {
            '+': a + b,
            '-': a - b,
            '*': a * b,
            '/': a / b if b != 0 else math.nan,
            '%': a % b if b != 0 else math.nan,
            '**': a ** b,
        }
        if op not in operations:
            raise ValueError('unsupported operation')
        return operations[op]

    def reset(self) -> None:
        self.state.records.clear()
        self.state.flags.clear()
        self.state.errors = 0

    def run(self) -> None:
        self.state.runs += 1
        self.reset()
        samples = ['5 + 2', '8 / 0', '4 ** 3', '10 ? 2']
        self.output.section('Calculator Runs')
        for item in samples:
            try:
                a, op, b = self.parse_expression(item)
                result = self.compute(a, op, b)
                self.output.kv(item, result)
            except Exception as exc:
                self.state.errors += 1
                print(self.format_kv(item, f'error: {exc}'))
        self.display_report()
    def cli_calculator_utility_1(self, value: Any) -> Any:
        """Utility routine 1 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_2(self, value: Any) -> Any:
        """Utility routine 2 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_3(self, value: Any) -> Any:
        """Utility routine 3 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_4(self, value: Any) -> Any:
        """Utility routine 4 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_5(self, value: Any) -> Any:
        """Utility routine 5 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_6(self, value: Any) -> Any:
        """Utility routine 6 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def cli_calculator_utility_7(self, value: Any) -> Any:
        """Utility routine 7 tuned for cli_calculator."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

                with self.state._lock:
                    self.state.errors += 1
                print(self.format_kv(item, f'error: {exc}'))
        self.display_report()
def main() -> None:
    app = CliCalculatorApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()

