"""
Phase 2: AI Cleaning Module (Groq-powered)
===========================================
Takes the messy output of Phase 1 and produces a cleaned dataset where:
    - Customer names are deduplicated to their canonical form
      ("ACME CORP", "Acme Corporation", "acme  corp" -> "Acme Industrial Corp")
    - Regions are standardized ("NE", "Northeast", "N.E." -> "Northeast")
    - Industry segments are normalized ("Chem", "Chemicals" -> "Chemical Processing")
    - Dates are parsed to ISO format
    - Revenue is coerced to float, nulls and strings handled

Why LLMs for this and not regex?
    Regex can handle capitalization and whitespace but collapses on typos,
    abbreviations, and semantic synonyms ("Mining" vs "Minerals"). An LLM
    handles the long tail of messiness that rules-based cleaners miss.

Rate-limit strategy for Groq free tier (30 RPM, 14,400 RPD on 8B model):
    - Batch up to 50 items per LLM call -> ~3 API calls for our 158 customers
    - Cache every result to disk in data/.cache/ so re-runs cost nothing
    - Sleep between batches to stay well under 30 RPM

Run:
    python src/cleaner.py

Output:
    data/clean_transactions.csv
    data/cleaning_report.json  (metrics for your resume bullets)
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can also come from the shell

# ---------------------------------------------------------------------------
# Groq client (lazy - only created when an LLM call is actually needed)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    """Lazily construct the Groq-compatible OpenAI client on first use."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Copy .env.example to .env and add your key "
            "from https://console.groq.com/keys"
        )

    from openai import OpenAI  # imported lazily so tests can run without it
    _client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    return _client


MODEL = "llama-3.1-8b-instant"       # 14,400 RPD on free tier; plenty smart for this
BATCH_SIZE = 50                      # items per LLM call
SLEEP_BETWEEN_BATCHES = 2.5          # seconds; keeps us under 30 RPM comfortably

CACHE_DIR = Path("data/.cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Canonical vocabularies
# ---------------------------------------------------------------------------
# We tell the LLM the "allowed" values for categorical fields. This is a
# critical pattern: without an allowed-list, the LLM will invent new
# categories and you'll still have a dirty column at the end.

CANONICAL_REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "International"]

CANONICAL_SEGMENTS = [
    "Pulp & Paper", "Mining", "Recycling",
    "Chemical Processing", "Food & Beverage", "Wood Products",
]


# ---------------------------------------------------------------------------
# Cache: avoid re-paying for the same LLM call twice
# ---------------------------------------------------------------------------
def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def _load_cache(name: str) -> dict:
    p = _cache_path(name)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _save_cache(name: str, data: dict) -> None:
    _cache_path(name).write_text(json.dumps(data, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Core LLM helper
# ---------------------------------------------------------------------------
def _llm_json(system: str, user: str, max_tokens: int = 2000) -> dict:
    """Call Groq, ask for JSON, parse and return it. Retries once on JSON error."""
    client = _get_client()
    for attempt in range(2):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,              # deterministic cleaning
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            if attempt == 0:
                continue
            raise RuntimeError(f"LLM returned non-JSON after retry: {content[:200]}")
    return {}


# ---------------------------------------------------------------------------
# Customer name cleaning (open-vocabulary)
# ---------------------------------------------------------------------------
def clean_customer_names(dirty_names: list[str]) -> dict[str, str]:
    """
    Map each dirty name to its canonical form. The LLM infers canonical names
    by clustering the input itself -- we don't hand it a list of valid names,
    because in the real world you don't always have one.
    """
    cache = _load_cache("customers")
    unique_dirty = sorted(set(n for n in dirty_names if isinstance(n, str) and n.strip()))
    to_process = [n for n in unique_dirty if n not in cache]

    if not to_process:
        print(f"  [customer] All {len(unique_dirty)} names already cached.")
        return cache

    print(f"  [customer] {len(to_process)} new names to clean "
          f"(cached: {len(unique_dirty) - len(to_process)})")

    system = (
        "You are a data-cleaning assistant. You receive a list of messy company "
        "names that may include typos, inconsistent capitalization, alternate "
        "abbreviations (Corp/Corporation, Inc/Incorporated, LLC/L.L.C.), extra "
        "whitespace, and the 'and'/'&' swap. Map each messy name to a single "
        "canonical company name. Names that refer to the same real company must "
        "map to IDENTICAL canonical strings. Return JSON with one key: "
        '"mapping", whose value is an object of {dirty_name: canonical_name}. '
        "Use title case, the '&' symbol (not 'and'), and 'Corp'/'Inc'/'LLC' "
        "(no dots) as the preferred short forms."
    )

    for i in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[i:i + BATCH_SIZE]
        print(f"  [customer] Batch {i // BATCH_SIZE + 1}: {len(batch)} names...")

        user = "Messy company names:\n" + "\n".join(f"- {n}" for n in batch)
        result = _llm_json(system, user, max_tokens=3000)
        mapping = result.get("mapping", {})

        for dirty in batch:
            cache[dirty] = mapping.get(dirty, dirty.strip().title())

        _save_cache("customers", cache)
        time.sleep(SLEEP_BETWEEN_BATCHES)

    return cache


# ---------------------------------------------------------------------------
# Region cleaning (closed-vocabulary -- faster, deterministic)
# ---------------------------------------------------------------------------
def clean_regions(dirty_regions: list[str]) -> dict[str, str]:
    """Map each dirty region to one of the canonical regions."""
    cache = _load_cache("regions")
    unique_dirty = sorted(set(r for r in dirty_regions if isinstance(r, str) and r.strip()))
    to_process = [r for r in unique_dirty if r not in cache]

    if not to_process:
        print(f"  [region] All {len(unique_dirty)} regions already cached.")
        return cache

    print(f"  [region] {len(to_process)} new regions to clean")

    system = (
        "You map messy region strings to a fixed vocabulary. Allowed values: "
        f"{CANONICAL_REGIONS}. Examples: 'NE' -> 'Northeast', 'S.W.' -> 'Southwest', "
        "'west coast' -> 'West', 'intl' -> 'International'. Return JSON with one "
        'key "mapping" whose value is an object of {dirty: canonical}. Every '
        "canonical value MUST be one of the allowed values -- no exceptions."
    )

    for i in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[i:i + BATCH_SIZE]
        user = "Messy regions:\n" + "\n".join(f"- {r}" for r in batch)
        result = _llm_json(system, user, max_tokens=1500)
        mapping = result.get("mapping", {})

        for dirty in batch:
            cleaned = mapping.get(dirty)
            # Safety check: if the LLM invented a new category, fall back
            if cleaned not in CANONICAL_REGIONS:
                cleaned = _fallback_match(dirty, CANONICAL_REGIONS)
            cache[dirty] = cleaned

        _save_cache("regions", cache)
        time.sleep(SLEEP_BETWEEN_BATCHES)

    return cache


def clean_segments(dirty_segments: list[str]) -> dict[str, str]:
    """Map each dirty industry segment to one of the canonical segments."""
    cache = _load_cache("segments")
    unique_dirty = sorted(set(s for s in dirty_segments if isinstance(s, str) and s.strip()))
    to_process = [s for s in unique_dirty if s not in cache]

    if not to_process:
        print(f"  [segment] All {len(unique_dirty)} segments already cached.")
        return cache

    print(f"  [segment] {len(to_process)} new segments to clean")

    system = (
        "You map messy industry-segment strings to a fixed vocabulary. Allowed "
        f"values: {CANONICAL_SEGMENTS}. Examples: 'chem' -> 'Chemical Processing', "
        "'F&B' -> 'Food & Beverage', 'Timber'/'Lumber'/'Wood' -> 'Wood Products'. "
        'Return JSON with one key "mapping" whose value is an object of '
        "{dirty: canonical}. Every canonical value MUST be one of the allowed values."
    )

    for i in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[i:i + BATCH_SIZE]
        user = "Messy segments:\n" + "\n".join(f"- {s}" for s in batch)
        result = _llm_json(system, user, max_tokens=1500)
        mapping = result.get("mapping", {})

        for dirty in batch:
            cleaned = mapping.get(dirty)
            if cleaned not in CANONICAL_SEGMENTS:
                cleaned = _fallback_match(dirty, CANONICAL_SEGMENTS)
            cache[dirty] = cleaned

        _save_cache("segments", cache)
        time.sleep(SLEEP_BETWEEN_BATCHES)

    return cache


def _fallback_match(dirty: str, allowed: list[str]) -> str:
    """Best-effort rescue if the LLM returns an invalid category."""
    dirty_lower = dirty.lower()
    for canonical in allowed:
        if canonical.lower() in dirty_lower or dirty_lower in canonical.lower():
            return canonical
    return allowed[0]  # last-resort default


# ---------------------------------------------------------------------------
# Deterministic cleaning (no LLM needed -- regex/pandas is faster and free)
# ---------------------------------------------------------------------------
def clean_dates(series: pd.Series) -> pd.Series:
    """Parse the zoo of date formats into real datetimes."""
    # pandas' to_datetime with format='mixed' is remarkably good at this
    return pd.to_datetime(series, format="mixed", errors="coerce")


def clean_revenue(value) -> Optional[float]:
    """Coerce string revenues like '$1,234.56' or NaN to float."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def clean_pipeline(
    input_path: str = "data/raw_transactions.csv",
    output_path: str = "data/clean_transactions.csv",
    report_path: str = "data/cleaning_report.json",
) -> dict:
    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path)
    print(f"  {len(df):,} rows, {df.shape[1]} columns\n")

    # --- Before metrics (for the report) ---
    before = {
        "rows": len(df),
        "unique_customers": df["customer_name"].nunique(),
        "unique_regions":   df["region"].nunique(),
        "unique_segments":  df["industry_segment"].nunique(),
        "null_revenues":    int(df["revenue_usd"].isna().sum()),
    }

    # --- AI cleaning ---
    print("Cleaning customer names via Groq...")
    cust_map = clean_customer_names(df["customer_name"].dropna().tolist())
    df["customer_name_clean"] = df["customer_name"].map(cust_map).fillna(df["customer_name"])

    print("\nCleaning regions via Groq...")
    region_map = clean_regions(df["region"].dropna().tolist())
    df["region_clean"] = df["region"].map(region_map).fillna(df["region"])

    print("\nCleaning industry segments via Groq...")
    segment_map = clean_segments(df["industry_segment"].dropna().tolist())
    df["industry_segment_clean"] = df["industry_segment"].map(segment_map).fillna(df["industry_segment"])

    # --- Deterministic cleaning ---
    print("\nParsing dates and revenue (deterministic)...")
    df["order_date_clean"] = clean_dates(df["order_date"])
    df["revenue_usd_clean"] = df["revenue_usd"].apply(clean_revenue)

    # --- After metrics ---
    after = {
        "unique_customers": df["customer_name_clean"].nunique(),
        "unique_regions":   df["region_clean"].nunique(),
        "unique_segments":  df["industry_segment_clean"].nunique(),
        "null_revenues":    int(df["revenue_usd_clean"].isna().sum()),
        "unparseable_dates": int(df["order_date_clean"].isna().sum()),
    }

    # --- Report ---
    report = {
        "before": before,
        "after": after,
        "reductions": {
            "customers_pct": round(100 * (1 - after["unique_customers"] / before["unique_customers"]), 1),
            "regions_pct":   round(100 * (1 - after["unique_regions"]   / before["unique_regions"]),   1),
            "segments_pct":  round(100 * (1 - after["unique_segments"]  / before["unique_segments"]),  1),
        },
        "model": MODEL,
        "rows_processed": len(df),
    }

    Path(report_path).write_text(json.dumps(report, indent=2))
    df.to_csv(output_path, index=False)

    # --- Pretty print ---
    print("\n" + "=" * 60)
    print("CLEANING REPORT")
    print("=" * 60)
    print(f"{'Metric':<25} {'Before':>10} {'After':>10} {'Reduction':>12}")
    print("-" * 60)
    for key, pct_key in [
        ("Unique customers", "customers_pct"),
        ("Unique regions",   "regions_pct"),
        ("Unique segments",  "segments_pct"),
    ]:
        metric = key.split()[1]
        b = before[f"unique_{metric}"]
        a = after[f"unique_{metric}"]
        print(f"{key:<25} {b:>10} {a:>10} {report['reductions'][pct_key]:>11}%")
    print("-" * 60)
    print(f"Saved cleaned data ->  {output_path}")
    print(f"Saved report       ->  {report_path}")

    return report


if __name__ == "__main__":
    clean_pipeline()
