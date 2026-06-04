"""Design a Secure User Authentication Simulation with Username and Password Verification

Generated for the 45-day Python development challenge.
"""
from base_app import BaseApp, BaseAppState
from typing import Any, Dict, List, Optional, Tuple
import json
import time

class UserAuthSimulationApp(BaseApp):
    def authenticate(self, username: str, password: str) -> bool:
        users = {'admin': 'admin123', 'guest': 'guest123'}
        return users.get(username) == password

    def run(self) -> None:
        self.state.runs += 1
        attempts = [('admin', 'wrong'), ('admin', 'wrong2'), ('admin', 'wrong3'), ('admin', 'admin123')]
        locked = False
        failures = 0
        self.section('Authentication Simulation')
        for username, password in attempts:
            if locked:
                break
            ok = self.authenticate(username, password)
            # Log only the username and boolean outcome — never the password.
            print(self.format_kv(username, ok))
            if not ok:
                failures += 1
            if failures >= 3:
                locked = True
        # Clear the attempts list so plaintext passwords are released from
        # this frame as soon as the loop is done.
        attempts.clear()
        self.record('locked', locked)
        self.display_report()
    def user_auth_simulation_utility_1(self, value: Any) -> Any:
        """Utility routine 1 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_2(self, value: Any) -> Any:
        """Utility routine 2 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_3(self, value: Any) -> Any:
        """Utility routine 3 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_4(self, value: Any) -> Any:
        """Utility routine 4 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_5(self, value: Any) -> Any:
        """Utility routine 5 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_6(self, value: Any) -> Any:
        """Utility routine 6 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

    def user_auth_simulation_utility_7(self, value: Any) -> Any:
        """Utility routine 7 tuned for user_auth_simulation."""
        if isinstance(value, str):
            return self.normalize_text(value)
        if isinstance(value, (int, float)):
            return self.clamp(float(value), -1_000_000, 1_000_000)
        if isinstance(value, list):
            return [self.normalize_text(str(x)) for x in value]
        return value

def main() -> None:
    app = UserAuthSimulationApp()
    try:
        app.run()
        app.finalize()
    except KeyboardInterrupt:
        print('Interrupted by user')

if __name__ == '__main__':
    main()

