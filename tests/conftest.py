"""
tests/conftest.py
──────────────────────────────────────────────────────────────────────────────
Shared pytest fixtures and configuration for Intelli-Credit test suite.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os

# Ensure backend is importable from all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (skip with -m 'not slow')")
    config.addinivalue_line("markers", "integration: marks tests requiring the full app stack")
    config.addinivalue_line("markers", "unit: marks pure unit tests (no DB, no HTTP)")
