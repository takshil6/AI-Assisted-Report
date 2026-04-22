"""
Phase 3: 80/20 Pareto Analysis Engine
======================================
Reads the cleaned dataset from Phase 2 and produces the analytical outputs
that drive Kadant's 80/20 program:

    1. CUSTOMER PARETO: which customers generate 80% of revenue?
    2. SEGMENT MIX:     which industry segments dominate the business?
    3. REGION MIX:      which regions dominate the business?
    4. WEEKLY TREND:    how is revenue evolving week over week?
    5. 80/20 TIER:      the VIP customer list that gets preferential pricing/service

No AI calls here -- this is pure, deterministic pandas. The cleaner did the
hard semantic work in Phase 2; now we just aggregate.

Run:
    python src/analyzer.py

Outputs:
    data/analysis_results.json        -- all metrics, structured for Phase 4
    data/customer_pareto.csv          -- customer-level with cumulative %
    data/segment_breakdown.csv        -- revenue by segment
    data/region_breakdown.csv         -- revenue by region
    data/weekly_revenue.csv           -- time series
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PARETO_THRESHOLD = 0.80              # the "80" in 80/20 -- top customers driving 80% of revenue
TOP_N_CUSTOMERS_IN_REPORT = 20       # how many rows to include in detail tables

INPUT_PATH = "data/clean_transactions.csv"
OUTPUT_JSON = "data/analysis_results.json"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_clean_data(path: str = INPUT_PATH) -> pd.DataFrame:
    """
    Load the cleaned transactions from Phase 2. Does basic validation so
    Phase 3 fails loudly if Phase 2 didn't run.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{path} not found. Run Phase 2 first:  python src/cleaner.py"
        )

    df = pd.read_csv(p, parse_dates=["order_date_clean"])

    required = {"customer_name_clean", "region_clean", "industry_segment_clean",
                "revenue_usd_clean", "order_date_clean"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{path} is missing expected columns: {missing}. "
            "Re-run Phase 2 to regenerate it."
        )

    # Drop rows with null revenue -- can't aggregate what isn't there.
    # We log this rather than silently dropping.
    null_count = int(df["revenue_usd_clean"].isna().sum())
    if null_count:
        print(f"  Note: dropping {null_count} rows with null revenue from analysis.")
    df = df.dropna(subset=["revenue_usd_clean"]).copy()

    # Also drop negative revenue (refunds/returns) from the Pareto analysis
    # since they distort cumulative curves. We could treat them differently
    # for a net-revenue view -- a real project would expose this as a flag.
    neg_count = int((df["revenue_usd_clean"] < 0).sum())
    if neg_count:
        print(f"  Note: excluding {neg_count} negative-revenue rows (refunds/returns).")
    df = df[df["revenue_usd_clean"] >= 0].copy()

    return df


# ---------------------------------------------------------------------------
# 1. Customer Pareto (the core 80/20 analysis)
# ---------------------------------------------------------------------------
def customer_pareto(df: pd.DataFrame, threshold: float = PARETO_THRESHOLD) -> pd.DataFrame:
    """
    For each customer, compute total revenue, rank them descending, and mark
    which customers collectively account for `threshold` of total revenue.

    Returns a DataFrame with columns:
        customer_name_clean, revenue, transactions, avg_order_value,
        rank, pct_of_total, cumulative_pct, is_pareto_80

    `is_pareto_80` is True for the minimal set of top customers whose
    cumulative revenue crosses the threshold. Those are the "80/20 customers"
    that Kadant would treat as VIPs.
    """
    agg = (
        df.groupby("customer_name_clean", as_index=False)
          .agg(revenue=("revenue_usd_clean", "sum"),
               transactions=("transaction_id", "count"),
               avg_order_value=("revenue_usd_clean", "mean"))
          .sort_values("revenue", ascending=False)
          .reset_index(drop=True)
    )

    total = agg["revenue"].sum()
    agg["rank"] = agg.index + 1
    agg["pct_of_total"] = agg["revenue"] / total
    agg["cumulative_pct"] = agg["pct_of_total"].cumsum()

    # Include the first customer that pushes cumulative % past the threshold.
    # This is the minimal set, not the largest set still under threshold.
    agg["is_pareto_80"] = False
    crossed = False
    for idx, row in agg.iterrows():
        agg.at[idx, "is_pareto_80"] = True
        if row["cumulative_pct"] >= threshold and not crossed:
            crossed = True
            # Mark only up to and including this row
            agg.loc[idx + 1:, "is_pareto_80"] = False
            break

    # Round for readability
    agg["revenue"] = agg["revenue"].round(2)
    agg["avg_order_value"] = agg["avg_order_value"].round(2)
    agg["pct_of_total"] = (agg["pct_of_total"] * 100).round(2)
    agg["cumulative_pct"] = (agg["cumulative_pct"] * 100).round(2)

    return agg


def pareto_summary(pareto_df: pd.DataFrame) -> dict:
    """
    Condense the Pareto table into headline stats:
        - How many customers drive 80%?
        - What % of customers is that?
        - What's the actual revenue share?
    """
    total_customers = len(pareto_df)
    vip = pareto_df[pareto_df["is_pareto_80"]]
    vip_count = len(vip)
    vip_revenue_pct = float(vip["pct_of_total"].sum())

    return {
        "total_customers": total_customers,
        "pareto_customers": vip_count,
        "pareto_customer_pct": round(100 * vip_count / total_customers, 1),
        "pareto_revenue_pct": round(vip_revenue_pct, 1),
        "top_1_customer": pareto_df.iloc[0]["customer_name_clean"],
        "top_1_revenue_pct": float(pareto_df.iloc[0]["pct_of_total"]),
    }


# ---------------------------------------------------------------------------
# 2 & 3. Segment and region breakdowns
# ---------------------------------------------------------------------------
def _dimension_breakdown(df: pd.DataFrame, dimension_col: str) -> pd.DataFrame:
    """Generic grouper for 'revenue by X' breakdowns (segment, region, etc.)."""
    total = df["revenue_usd_clean"].sum()

    out = (
        df.groupby(dimension_col, as_index=False)
          .agg(revenue=("revenue_usd_clean", "sum"),
               transactions=("transaction_id", "count"),
               unique_customers=("customer_name_clean", "nunique"))
          .sort_values("revenue", ascending=False)
          .reset_index(drop=True)
    )
    out["pct_of_total"] = (out["revenue"] / total * 100).round(2)
    out["revenue"] = out["revenue"].round(2)
    return out


def segment_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    return _dimension_breakdown(df, "industry_segment_clean")


def region_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    return _dimension_breakdown(df, "region_clean")


# ---------------------------------------------------------------------------
# 4. Weekly time series
# ---------------------------------------------------------------------------
def weekly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    Revenue aggregated by ISO week. Useful for trend lines in the report
    and for 'week over week' comparisons.
    """
    weekly = (
        df.set_index("order_date_clean")
          .resample("W")["revenue_usd_clean"]
          .agg(["sum", "count"])
          .rename(columns={"sum": "revenue", "count": "transactions"})
          .reset_index()
    )
    weekly["revenue"] = weekly["revenue"].round(2)

    # Week-over-week change (first week is NaN, that's expected)
    weekly["wow_change_pct"] = (
        weekly["revenue"].pct_change() * 100
    ).round(2)

    return weekly


def weekly_summary(weekly_df: pd.DataFrame) -> dict:
    """Headline stats from the weekly series."""
    if weekly_df.empty:
        return {}

    return {
        "weeks_covered":       len(weekly_df),
        "avg_weekly_revenue":  round(float(weekly_df["revenue"].mean()), 2),
        "best_week_revenue":   round(float(weekly_df["revenue"].max()), 2),
        "worst_week_revenue":  round(float(weekly_df["revenue"].min()), 2),
        "latest_week_revenue": round(float(weekly_df["revenue"].iloc[-1]), 2),
        "latest_wow_change":   (
            round(float(weekly_df["wow_change_pct"].iloc[-1]), 2)
            if pd.notna(weekly_df["wow_change_pct"].iloc[-1]) else None
        ),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_analysis(
    input_path: str = INPUT_PATH,
    output_json: str = OUTPUT_JSON,
) -> dict:
    """
    End-to-end Phase 3. Writes four CSVs and one JSON summary, and returns
    the summary dict.
    """
    print(f"Loading {input_path}...")
    df = load_clean_data(input_path)
    print(f"  {len(df):,} analyzable rows (after dropping nulls/negatives)\n")

    print("Running customer Pareto analysis...")
    pareto = customer_pareto(df)
    pareto.to_csv("data/customer_pareto.csv", index=False)
    p_summary = pareto_summary(pareto)

    print("Building segment breakdown...")
    segments = segment_breakdown(df)
    segments.to_csv("data/segment_breakdown.csv", index=False)

    print("Building region breakdown...")
    regions = region_breakdown(df)
    regions.to_csv("data/region_breakdown.csv", index=False)

    print("Computing weekly revenue trend...")
    weekly = weekly_revenue(df)
    weekly.to_csv("data/weekly_revenue.csv", index=False)
    w_summary = weekly_summary(weekly)

    # Overall dataset summary
    dataset_summary = {
        "total_revenue":       round(float(df["revenue_usd_clean"].sum()), 2),
        "total_transactions":  len(df),
        "date_range_start":    df["order_date_clean"].min().strftime("%Y-%m-%d"),
        "date_range_end":      df["order_date_clean"].max().strftime("%Y-%m-%d"),
        "unique_customers":    int(df["customer_name_clean"].nunique()),
        "unique_segments":     int(df["industry_segment_clean"].nunique()),
        "unique_regions":      int(df["region_clean"].nunique()),
    }

    # Assemble the full analysis result for Phase 4 to consume
    results = {
        "dataset_summary":  dataset_summary,
        "pareto_summary":   p_summary,
        "weekly_summary":   w_summary,
        "top_customers":    pareto.head(TOP_N_CUSTOMERS_IN_REPORT).to_dict(orient="records"),
        "segment_breakdown": segments.to_dict(orient="records"),
        "region_breakdown":  regions.to_dict(orient="records"),
        # weekly series kept in CSV only -- too long for JSON headlines
    }

    Path(output_json).write_text(json.dumps(results, indent=2, default=str))

    _print_report(dataset_summary, p_summary, segments, regions, w_summary)
    print(f"\nSaved all analysis outputs under data/")
    return results


def _print_report(dataset, pareto, segments, regions, weekly) -> None:
    """Pretty terminal output so you can read results without opening files."""
    print("\n" + "=" * 64)
    print("ANALYSIS REPORT")
    print("=" * 64)

    print(f"\nDataset")
    print(f"  Date range:         {dataset['date_range_start']}  ->  {dataset['date_range_end']}")
    print(f"  Total revenue:      ${dataset['total_revenue']:>15,.2f}")
    print(f"  Transactions:       {dataset['total_transactions']:>16,}")
    print(f"  Unique customers:   {dataset['unique_customers']:>16}")

    print(f"\n80/20 Pareto")
    print(f"  Top {pareto['pareto_customers']} of {pareto['total_customers']} "
          f"customers ({pareto['pareto_customer_pct']}%) "
          f"drive {pareto['pareto_revenue_pct']}% of revenue.")
    print(f"  #1 customer:  {pareto['top_1_customer']} "
          f"({pareto['top_1_revenue_pct']}% of total)")

    print(f"\nTop 5 Industry Segments")
    for _, row in segments.head(5).iterrows():
        print(f"  {row['industry_segment_clean']:<25} "
              f"${row['revenue']:>12,.2f}  ({row['pct_of_total']}%)")

    print(f"\nTop 5 Regions")
    for _, row in regions.head(5).iterrows():
        print(f"  {row['region_clean']:<25} "
              f"${row['revenue']:>12,.2f}  ({row['pct_of_total']}%)")

    if weekly:
        print(f"\nWeekly Revenue")
        print(f"  Weeks covered:        {weekly['weeks_covered']}")
        print(f"  Avg/week:             ${weekly['avg_weekly_revenue']:,.2f}")
        print(f"  Best week:            ${weekly['best_week_revenue']:,.2f}")
        print(f"  Latest week:          ${weekly['latest_week_revenue']:,.2f}")
        if weekly.get("latest_wow_change") is not None:
            arrow = "▲" if weekly['latest_wow_change'] > 0 else "▼"
            print(f"  Latest WoW change:    {arrow} {abs(weekly['latest_wow_change']):.1f}%")


if __name__ == "__main__":
    run_analysis()
