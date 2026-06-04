"""Centralized configuration with environment variable override support.

Usage::

    from .config import AppConfig
    self.cfg = AppConfig()

    self.cfg.output_dir         # Path — overridable via OUTPUT_DIR
    self.cfg.weather_api_url    # str  — overridable via WEATHER_API_URL
"""

import os
from pathlib import Path
from typing import List, Optional


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_list(key: str, default: str) -> List[str]:
    raw = os.getenv(key, default)
    return [s.strip() for s in raw.split(',') if s.strip()]


class AppConfig:
    """All defaults live here. Set environment variables to override at runtime."""

    def __init__(self) -> None:
        # Common — shared by all modules
        self.output_dir: Path = Path(_env_str('OUTPUT_DIR', 'outputs'))
        self.state_file_suffix: str = _env_str('STATE_FILE_SUFFIX', '_state.json')
        self.history_tail_default: int = _env_int('HISTORY_TAIL', 5)

        # Weather module
        self.weather_api_url: str = _env_str(
            'WEATHER_API_URL',
            'https://jsonplaceholder.typicode.com/users/1',
        )
        self.weather_user_agent: str = _env_str(
            'WEATHER_USER_AGENT',
            'Python45-Dev/1.0',
        )
        self.weather_timeout: int = _env_int('WEATHER_TIMEOUT', 10)
        self.weather_fallback_temp: int = _env_int('WEATHER_FALLBACK_TEMP', 72)
        self.weather_fallback_humidity: int = _env_int('WEATHER_FALLBACK_HUMIDITY', 55)
        self.weather_fallback_condition: str = _env_str(
            'WEATHER_FALLBACK_CONDITION',
            'Partly Cloudy',
        )
        self.weather_fallback_wind: int = _env_int('WEATHER_FALLBACK_WIND', 12)
        self.weather_conditions: List[str] = _env_list(
            'WEATHER_CONDITIONS',
            'Sunny,Partly Cloudy,Cloudy,Light Rain,Clear',
        )
        self.weather_forecast_days: int = _env_int('WEATHER_FORECAST_DAYS', 5)
        self.weather_forecast_base_temp: int = _env_int('WEATHER_FORECAST_BASE_TEMP', 68)
        self.weather_forecast_temp_inc: int = _env_int('WEATHER_FORECAST_TEMP_INC', 2)

        # Banking module
        self.banking_account_holder: str = _env_str(
            'BANKING_ACCOUNT_HOLDER',
            'John Doe',
        )
        self.banking_initial_balance: float = _env_float(
            'BANKING_INITIAL_BALANCE',
            1000.0,
        )
        self.banking_transaction_ops: List[str] = _env_list(
            'BANKING_TRANSACTIONS',
            'deposit:500,withdraw:200,withdraw:800,deposit:100',
        )

        # Calculator module
        self.calc_samples: List[str] = _env_list(
            'CALC_SAMPLES',
            '5 + 2,8 / 0,4 ** 3,10 ? 2',
        )
