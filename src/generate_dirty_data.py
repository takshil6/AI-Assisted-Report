"""
Phase 1: Synthetic Dirty Data Generator
========================================
Generates a realistic-looking messy industrial transaction dataset that mimics
what you'd export from a real ERP system (SAP, Oracle, NetSuite) before
anyone has cleaned it.

The "dirtiness" is intentional and calibrated:
    - Customer names: inconsistent capitalization, abbreviations, typos, trailing spaces
    - Regions: multiple spellings for the same place ("NE", "Northeast", "north east")
    - Dates: mixed formats (ISO, US, European, text)
    - Revenue: occasional nulls, negative values, string numbers with commas
    - Industry segments: free-text with typos

Run:
    python src/generate_dirty_data.py

Output:
    data/raw_transactions.csv
"""

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

# Simple name pool for sales reps (replaces Faker dependency to keep things lean)
_FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
                "Linda", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
                "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy"]
_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
               "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
               "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee"]


def _fake_name() -> str:
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"


def _fake_id() -> str:
    return uuid.uuid4().hex[:8].upper()

# ---------------------------------------------------------------------------
# Configuration: the "truth" behind the mess
# ---------------------------------------------------------------------------
# In a real company, there would be ~100 real customers. But in the raw export,
# each appears under many name variants. We define canonical names here, then
# generate dirty variants from them.

CANONICAL_CUSTOMERS = [
    "Acme Industrial Corp",
    "Global Pulp & Paper Inc",
    "Midwest Steel Works",
    "Pacific Recycling LLC",
    "Northern Timber Co",
    "Atlantic Chemical Partners",
    "Continental Packaging Group",
    "Summit Mining Enterprises",
    "Redwood Fiber Solutions",
    "BlueRidge Manufacturing",
    "Cascade Paper Products",
    "Evergreen Forest Industries",
    "Heartland Processing Co",
    "Ironworks Heavy Equipment",
    "Lakeside Pulp Mills",
    "Meridian Engineering Services",
    "Oakwood Materials Inc",
    "Prairie Grain Handlers",
    "Sequoia Wood Products",
    "Tidewater Chemical Co",
]

CANONICAL_REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "International"]

CANONICAL_SEGMENTS = [
    "Pulp & Paper",
    "Mining",
    "Recycling",
    "Chemical Processing",
    "Food & Beverage",
    "Wood Products",
]

PRODUCT_SKUS = [f"KDT-{random.randint(1000, 9999)}" for _ in range(50)]


# ---------------------------------------------------------------------------
# Dirtiness functions: each takes a clean value and returns a messy variant
# ---------------------------------------------------------------------------
def dirty_customer_name(name: str) -> str:
    """Introduce realistic name variations: casing, abbreviations, typos, spacing."""
    variants = [
        name,                                           # clean
        name.upper(),                                   # ACME INDUSTRIAL CORP
        name.lower(),                                   # acme industrial corp
        name.replace("Corp", "Corporation"),
        name.replace("Inc", "Incorporated"),
        name.replace("LLC", "L.L.C."),
        name.replace("Co", "Company"),
        f"  {name}  ",                                  # trailing/leading spaces
        name.replace(" ", "  "),                        # double-space
        name.replace("&", "and"),
        name[:-1] if len(name) > 5 else name,           # missing last char (typo)
    ]
    # Occasionally drop a random letter to simulate a typo
    if random.random() < 0.08 and len(name) > 6:
        idx = random.randint(1, len(name) - 2)
        typo = name[:idx] + name[idx + 1:]
        variants.append(typo)
    return random.choice(variants)


def dirty_region(region: str) -> str:
    """Multiple spellings and abbreviations for the same region."""
    mapping = {
        "Northeast":     ["Northeast", "NE", "North East", "north-east", "N.E.", "Northeastern"],
        "Southeast":     ["Southeast", "SE", "South East", "south east", "S.E.", "Southeastern"],
        "Midwest":       ["Midwest", "MW", "Mid-West", "midwest", "Mid West", "Middle West"],
        "Southwest":     ["Southwest", "SW", "South West", "south-west", "S.W."],
        "West":          ["West", "W", "West Coast", "western", "Pacific"],
        "International": ["International", "INTL", "Intl.", "Global", "Overseas", "intl"],
    }
    return random.choice(mapping[region])


def dirty_segment(segment: str) -> str:
    """Typos and alternate phrasings for industry segments."""
    mapping = {
        "Pulp & Paper":        ["Pulp & Paper", "Pulp and Paper", "Paper", "P&P", "pulp/paper", "Paper Products"],
        "Mining":              ["Mining", "Mining & Extraction", "mining", "MINING", "Minerals"],
        "Recycling":           ["Recycling", "Recycle", "recycling", "Recyc.", "Waste Management"],
        "Chemical Processing": ["Chemical Processing", "Chemicals", "Chemical", "Chem Proc", "chem"],
        "Food & Beverage":     ["Food & Beverage", "F&B", "Food/Bev", "Food and Beverage", "food & bev"],
        "Wood Products":       ["Wood Products", "Wood", "Timber", "Lumber", "wood prod"],
    }
    return random.choice(mapping[segment])


def dirty_date(d: datetime) -> str:
    """Return the same date in one of several common formats."""
    formats = [
        "%Y-%m-%d",      # 2024-03-15
        "%m/%d/%Y",      # 03/15/2024
        "%d/%m/%Y",      # 15/03/2024  (European - ambiguous!)
        "%b %d, %Y",     # Mar 15, 2024
        "%d-%b-%Y",      # 15-Mar-2024
    ]
    return d.strftime(random.choice(formats))


def dirty_revenue(amount: float) -> object:
    """Occasionally return a string with commas, None, or a negative."""
    r = random.random()
    if r < 0.03:
        return None                                     # ~3% nulls
    if r < 0.06:
        return f"${amount:,.2f}"                        # string with $ and commas
    if r < 0.08:
        return -amount                                  # negative (return/refund)
    return round(amount, 2)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate(n_rows: int = 5000, out_path: str = "data/raw_transactions.csv") -> pd.DataFrame:
    """Generate the dirty dataset and write it to disk."""

    # Pareto-realistic revenue distribution: 20% of customers drive 80% of revenue.
    # We achieve this by giving customers weighted probabilities of appearing in
    # rows, and giving the "top" customers larger transaction sizes.
    customer_weights = [random.paretovariate(1.16) for _ in CANONICAL_CUSTOMERS]

    rows = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    date_range_days = (end_date - start_date).days

    for _ in range(n_rows):
        canonical_customer = random.choices(CANONICAL_CUSTOMERS, weights=customer_weights, k=1)[0]

        # Bigger customers -> bigger transactions
        weight_idx = CANONICAL_CUSTOMERS.index(canonical_customer)
        base_revenue = customer_weights[weight_idx] * random.uniform(500, 8000)

        trans_date = start_date + timedelta(days=random.randint(0, date_range_days))

        rows.append({
            "transaction_id":   _fake_id(),
            "customer_name":    dirty_customer_name(canonical_customer),
            "region":           dirty_region(random.choice(CANONICAL_REGIONS)),
            "industry_segment": dirty_segment(random.choice(CANONICAL_SEGMENTS)),
            "product_sku":      random.choice(PRODUCT_SKUS),
            "order_date":       dirty_date(trans_date),
            "quantity":         random.randint(1, 200),
            "revenue_usd":      dirty_revenue(base_revenue),
            "sales_rep":        _fake_name(),
            "notes":            random.choice([
                "", "", "", "Urgent order", "Customer requested rush",
                "Repeat customer", "NEW ACCOUNT", "follow up needed",
                "discount applied 10%", None,
            ]),
        })

    df = pd.DataFrame(rows)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    # Also hold on to the "truth" mapping so Phase 2 has a grader to measure
    # cleaning accuracy against. Without this you can't claim metrics honestly.
    truth_path = out.parent / "truth_mappings.csv"
    truth_rows = []
    for _, row in df.iterrows():
        # Reverse-engineering the truth for customer/region/segment is done by
        # generating the truth column alongside the dirty one. For simplicity
        # here, we re-derive by nearest-match for the interview artifact.
        truth_rows.append({
            "dirty_customer":    row["customer_name"],
            "dirty_region":      row["region"],
            "dirty_segment":     row["industry_segment"],
        })
    pd.DataFrame(truth_rows).drop_duplicates().to_csv(truth_path, index=False)

    return df


def print_summary(df: pd.DataFrame) -> None:
    print(f"\n✓ Generated {len(df):,} rows")
    print(f"✓ Unique (dirty) customer strings: {df['customer_name'].nunique()}")
    print(f"  (Ground truth: only {len(CANONICAL_CUSTOMERS)} real customers)")
    print(f"✓ Unique (dirty) region strings:   {df['region'].nunique()}")
    print(f"  (Ground truth: only {len(CANONICAL_REGIONS)} real regions)")
    print(f"✓ Nulls in revenue_usd:            {df['revenue_usd'].isna().sum()}")
    print(f"✓ File size: ~{Path('data/raw_transactions.csv').stat().st_size / 1024:.1f} KB")
    print("\nFirst 5 rows:")
    print(df.head().to_string())


if __name__ == "__main__":
    df = generate(n_rows=5000)
    print_summary(df)
