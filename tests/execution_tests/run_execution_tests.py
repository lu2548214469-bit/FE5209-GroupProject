"""Execution framework tests (synthetic data only, no market data needed).

    python tests/execution_tests/run_execution_tests.py

Accounting identities, zero-volume delays, lots and minimum fees, cash and T+2 settlement,
splits / dividends / delisting, no look-ahead, and the 14-day dividend policy.
"""
import sys
import unittest
from pathlib import Path

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(here), pattern="test_*.py", top_level_dir=str(here))
    sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
