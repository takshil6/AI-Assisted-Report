"""
Phase 1 verification: run this BEFORE setting up Phase 2 to confirm
your dirty dataset looks right. Catches problems early so you don't
waste Groq API calls on a broken input.

Run:
    python tests/verify_phase1.py
"""

import sys
from pathlib import Path

import pandas as pd

CSV_PATH = Path("data/raw_transactions.csv")

EXPECTED_COLUMNS = {
    "transaction_id", "customer_name", "region", "industry_segment",
    "product_sku", "order_date", "quantity", "revenue_usd",
    "sales_rep", "notes",
}


def check(condition: bool, label: str, detail: str = "") -> bool:
    mark = "✓" if condition else "✗"
    print(f"  {mark} {label}" + (f"  ({detail})" if detail else ""))
    return condition


def main() -> int:
    print(f"\nVerifying {CSV_PATH}...\n")

    if not CSV_PATH.exists():
        print(f"  ✗ File not found: {CSV_PATH}")
        print("    Run:  python src/generate_dirty_data.py")
        return 1

    df = pd.read_csv(CSV_PATH)
    all_passed = True

    # Row count
    all_passed &= check(
        len(df) == 5000,
        "Row count is 5000",
        f"got {len(df):,}",
    )

    # Columns present
    missing = EXPECTED_COLUMNS - set(df.columns)
    all_passed &= check(
        not missing,
        "All 10 expected columns present",
        f"missing: {missing}" if missing else "",
    )

    # Customer dirtiness: unique count should be much larger than 20
    n_customers = df["customer_name"].nunique()
    all_passed &= check(
        n_customers > 50,
        "Customer names are messy (>50 unique variants)",
        f"{n_customers} unique strings (clean truth: 20)",
    )

    # Region dirtiness
    n_regions = df["region"].nunique()
    all_passed &= check(
        n_regions > 15,
        "Region strings are messy (>15 unique variants)",
        f"{n_regions} unique strings (clean truth: 6)",
    )

    # Some revenue nulls exist (proves the dirtying logic ran)
    n_nulls = int(df["revenue_usd"].isna().sum())
    all_passed &= check(
        50 <= n_nulls <= 400,
        "Revenue has realistic null rate",
        f"{n_nulls} nulls (~3-8% expected)",
    )

    # Date format variety: at least 3 distinct character-pattern lengths
    date_len_variety = df["order_date"].dropna().astype(str).str.len().nunique()
    all_passed &= check(
        date_len_variety >= 3,
        "Date column has mixed formats",
        f"{date_len_variety} different length patterns",
    )

    # Revenue column has string entries somewhere (the $1,234.56 dirtying)
    has_string_revenue = df["revenue_usd"].apply(
        lambda v: isinstance(v, str) and "$" in v
    ).any()
    all_passed &= check(
        has_string_revenue,
        "Some revenue values are strings with $ (dirtying worked)",
    )

    print()
    if all_passed:
        print("✓ Phase 1 output looks healthy. You're ready for Phase 2.\n")
        return 0
    else:
        print("✗ Something looks off. Try regenerating:")
        print("    python src/generate_dirty_data.py\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
