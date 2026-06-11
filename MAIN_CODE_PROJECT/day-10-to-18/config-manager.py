"""
Multi-Format Config File Manager with Validation, Defaults and Override Priority
Reads/writes .ini and JSON configs, validates keys, merges with priority order.
"""

import json
import os
import configparser
from copy import deepcopy
from datetime import datetime


# ── Schema & Defaults ──────────────────────────────────────────────────────────
CONFIG_SCHEMA = {
    "app": {
        "name":        {"type": str,   "default": "MyApp",     "required": True},
        "version":     {"type": str,   "default": "1.0.0",     "required": True},
        "debug":       {"type": bool,  "default": False,        "required": False},
        "log_level":   {"type": str,   "default": "INFO",       "required": False,
                        "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]},
        "max_workers": {"type": int,   "default": 4,            "required": False,
                        "min": 1, "max": 64},
    },
    "database": {
        "host":        {"type": str,   "default": "localhost",  "required": True},
        "port":        {"type": int,   "default": 5432,         "required": True,
                        "min": 1, "max": 65535},
        "name":        {"type": str,   "default": "mydb",       "required": True},
        "user":        {"type": str,   "default": "admin",      "required": True},
        "password":    {"type": str,   "default": "",           "required": False},
        "pool_size":   {"type": int,   "default": 10,           "required": False,
                        "min": 1, "max": 100},
        "timeout":     {"type": float, "default": 30.0,         "required": False,
                        "min": 0.1, "max": 300.0},
    },
    "server": {
        "host":        {"type": str,   "default": "0.0.0.0",   "required": True},
        "port":        {"type": int,   "default": 8080,         "required": True,
                        "min": 1, "max": 65535},
        "ssl":         {"type": bool,  "default": False,        "required": False},
        "cors":        {"type": bool,  "default": True,         "required": False},
        "rate_limit":  {"type": int,   "default": 100,          "required": False,
                        "min": 1, "max": 10000},
    },
    "cache": {
        "backend":     {"type": str,   "default": "memory",     "required": False,
                        "choices": ["memory", "redis", "memcached"]},
        "ttl":         {"type": int,   "default": 300,          "required": False,
                        "min": 0},
        "max_size":    {"type": int,   "default": 1000,         "required": False,
                        "min": 1},
    },
}


def get_defaults():
    """Build a flat dict of section -> {key: default_value} from schema."""
    defaults = {}
    for section, keys in CONFIG_SCHEMA.items():
        defaults[section] = {k: v["default"] for k, v in keys.items()}
    return defaults


# ── Validation ─────────────────────────────────────────────────────────────────
def coerce_value(value, type_cls):
    """Coerce a string/raw value to the target type."""
    if isinstance(value, type_cls):
        return value
    if type_cls == bool:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    return type_cls(value)


def validate_config(config: dict) -> list:
    """
    Validate config against schema.
    Returns list of error strings (empty = valid).
    """
    errors = []
    for section, keys in CONFIG_SCHEMA.items():
        sec_data = config.get(section, {})
        for key, rules in keys.items():
            val = sec_data.get(key)

            # Required check
            if rules.get("required") and (val is None or val == ""):
                errors.append(f"[{section}].{key} is required but missing.")
                continue

            if val is None:
                continue

            # Type coercion + check
            try:
                val = coerce_value(val, rules["type"])
                sec_data[key] = val
            except (ValueError, TypeError) as e:
                errors.append(f"[{section}].{key} type error: {e}")
                continue

            # Choices check
            if "choices" in rules and val not in rules["choices"]:
                errors.append(f"[{section}].{key}={val!r} not in {rules['choices']}")

            # Range checks
            if "min" in rules and val < rules["min"]:
                errors.append(f"[{section}].{key}={val} < min={rules['min']}")
            if "max" in rules and val > rules["max"]:
                errors.append(f"[{section}].{key}={val} > max={rules['max']}")

    return errors


# ── Readers ────────────────────────────────────────────────────────────────────
def read_ini(filepath: str) -> dict:
    parser = configparser.ConfigParser()
    if not parser.read(filepath):
        raise FileNotFoundError(f"INI file not found: {filepath}")
    return {section: dict(parser[section]) for section in parser.sections()}


def read_json(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


def read_config(filepath: str) -> dict:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".ini", ".cfg", ".conf"):
        return read_ini(filepath)
    elif ext == ".json":
        return read_json(filepath)
    raise ValueError(f"Unsupported config format: {ext}")


# ── Writers ────────────────────────────────────────────────────────────────────
def write_ini(config: dict, filepath: str):
    parser = configparser.ConfigParser()
    for section, keys in config.items():
        parser[section] = {k: str(v) for k, v in keys.items()}
    with open(filepath, "w") as f:
        parser.write(f)


def write_json(config: dict, filepath: str, pretty=True):
    with open(filepath, "w") as f:
        json.dump(config, f, indent=2 if pretty else None)


def write_config(config: dict, filepath: str):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".ini", ".cfg", ".conf"):
        write_ini(config, filepath)
    elif ext == ".json":
        write_json(config, filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}")
    print(f"  ✓ Config written to '{filepath}'")


# ── Merging with Priority ──────────────────────────────────────────────────────
def deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base (override wins). Mutates and returns base copy."""
    result = deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def merge_configs(*configs) -> dict:
    """
    Merge multiple configs left to right — later configs have higher priority.
    configs[0] = lowest priority (defaults), configs[-1] = highest (env/CLI).
    """
    result = {}
    for cfg in configs:
        result = deep_merge(result, cfg)
    return result


# ── Display ────────────────────────────────────────────────────────────────────
def print_config(config: dict, title="Configuration"):
    print(f"\n  {'═'*55}")
    print(f"  {title}")
    print(f"  {'═'*55}")
    for section, keys in config.items():
        print(f"\n  [{section}]")
        for k, v in keys.items():
            # Mask passwords
            display = "***" if "password" in k.lower() or "secret" in k.lower() else str(v)
            print(f"    {k:<18} = {display}")
    print(f"  {'═'*55}\n")


def print_validation(errors):
    if not errors:
        print("  ✓ Config validation passed — no errors.")
    else:
        print(f"  ✗ {len(errors)} validation error(s):")
        for e in errors:
            print(f"    • {e}")


# ── Demo ───────────────────────────────────────────────────────────────────────
def create_demo_ini(path):
    content = """
[app]
name = ProductionApp
version = 2.1.0
debug = false
log_level = WARNING
max_workers = 8

[database]
host = db.prod.example.com
port = 5432
name = proddb
user = app_user
password = s3cr3t
pool_size = 20
timeout = 60.0

[server]
host = 0.0.0.0
port = 443
ssl = true
cors = false
rate_limit = 500
"""
    with open(path, "w") as f:
        f.write(content.strip())


def create_dev_json(path):
    dev = {
        "app": {"debug": True, "log_level": "DEBUG", "max_workers": 2},
        "database": {"host": "localhost", "name": "devdb", "password": "devpass"},
        "server": {"port": 8080, "ssl": False, "rate_limit": 10},
        "cache": {"backend": "memory", "ttl": 60},
    }
    with open(path, "w") as f:
        json.dump(dev, f, indent=2)


def create_env_override(path):
    env = {
        "app": {"name": "MyApp-Env", "debug": False},
        "server": {"port": 9090},
    }
    with open(path, "w") as f:
        json.dump(env, f, indent=2)


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Multi-Format Config Manager v1.0      ║")
    print("╚══════════════════════════════════════════╝")

    # Create demo config files
    ini_path  = "prod.ini"
    dev_path  = "dev.json"
    env_path  = "env_override.json"

    create_demo_ini(ini_path)
    create_dev_json(dev_path)
    create_env_override(env_path)

    print("\n  [1] Reading individual configs...")
    prod_cfg = read_config(ini_path)
    dev_cfg  = read_config(dev_path)
    env_cfg  = read_config(env_path)

    print_config(prod_cfg, "Production (INI)")
    print_config(dev_cfg,  "Development (JSON)")

    print("\n  [2] Applying defaults for missing keys...")
    defaults = get_defaults()
    full_prod = merge_configs(defaults, prod_cfg)
    full_dev  = merge_configs(defaults, prod_cfg, dev_cfg)  # dev overrides prod

    print_config(full_prod, "Production + Defaults")
    print_config(full_dev,  "Dev overrides Prod (merged)")

    print("\n  [3] Applying environment overrides (highest priority)...")
    final_cfg = merge_configs(defaults, prod_cfg, dev_cfg, env_cfg)
    print_config(final_cfg, "Final Config (defaults < prod < dev < env)")

    print("\n  [4] Validating configs...")
    errors_prod = validate_config(full_prod)
    print("  Production config:"); print_validation(errors_prod)

    # Create invalid config for demo
    bad_cfg = merge_configs(defaults, {
        "app":      {"log_level": "VERBOSE", "max_workers": 200},
        "database": {"port": 99999},
        "server":   {"port": -1},
        "cache":    {"backend": "sqlite"},
    })
    errors_bad = validate_config(bad_cfg)
    print("\n  Invalid config:"); print_validation(errors_bad)

    print("\n  [5] Writing merged config to new files...")
    write_config(final_cfg, "merged_config.json")
    write_config(final_cfg, "merged_config.ini")

    print("\n  [6] Round-trip test (json → read → write → compare)...")
    read_back = read_config("merged_config.json")
    # Validate round-trip
    for section in final_cfg:
        for key in final_cfg.get(section, {}):
            orig = str(final_cfg[section][key])
            back = str(read_back.get(section, {}).get(key, "MISSING"))
            if orig != back:
                print(f"  ✗ Mismatch [{section}].{key}: {orig!r} vs {back!r}")
    print("  ✓ Round-trip verification complete.")

    # Cleanup
    for f in [ini_path, dev_path, env_path, "merged_config.json", "merged_config.ini"]:
        if os.path.exists(f):
            os.remove(f)

    print("\n  All config operations complete.")


if __name__ == "__main__":
    main()
