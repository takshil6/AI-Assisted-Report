"""
Offline smoke test: validates deterministic pieces of cleaner.py without
hitting the Groq API. Run this FIRST before running cleaner.py to catch
environment issues early.

Run:
    python tests/test_cleaner_offline.py
"""

import sys
from pathlib import Path

# Make src/ importable when running from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from cleaner import clean_dates, clean_revenue, _fallback_match, CANONICAL_REGIONS


def test_dates():
    series = pd.Series([
        "2024-03-15",
        "03/15/2024",
        "Mar 15, 2024",
        "15-Mar-2024",
        "garbage",
    ])
    result = clean_dates(series)
    assert result.iloc[0].year == 2024
    assert result.iloc[0].month == 3
    assert result.iloc[0].day == 15
    assert pd.isna(result.iloc[4])  # unparseable -> NaT
    print("✓ test_dates passed")


def test_revenue():
    assert clean_revenue(1234.56) == 1234.56
    assert clean_revenue("$1,234.56") == 1234.56
    assert clean_revenue("1,000") == 1000.0
    assert clean_revenue(None) is None
    assert clean_revenue("garbage") is None
    assert clean_revenue(-500) == -500.0
    print("✓ test_revenue passed")


def test_fallback_match():
    assert _fallback_match("north east", CANONICAL_REGIONS) == "Northeast"
    assert _fallback_match("wild guess", CANONICAL_REGIONS) == "Northeast"  # default
    print("✓ test_fallback_match passed")


if __name__ == "__main__":
    test_dates()
    test_revenue()
    test_fallback_match()
    print("\nAll offline tests passed. Safe to run the real pipeline.")
