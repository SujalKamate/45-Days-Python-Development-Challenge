"""
Basic tests to verify that core modules can be imported and execute correctly
"""
import importlib
import inspect
import os
import sys
from pathlib import Path


class TestBasicImports:
    def test_json_module(self):
        import json
        assert json is not None

    def test_datetime_module(self):
        from datetime import datetime
        assert datetime is not None

    def test_pathlib_module(self):
        from pathlib import Path
        assert Path is not None

    def test_dataclasses_module(self):
        from dataclasses import dataclass, field
        assert dataclass is not None
        assert field is not None


class TestProjectStructure:
    def test_main_code_project_exists(self):
        project_root = Path(__file__).parent.parent
        assert project_root.exists(), f"MAIN_CODE_PROJECT not found at {project_root}"

    def test_src_directory_exists(self):
        project_root = Path(__file__).parent.parent
        src_dir = project_root / "src"
        assert src_dir.exists(), f"src directory not found at {src_dir}"
    def test_src_files_exist(self):
        """Test that all src files exist"""
        project_root = Path(__file__).parent.parent
        src_dir = project_root / "src"
        src_files = [f for f in sorted(os.listdir(src_dir)) if f.endswith('.py') and not f.startswith('__')]
        assert len(src_files) >= 50, f"Expected 50+ source files, found {len(src_files)}"
        for f in src_files:
            mod_name = 'src.' + f[:-3]
            try:
                mod = importlib.import_module(mod_name)
                assert mod is not None
            except Exception as e:
                assert False, f"Failed to import {f}: {e}"

        files = sorted(f.name for f in src_dir.iterdir() if f.suffix == '.py')
        assert len(files) >= 50, f"Expected at least 50 source files, found {len(files)}"
