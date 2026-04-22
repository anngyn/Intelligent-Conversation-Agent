"""Pytest configuration for test suite."""

import os
import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Change working directory to project root (for relative paths to work)
os.chdir(PROJECT_ROOT)
