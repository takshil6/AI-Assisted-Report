"""
Offline tests for Phase 3 analyzer. Uses a tiny hand-crafted dataset where
we can verify every output manually.

Run:
    python tests/test_analyzer_offline.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyzer import (
    customer_pareto, pareto_summary,
    segment_breakdown, region_breakdown,
    weekly_revenue, weekly_summary,
)


def _fixture() -> pd.DataFrame:
    """
    Tiny 8-row dataset designed so we can manually verify every aggregation.
    Customer A has $800 of revenue, B has $150, C has $50. Total = $1000.
    Customer A alone should be the 80/20 tier (80% exactly).
    """
    return pd.DataFrame({
        "transaction_id":          ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"],
        "customer_name_clean":     ["A", "A", "A", "A", "B", "B", "B", "C"],
        "region_clean":            ["East", "East", "West", "West", "East", "West", "East", "West"],
        "industry_segment_clean":  ["Paper", "Paper", "Paper", "Paper", "Mining", "Mining", "Mining", "Paper"],
        "revenue_usd_clean":       [200.0, 200.0, 200.0, 200.0, 50.0, 50.0, 50.0, 50.0],
        "order_date_clean":        pd.to_datetime([
            "2024-01-02", "2024-01-09", "2024-01-16", "2024-01-23",
            "2024-01-02", "2024-01-09", "2024-01-16", "2024-01-23",
        ]),
    })


def test_customer_pareto():
    df = _fixture()
    p = customer_pareto(df)

    # Must be sorted descending by revenue
    assert list(p["customer_name_clean"]) == ["A", "B", "C"]

    # Revenue totals
    assert p.iloc[0]["revenue"] == 800.0
    assert p.iloc[1]["revenue"] == 150.0
    assert p.iloc[2]["revenue"] == 50.0

    # Cumulative percentages (total = 1000)
    assert p.iloc[0]["cumulative_pct"] == 80.0
    assert p.iloc[1]["cumulative_pct"] == 95.0
    assert p.iloc[2]["cumulative_pct"] == 100.0

    # Only customer A is in the 80/20 tier (A crosses 80% exactly)
    assert p.iloc[0]["is_pareto_80"] == True
    assert p.iloc[1]["is_pareto_80"] == False
    assert p.iloc[2]["is_pareto_80"] == False

    print("✓ test_customer_pareto passed")


def test_pareto_summary():
    df = _fixture()
    p = customer_pareto(df)
    s = pareto_summary(p)

    assert s["total_customers"] == 3
    assert s["pareto_customers"] == 1
    assert s["top_1_customer"] == "A"
    # 1 of 3 customers = 33.3%
    assert s["pareto_customer_pct"] == 33.3
    print("✓ test_pareto_summary passed")


def test_segment_breakdown():
    df = _fixture()
    s = segment_breakdown(df)

    # Paper: A's 800 + C's 50 = 850.  Mining: B's 150.
    paper = s[s["industry_segment_clean"] == "Paper"].iloc[0]
    mining = s[s["industry_segment_clean"] == "Mining"].iloc[0]

    assert paper["revenue"] == 850.0
    assert mining["revenue"] == 150.0
    assert paper["pct_of_total"] == 85.0
    assert paper["unique_customers"] == 2      # A and C sold Paper
    assert mining["unique_customers"] == 1     # only B sold Mining
    print("✓ test_segment_breakdown passed")


def test_region_breakdown():
    df = _fixture()
    r = region_breakdown(df)

    # East: T1(200)+T2(200)+T5(50)+T7(50) = 500.  West: T3(200)+T4(200)+T6(50)+T8(50) = 500.
    assert r["revenue"].sum() == 1000.0
    assert r.iloc[0]["pct_of_total"] == 50.0
    print("✓ test_region_breakdown passed")


def test_weekly_revenue():
    df = _fixture()
    w = weekly_revenue(df)

    # 4 weekly buckets exist (Jan 2, 9, 16, 23, 2024). Exact count depends on
    # where pandas snaps week-ends, but we should have revenue in each.
    assert len(w) >= 3
    assert w["revenue"].sum() == 1000.0
    # First week's WoW change is always NaN
    assert pd.isna(w["wow_change_pct"].iloc[0])
    print("✓ test_weekly_revenue passed")


def test_weekly_summary():
    df = _fixture()
    w = weekly_revenue(df)
    s = weekly_summary(w)

    assert s["weeks_covered"] == len(w)
    assert s["best_week_revenue"] >= s["worst_week_revenue"]
    print("✓ test_weekly_summary passed")


if __name__ == "__main__":
    test_customer_pareto()
    test_pareto_summary()
    test_segment_breakdown()
    test_region_breakdown()
    test_weekly_revenue()
    test_weekly_summary()
    print("\nAll Phase 3 offline tests passed. Safe to run the real analyzer.")
