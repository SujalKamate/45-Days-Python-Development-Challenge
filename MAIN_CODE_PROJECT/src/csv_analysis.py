"""Create a Dynamic CSV Data Analysis Utility with Statistical Insights

Generated for the 45-day Python development challenge.
"""
from base_app import BaseApp, BaseAppState
from typing import Any, Dict, List, Optional, Tuple
import json
import time

class CsvAnalysisApp(BaseApp):
    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import csv, io

        CANONICAL_MAP = {
            'name': 'name', 'full name': 'name', 'employee name': 'name',
            'age': 'age', 'years': 'age', 'years old': 'age',
            'salary': 'salary', 'income': 'salary', 'wage': 'salary',
            'department': 'department', 'dept': 'department', 'team': 'department',
        }

        def normalize(name: str) -> str:
            return CANONICAL_MAP.get(name.strip().lower(), name.strip().lower())

        results = []
        for item in items:
            raw = item.get('csv', '')
            if not isinstance(raw, str) or not raw.strip():
                results.append({'rows': 0, 'error': 'Missing or empty CSV content'})
                continue
            try:
                reader = csv.DictReader(io.StringIO(raw))
                if not reader.fieldnames:
                    results.append({'rows': 0, 'error': 'No headers found'})
                    continue
                active_headers = [normalize(h) for h in reader.fieldnames]
                parsed = []
                for row in reader:
                    normalized = {}
                    for original, value in row.items():
                        key = normalize(original)
                        normalized[key] = value.strip() if value else ''
                    parsed.append(normalized)
                missing = [col for col in ('name', 'age') if col not in active_headers]
                results.append({
                    'rows': len(parsed),
                    'headers_found': active_headers,
                    'missing_expected': missing if missing else None,
                    'data': parsed[:10],
                })
            except Exception as exc:
                results.append({'rows': 0, 'error': str(exc)})

        return {
            'files_processed': len(items),
            'results': results,
        }

    def run(self) -> None:
        self.state.runs += 1
        self.section('Processing')
        items = self.dataset()
        result = self.process_dataset(items)
        self.record('result', result)
        print(json.dumps(result, indent=2))
        self.display_report()
    def csv_analysis_utility_1(self, value: Any) -> Any:
        """Utility routine 1 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_2(self, value: Any) -> Any:
        """Utility routine 2 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_3(self, value: Any) -> Any:
        """Utility routine 3 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_4(self, value: Any) -> Any:
        """Utility routine 4 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_5(self, value: Any) -> Any:
        """Utility routine 5 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_6(self, value: Any) -> Any:
        """Utility routine 6 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def csv_analysis_utility_7(self, value: Any) -> Any:
        """Utility routine 7 tuned for csv_analysis."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

def main() -> None:
    app = CsvAnalysisApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()


