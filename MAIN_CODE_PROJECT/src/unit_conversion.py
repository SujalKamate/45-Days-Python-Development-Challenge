"""Design a Multipurpose Unit Conversion Utility Supporting Multiple Conversion Categories

Generated for the 45-day Python development challenge.
"""
from base_app import BaseApp, BaseAppState
from typing import Any, Dict, List, Optional, Tuple
import json
import time

class UnitConversionApp(BaseApp):
    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        from fractions import Fraction

        CONVERSIONS = {
            'celsius_to_fahrenheit': lambda v: v * Fraction(9, 5) + Fraction(32),
            'fahrenheit_to_celsius': lambda v: (v - Fraction(32)) * Fraction(5, 9),
            'km_to_miles': lambda v: v * Fraction(125000, 201168),
            'miles_to_km': lambda v: v * Fraction(201168, 125000),
            'kg_to_pounds': lambda v: v * Fraction(100000000, 45359237),
            'pounds_to_kg': lambda v: v * Fraction(45359237, 100000000),
            'liters_to_gallons': lambda v: v * Fraction(1000000000, 3785411784),
            'gallons_to_liters': lambda v: v * Fraction(3785411784, 1000000000),
        }

        results = []
        for item in items:
            raw = item.get('value', 0)
            from_conv = item.get('from', '')
            original = Fraction(str(raw))
            forward = CONVERSIONS[from_conv](original)
            parts = from_conv.split('_to_')
            if len(parts) == 2:
                reverse_key = f'{parts[1]}_to_{parts[0]}'
                roundtrip = CONVERSIONS[reverse_key](forward)
            else:
                roundtrip = forward
            error = abs(roundtrip - original)
            results.append({
                'value': float(original),
                'conversion': from_conv,
                'converted': float(forward),
                'roundtrip': float(roundtrip),
                'roundtrip_error': float(error),
                'exact_roundtrip': error == 0,
            })

        return {
            'conversions_performed': len(items),
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
    def unit_conversion_utility_1(self, value: Any) -> Any:
        """Utility routine 1 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_2(self, value: Any) -> Any:
        """Utility routine 2 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_3(self, value: Any) -> Any:
        """Utility routine 3 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_4(self, value: Any) -> Any:
        """Utility routine 4 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_5(self, value: Any) -> Any:
        """Utility routine 5 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_6(self, value: Any) -> Any:
        """Utility routine 6 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def unit_conversion_utility_7(self, value: Any) -> Any:
        """Utility routine 7 tuned for unit_conversion."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

def main() -> None:
    app = UnitConversionApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()


