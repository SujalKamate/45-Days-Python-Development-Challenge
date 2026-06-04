"""
Pytest configuration and shared fixtures
"""
import sys
import os
from pathlib import Path

# Add MAIN_CODE_PROJECT to path so we can import modules
main_code_project = Path(__file__).parent.parent
sys.path.insert(0, str(main_code_project))

# Provide the absolute path for tests that need it
BASE_DIR = str(main_code_project)
