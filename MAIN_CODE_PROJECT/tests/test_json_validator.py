import pytest
from pathlib import Path
import json
from src.json_validator import (
    validate_schema,
    safe_load_json,
    safe_save_json,
    generate_signature,
    generate_checksum,
    JsonValidatorApp
)

def test_validate_schema_basic():
    # Basic types
    assert validate_schema(10, int) is True
    assert validate_schema("hello", str) is True
    assert validate_schema(10.5, float) is True
    assert validate_schema(True, bool) is True
    
    # Typos/mismatches
    assert validate_schema("hello", int) is False
    assert validate_schema(10, str) is False
    
    # Bool should not be accepted as int in strict validation
    assert validate_schema(True, int) is False


def test_validate_schema_tuple():
    assert validate_schema(10, (int, float)) is True
    assert validate_schema(10.5, (int, float)) is True
    assert validate_schema("hello", (int, float)) is False
    # Bool check in tuple
    assert validate_schema(True, (int, float)) is False


def test_validate_schema_dict():
    schema = {
        "name": str,
        "age": int,
        "active": bool
    }
    
    valid_data = {
        "name": "Alice",
        "age": 30,
        "active": True
    }
    
    invalid_data_type = {
        "name": "Alice",
        "age": "30", # wrong type
        "active": True
    }
    
    invalid_data_missing = {
        "name": "Alice",
        "age": 30
        # missing active
    }
    
    assert validate_schema(valid_data, schema) is True
    assert validate_schema(invalid_data_type, schema) is False
    assert validate_schema(invalid_data_missing, schema) is False
    assert validate_schema([1, 2, 3], schema) is False


def test_validate_schema_nested_dict():
    schema = {
        "name": str,
        "details": {
            "height": float,
            "hobbies": [str]
        }
    }
    
    valid_data = {
        "name": "Bob",
        "details": {
            "height": 1.75,
            "hobbies": ["reading", "running"]
        }
    }
    
    invalid_data_nested_type = {
        "name": "Bob",
        "details": {
            "height": 1.75,
            "hobbies": ["reading", 42] # list has int instead of str
        }
    }
    
    assert validate_schema(valid_data, schema) is True
    assert validate_schema(invalid_data_nested_type, schema) is False


def test_safe_load_json_basic(tmp_path):
    data_path = tmp_path / "data.json"
    payload = {"name": "test", "version": 1}
    
    # Save standard JSON without integrity
    data_path.write_text(json.dumps(payload), encoding='utf-8')
    
    # Load without schema or integrity check
    loaded = safe_load_json(data_path)
    assert loaded == payload
    
    # Load with valid schema
    loaded = safe_load_json(data_path, schema={"name": str, "version": int})
    assert loaded == payload
    
    # Load with invalid schema
    with pytest.raises(ValueError, match="Schema validation failed"):
        safe_load_json(data_path, schema={"name": int})


def test_safe_load_json_file_missing():
    with pytest.raises(ValueError, match="File not found"):
        safe_load_json(Path("non_existent_file.json"))


def test_safe_load_json_invalid_json(tmp_path):
    data_path = tmp_path / "data.json"
    data_path.write_text("invalid json { content", encoding='utf-8')
    
    with pytest.raises(ValueError, match="Invalid JSON"):
        safe_load_json(data_path)


def test_safe_load_json_not_dict(tmp_path):
    data_path = tmp_path / "data.json"
    data_path.write_text("[1, 2, 3]", encoding='utf-8')
    
    with pytest.raises(ValueError, match="Expected dict"):
        safe_load_json(data_path)


def test_safe_load_json_sidecar_checksum(tmp_path):
    data_path = tmp_path / "data.json"
    payload = {"foo": "bar"}
    
    # Save with sidecar checksum
    safe_save_json(data_path, payload, use_sidecar=True)
    
    checksum_path = tmp_path / "data.json.sha256"
    assert checksum_path.exists()
    
    # Success loading
    loaded = safe_load_json(data_path)
    assert loaded == payload
    
    # Tamper the file contents
    data_path.write_text(json.dumps({"foo": "hacked"}), encoding='utf-8')
    with pytest.raises(ValueError, match="Checksum mismatch"):
        safe_load_json(data_path)


def test_safe_load_json_sidecar_signature(tmp_path):
    data_path = tmp_path / "data.json"
    payload = {"foo": "bar"}
    key = b"supersecretkey"
    
    # Save with sidecar signature
    safe_save_json(data_path, payload, secret_key=key, use_sidecar=True)
    
    sig_path = tmp_path / "data.json.sig"
    assert sig_path.exists()
    
    # Success loading
    loaded = safe_load_json(data_path, secret_key=key)
    assert loaded == payload
    
    # Failure if wrong key
    with pytest.raises(ValueError, match="Signature mismatch"):
        safe_load_json(data_path, secret_key=b"wrongkey")
        
    # Failure if no key
    with pytest.raises(ValueError, match="no secret key provided"):
        safe_load_json(data_path)


def test_safe_load_json_inline_checksum(tmp_path):
    data_path = tmp_path / "data.json"
    payload = {"foo": "bar"}
    
    # Save with inline checksum
    safe_save_json(data_path, payload, use_sidecar=False)
    
    assert not (tmp_path / "data.json.sha256").exists()
    
    # Success loading
    loaded = safe_load_json(data_path)
    assert loaded == payload
    
    # Tamper inline checksum data
    raw = json.loads(data_path.read_text(encoding='utf-8'))
    raw['foo'] = 'hacked' # change content but not checksum
    data_path.write_text(json.dumps(raw), encoding='utf-8')
    
    with pytest.raises(ValueError, match="Inline checksum mismatch"):
        safe_load_json(data_path)


def test_safe_load_json_inline_signature(tmp_path):
    data_path = tmp_path / "data.json"
    payload = {"foo": "bar"}
    key = b"mysecret"
    
    # Save with inline signature
    safe_save_json(data_path, payload, secret_key=key, use_sidecar=False)
    
    # Success loading
    loaded = safe_load_json(data_path, secret_key=key)
    assert loaded == payload
    
    # Failure if no key
    with pytest.raises(ValueError, match="no secret key provided"):
        safe_load_json(data_path)
        
    # Failure if wrong key
    with pytest.raises(ValueError, match="Inline signature mismatch"):
        safe_load_json(data_path, secret_key=b"wrongkey")


def test_json_validator_app():
    app = JsonValidatorApp()
    assert app.state.runs == 0
    app.run()
    assert app.state.runs == 1
    assert len(app.state.history) > 0
    
    demo = app.demo_data()
    assert isinstance(demo, list)
    assert len(demo) > 0
    
    result = app.process_dataset(demo)
    assert "results" in result
    assert result["results"][0]["valid"] is True
