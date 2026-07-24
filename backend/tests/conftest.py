"""Pytest configuration for delta-chat backend tests."""

import os
import sys

# Ensure TESTING mode
os.environ["TESTING"] = "true"

# Add the backend directory to sys.path so `src.*` imports work
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
