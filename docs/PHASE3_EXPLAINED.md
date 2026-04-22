# Understanding Phase 3 — The 80/20 Analysis Engine

This document explains what Phase 3 does, why each piece matters, and what you'll see when you run it. Read alongside `src/analyzer.py`.

---

## Part 1: What Phase 3 Is For

### The business problem

Kadant's job description is about **the 80/20 program**. That's short for the **Pareto principle**: in most businesses, roughly 80% of revenue comes from roughly 20% of customers. The business implication is simple but powerful — if you can identify *which* 20%, you can treat them better (faster delivery, dedicated support, volume discounts) and stop wasting time on low-value customers.

Phase 3 is the module that **finds those 20%**.

### What goes in, what comes out

**Input:** `data/clean_transactions.csv` (output from Phase 2)

**Outputs:**

| File | What it contains |
|---|---|
| `data/customer_pareto.csv` | Every customer, ranked, with cumulative % and a flag for who's in the 80/20 tier |
| `data/segment_breakdown.csv` | Revenue by industry segment |
| `data/region_breakdown.csv` | Revenue by geographic region |
| `data/weekly_revenue.csv` | Revenue per week with week-over-week changes |
| `data/analysis_results.json` | All headline metrics assembled in one file (this is what Phase 4's reporter will consume) |

### No AI, no API calls, no network

Phase 3 is 100% pandas. The AI work happened in Phase 2 — once customer names were standardized, the analysis is pure arithmetic. This is important because:

- **Deterministic results** — the same input always produces the same output, no LLM randomness
- **Fast** — runs in under a second on 5,000 rows
- **Free** — no API quota consumed, works offline
- **Testable** — we can write unit tests with hand-verified answers (see `tests/test_analyzer_offline.py`)

**General principle:** Use AI where judgment is needed (Phase 2). Use deterministic code where the answer is mathematical (Phase 3). Don't mix them up.

---

## Part 2: Walking Through `analyzer.py`

### 2.1 Loading and validation

```python
def load_clean_data(path):
    df = pd.read_csv(p, parse_dates=["order_date_clean"])
    required = {"customer_name_clean", "region_clean", ...}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(...)
```

**What this does:** Reads the cleaned CSV and makes sure the columns we expect actually exist. If Phase 2 didn't run (or ran with a bug), we fail loudly with a helpful message rather than producing wrong results silently.

**Why it matters:** "Fail fast with a good error message" is the difference between a 30-second fix and an hour of debugging.

```python
    null_count = int(df["revenue_usd_clean"].isna().sum())
    df = df.dropna(subset=["revenue_usd_clean"]).copy()
    
    neg_count = int((df["revenue_usd_clean"] < 0).sum())
    df = df[df["revenue_usd_clean"] >= 0].copy()
```

**What this does:** Drops rows where revenue is null or negative. Prints how many were dropped so you can see what got excluded.

**The important judgment call:** Should refunds (negative revenue) be included or excluded?
- **Include them:** You get "net revenue" — what the company actually kept
- **Exclude them:** You get "gross sales" — what customers ordered

We exclude them for the Pareto analysis because negative rows distort the cumulative revenue curve. **A real production system would expose this as a configuration flag** so the user can choose. We note this explicitly to the user with a printed message, so nothing is hidden.

### 2.2 Customer Pareto — the heart of 80/20

```python
def customer_pareto(df, threshold=0.80):
    agg = (
        df.groupby("customer_name_clean", as_index=False)
          .agg(revenue=("revenue_usd_clean", "sum"),
               transactions=("transaction_id", "count"),
               avg_order_value=("revenue_usd_clean", "mean"))
          .sort_values("revenue", ascending=False)
          .reset_index(drop=True)
    )
```

**What this does:** For every unique (clean) customer name:
- Sum their total revenue
- Count their transactions
- Compute their average order value

Then sort them from highest revenue to lowest.

**pandas walkthrough:**
- `groupby("customer_name_clean")` — group rows that share the same customer
- `.agg(revenue=("revenue_usd_clean", "sum"), ...)` — compute aggregates per group
- `sort_values("revenue", ascending=False)` — biggest customers first
- `reset_index(drop=True)` — renumber rows 0,1,2... after sorting

```python
    total = agg["revenue"].sum()
    agg["rank"] = agg.index + 1
    agg["pct_of_total"] = agg["revenue"] / total
    agg["cumulative_pct"] = agg["pct_of_total"].cumsum()
```

**What this does:** Adds three columns:
- **`rank`** — 1 for the biggest customer, 2 for the second, etc.
- **`pct_of_total`** — that customer's share of total revenue (e.g., 0.23 = 23%)
- **`cumulative_pct`** — the running sum. First customer has their own %, second customer has their + the first customer's %, etc.

**The cumulative column is the magic.** It answers "if I take the top N customers, what % of revenue do they represent?" When cumulative_pct first reaches 80%, you've found your 80/20 tier.

```python
    agg["is_pareto_80"] = False
    for idx, row in agg.iterrows():
        agg.at[idx, "is_pareto_80"] = True
        if row["cumulative_pct"] >= threshold and not crossed:
            crossed = True
            agg.loc[idx + 1:, "is_pareto_80"] = False
            break
```

**What this does:** Walks down the sorted list, flagging each customer as "in the 80/20 tier" until the cumulative crosses 80%. The customer who *crosses* the threshold is included (not excluded). Everyone below is flagged False.

**Why this matters for interview storytelling:** Different companies define "the 80/20 tier" differently. Some take the smallest N whose cumulative is ≥80%. Some take the largest N whose cumulative is ≤80%. We took the first approach — it's the more conservative, more inclusive tier. **Being able to explain this choice is the difference between a senior and a junior analyst.**

### 2.3 Segment and region breakdowns — a shared helper

```python
def _dimension_breakdown(df, dimension_col):
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
    return out


def segment_breakdown(df):
    return _dimension_breakdown(df, "industry_segment_clean")


def region_breakdown(df):
    return _dimension_breakdown(df, "region_clean")
```

**What this does:** Since segment and region breakdowns are the same operation on different columns, we wrote the logic once in `_dimension_breakdown` and reuse it. This is called the **DRY principle** (Don't Repeat Yourself). In a real production codebase this pattern saves hundreds of lines.

**What `unique_customers` measures:** How many distinct customers operate in that segment/region. A segment with 10 unique customers is healthier and less risky than one dominated by 1 customer — even if the total revenue is the same. This is a signal a business analyst looks for.

### 2.4 Weekly revenue time series

```python
def weekly_revenue(df):
    weekly = (
        df.set_index("order_date_clean")
          .resample("W")["revenue_usd_clean"]
          .agg(["sum", "count"])
          .rename(columns={"sum": "revenue", "count": "transactions"})
          .reset_index()
    )
    weekly["wow_change_pct"] = (weekly["revenue"].pct_change() * 100).round(2)
    return weekly
```

**pandas walkthrough:**
- `set_index("order_date_clean")` — use the date column as the row index so we can do date-based operations
- `resample("W")` — group by week ("W" = week ending Sunday). You could also use "M" for monthly, "D" for daily, "Q" for quarterly.
- `.agg(["sum", "count"])` — for each week, compute the sum (revenue) and count (number of transactions)
- `pct_change()` — the change from one row to the next, as a decimal. The first row is always NaN because there's no prior row to compare to.

**Why weekly and not monthly?** Because the job description specifically says "weekly business analytics summaries." That's where this design decision came from — always match the grain of your analysis to what the stakeholder actually asked for.

### 2.5 The orchestrator

```python
def run_analysis(input_path, output_json):
    df = load_clean_data(input_path)
    pareto = customer_pareto(df)
    pareto.to_csv("data/customer_pareto.csv", index=False)
    p_summary = pareto_summary(pareto)
    
    segments = segment_breakdown(df)
    ... (and so on)
    
    results = {
        "dataset_summary":  dataset_summary,
        "pareto_summary":   p_summary,
        "weekly_summary":   w_summary,
        "top_customers":    pareto.head(20).to_dict(orient="records"),
        "segment_breakdown": segments.to_dict(orient="records"),
        "region_breakdown":  regions.to_dict(orient="records"),
    }
    Path(output_json).write_text(json.dumps(results, indent=2, default=str))
```

**What this does:** Runs every analysis function, saves each result as a CSV (for spreadsheet review), and assembles a master JSON with all the headline numbers.

**Why both CSV and JSON?**
- **CSVs** — for humans to open in Excel and sanity-check
- **JSON** — for Phase 4 (the reporter) to consume programmatically. Much easier to drop structured data into a report template than to re-parse CSVs.

**`to_dict(orient="records")` explained:** Converts a DataFrame to a list of dicts, one per row:
```python
# DataFrame:         [A, 100]
#                    [B, 50]
# becomes:           [{"customer": "A", "revenue": 100},
#                     {"customer": "B", "revenue": 50}]
```
This is the format that JSON loves and Jinja2 templates (used in Phase 4) can iterate over cleanly.

---

## Part 3: What Your Output Will Look Like

With your Phase 2 cleaning (23 customers), you'll see output roughly like this:

```
Dataset
  Date range:         2024-01-01  ->  2024-12-31
  Total revenue:      $ 358,000,000
  Transactions:                  4,713
  Unique customers:                 23

80/20 Pareto
  Top 2 of 23 customers (8.7%) drive 85% of revenue.
  #1 customer:  Global Pulp & Paper Inc (~77% of total)

Top 5 Industry Segments
  Pulp & Paper              $63M  (17.67%)
  Mining                    $62M  (17.44%)
  ...

Weekly Revenue
  Weeks covered:        53
  Avg/week:             $6.7M
```

**These aren't made-up numbers** — they come from the Pareto distribution we built into Phase 1's generator. When the generator gave some customers much higher "weights," those customers also got bigger transactions — so they naturally dominate revenue in the analysis.

**Very concentrated Pareto is a feature, not a bug.** Real industrial B2B businesses often have a top customer that does 20-40% of revenue. 77% is more extreme than real-life but demonstrates the concept clearly. In your writeup you can say: *"The synthetic data was generated with an intentionally strong Pareto concentration to validate the pipeline. Real industrial data typically shows 60-80% revenue from the top 20% of customers, which the pipeline identifies correctly."*

---

## Part 4: Checklist to Complete Phase 3

Before moving to Phase 4, confirm:

1. ☐ `data/clean_transactions.csv` exists (from Phase 2)
2. ☐ `python tests/test_analyzer_offline.py` shows **6 green checkmarks**
3. ☐ `python src/analyzer.py` runs end-to-end without errors
4. ☐ The terminal output shows your actual numbers (total revenue, Pareto %, top customer)
5. ☐ The following files exist in `data/`:
   - `analysis_results.json`
   - `customer_pareto.csv`
   - `segment_breakdown.csv`
   - `region_breakdown.csv`
   - `weekly_revenue.csv`
6. ☐ You've opened `customer_pareto.csv` in Excel and seen the `is_pareto_80` column marking the top customers
7. ☐ You've committed and pushed to GitHub

---

## Part 5: Glossary — New Terms

**Aggregation** — Collapsing many rows into fewer rows by computing sums, means, counts. "Group rows by customer, sum their revenue" is an aggregation.

**Cumulative sum / running total** — A column where each row is the sum of all rows before it plus itself. Used to measure concentration.

**DRY (Don't Repeat Yourself)** — A coding principle: if you write the same logic twice, extract it to a function. Keeps code maintainable.

**Groupby** — pandas operation that groups rows sharing some value (like customer name), so you can aggregate per group.

**Pareto distribution** — A skewed distribution where a few items dominate. Source of the 80/20 rule.

**Resample** — pandas operation that re-bins time-series data into regular intervals (daily, weekly, monthly).

**Time series** — Data indexed by date/time. Revenue per week is a time series.

---

## Part 6: Interview-Ready Talking Points

When you demo this project, be ready to answer:

- **"How does your 80/20 analysis work?"** → "I rank customers by revenue, compute cumulative percentage, and flag the smallest set whose cumulative reaches 80%."
- **"Why pandas and not SQL?"** → "For a 5,000-row dataset, pandas is faster to iterate on and easier to test. For 500 million rows I'd push the aggregation into SQL."
- **"What about refunds?"** → "I exclude negative-revenue rows from the Pareto to avoid distorting the cumulative curve, but I log the count so it's visible. In production I'd expose this as a flag."
- **"What's the weakness of your current analysis?"** → "It's a single snapshot. A production version would compare periods — this quarter vs. last quarter — and flag customers trending up or down."

Specific answers to specific questions. That's what senior engineers value.
