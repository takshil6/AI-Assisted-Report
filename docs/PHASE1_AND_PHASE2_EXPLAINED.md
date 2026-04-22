# Understanding Phase 1 & Phase 2 — A Detailed Walkthrough

This document explains everything the project does so far. Read it front-to-back; by the end you'll understand not just *what* each file does, but *why* it was built that way. You can rewrite any of this into your own notes.

---

## Part 1: The Big Picture

### What is a "data pipeline"?

A **data pipeline** is just a series of steps that take raw, messy data from one place, transform it into clean and useful data, and deliver it somewhere else. Think of it like a car factory assembly line:

- **Station 1:** Raw metal comes in
- **Station 2:** It gets cut and shaped
- **Station 3:** It gets painted
- **Station 4:** The finished part goes out

Our pipeline works the same way:

- **Phase 1:** Raw messy data comes in (simulated industrial transactions)
- **Phase 2:** AI cleans and standardizes it
- **Phase 3 (later):** Analysis runs on the clean data
- **Phase 4 (later):** A report is generated
- **Phase 5 (later):** The report gets delivered to SharePoint
- **Phase 6 (later):** Users can ask questions in plain English

Each phase produces a **file on disk** that the next phase reads. This is important: every phase can be tested independently, and you can re-run any phase without redoing the ones before it.

### Why are we simulating data instead of using real data?

Three reasons:

1. **No real company will give you their transaction data.** Real industrial transaction data is proprietary and confidential. Kadant is not going to email you their sales records so you can practice.
2. **We need data that looks realistic but is controlled.** To prove the AI cleaner works, we need to *know* how dirty the data is going in, so we can measure how clean it is coming out. With real data, you can never measure cleaning accuracy.
3. **The messiness is the interesting part.** Any intern can analyze clean data. The job description specifically asks for "collecting, cleaning, and analyzing large structured and unstructured datasets" — the cleaning is where AI adds value.

---

## Part 2: Phase 1 — The Synthetic Dirty Data Generator

### Goal of Phase 1

Produce a CSV file (`data/raw_transactions.csv`) with 5,000 rows that looks like what you'd export from a real industrial company's ERP system (Enterprise Resource Planning software — think SAP or Oracle) before anyone has cleaned it.

### Files Involved in Phase 1

| File | Role |
|---|---|
| `src/generate_dirty_data.py` | The script that generates the data |
| `data/raw_transactions.csv` | **Output** — the messy dataset (5,000 rows) |
| `data/truth_mappings.csv` | A companion file recording which dirty strings came from which true customer — useful later to grade the AI |

### The Dataset Columns

When the script runs, it produces 10 columns:

| Column | What it is | How it's made dirty |
|---|---|---|
| `transaction_id` | Unique 8-character ID for each row | Always clean |
| `customer_name` | The customer company's name | Randomized capitalization, abbreviations (Corp ↔ Corporation), extra spaces, occasional typos |
| `region` | Geographic sales region | Multiple spellings ("NE", "Northeast", "N.E.", "northeastern") |
| `industry_segment` | What industry the customer is in | Typos and alternate phrasings ("Chem", "Chemicals", "Chemical Processing") |
| `product_sku` | Product code like "KDT-4582" | Always clean |
| `order_date` | Date of the transaction | **Multiple date formats** — ISO, US, European, text |
| `quantity` | Number of units ordered | Always clean |
| `revenue_usd` | Dollar amount | Occasionally null, occasionally a string with `$` and commas, occasionally negative |
| `sales_rep` | Name of the salesperson | Always clean |
| `notes` | Free-text comments | Mixed casing, occasional nulls, empty strings |

### Walking Through `generate_dirty_data.py`

Let me explain the script in the order it executes, not the order it's written.

#### 1. Set up random seeds

```python
random.seed(42)
```

**What this does:** Tells Python's random number generator to always produce the *same* sequence of "random" numbers when the script runs. 

**Why this matters:** Without a seed, you'd get a completely different dataset every time you ran the script. With a seed, the output is reproducible — you and I and a recruiter can all run the script and get the exact same CSV. This is a non-negotiable best practice for any data work.

#### 2. Define the "truth"

```python
CANONICAL_CUSTOMERS = [
    "Acme Industrial Corp",
    "Global Pulp & Paper Inc",
    ...20 total...
]

CANONICAL_REGIONS = ["Northeast", "Southeast", ...]

CANONICAL_SEGMENTS = ["Pulp & Paper", "Mining", ...]
```

**What this does:** Lists the real, clean version of each customer, region, and industry segment. There are 20 real customers, 6 real regions, 6 real industry segments.

**Why this matters:** These lists are the ground truth. The whole point of the dirty-data generator is to produce *variants* of these clean values. When Phase 2 cleans the data, a successful run will collapse all the variants back to these 20 / 6 / 6 values.

#### 3. The "dirtiness functions"

These are helper functions that take a clean value and return a messy version. There's one for each type of field.

**`dirty_customer_name(name)`** — Takes "Acme Industrial Corp" and randomly returns one of:
- `"Acme Industrial Corp"` (clean, no change)
- `"ACME INDUSTRIAL CORP"` (all uppercase)
- `"acme industrial corp"` (all lowercase)
- `"Acme Industrial Corporation"` (Corp expanded)
- `"  Acme Industrial Corp  "` (extra spaces)
- `"Acme  Industrial  Corp"` (double spaces between words)
- `"Acme Industrial Cor"` (missing last letter — a typo)

**Why this design:** These are the actual kinds of mistakes that happen in real data. Sales reps enter the same customer differently across orders. Systems export names with inconsistent formatting. Automated OCR introduces typos. By including all of these, we make the test realistic.

**`dirty_region(region)`** — Maps one clean region to many variants using a dictionary:

```python
mapping = {
    "Northeast": ["Northeast", "NE", "North East", "north-east", "N.E.", "Northeastern"],
    ...
}
return random.choice(mapping[region])
```

**Why a dictionary here but not for customers?** Because regions have a **closed vocabulary** — only 6 possible real values. For customers, we can generate variants algorithmically because the patterns (uppercase, abbreviations, typos) apply to any company name. For regions, we hand-curate each variant list because there's no general pattern — "NE" is a specific cultural abbreviation, not something you'd derive from "Northeast" by rule.

**`dirty_date(d)`** — Takes a real `datetime` object and formats it in one of 5 random formats:
- `"2024-03-15"` (ISO)
- `"03/15/2024"` (US)
- `"15/03/2024"` (European — ambiguous with US!)
- `"Mar 15, 2024"` (written out)
- `"15-Mar-2024"` (mixed)

**Why this is tricky:** Notice that `03/15/2024` and `15/03/2024` are visually identical formats (two numbers separated by slashes), but one is month-first and the other is day-first. In Phase 2, pandas' date parser handles this well most of the time — but sometimes it guesses wrong. This is a genuinely hard real-world problem.

**`dirty_revenue(amount)`** — With small probabilities, returns something unexpected:
- 3% of the time: `None` (null value — field was blank in the source system)
- 3% of the time: `"$1,234.56"` (a string with dollar sign and comma — not a number)
- 2% of the time: a negative number (a refund or return)
- 92% of the time: the normal float value

**Why this design:** Real data has all three issues. Nulls happen when fields aren't filled in. String revenues happen when the export included currency formatting. Negative revenues happen when refunds are recorded as transactions. Your Phase 2 cleaner needs to handle all three without crashing.

#### 4. The main generator function

```python
def generate(n_rows=5000, out_path="data/raw_transactions.csv"):
    customer_weights = [random.paretovariate(1.16) for _ in CANONICAL_CUSTOMERS]
    ...
```

**What `random.paretovariate(1.16)` does:** This generates numbers that follow a **Pareto distribution** — a skewed distribution where a small number of values are very large and most values are small. The `1.16` shape parameter is specifically chosen to produce the famous **80/20 rule**: roughly 20% of values will account for 80% of the total.

**Why this matters for the 80/20 job:** The job title is "80/20 Data Analytics" because Kadant's business philosophy is the Pareto principle — focus on the top 20% of customers. By building this into our synthetic data, we guarantee that when Phase 3 runs the 80/20 analysis, it will find a real, meaningful pattern. If we generated data with uniform revenue across customers, the 80/20 analysis would show nothing interesting.

```python
    for _ in range(n_rows):
        canonical_customer = random.choices(CANONICAL_CUSTOMERS, weights=customer_weights, k=1)[0]
        
        weight_idx = CANONICAL_CUSTOMERS.index(canonical_customer)
        base_revenue = customer_weights[weight_idx] * random.uniform(500, 8000)
```

**What this does:** For each of the 5,000 rows:
1. Pick a customer, but customers with high Pareto weights get picked more often (so top customers have more transactions)
2. Compute a base revenue that is larger for higher-weighted customers (so top customers have bigger transactions too)

**The compounding effect:** High-weight customers both transact more often AND transact in larger amounts, which drives a strong Pareto effect in the total revenue.

#### 5. Write the CSV

```python
df = pd.DataFrame(rows)
df.to_csv(out_path, index=False)
```

Takes the list of dictionaries and turns it into a pandas DataFrame (a table in memory), then writes it to a CSV file.

### What Phase 1 Produces

After running `python src/generate_dirty_data.py`, you should see:

```
✓ Generated 5,000 rows
✓ Unique (dirty) customer strings: 158
  (Ground truth: only 20 real customers)
✓ Unique (dirty) region strings:   34
  (Ground truth: only 6 real regions)
✓ Nulls in revenue_usd:            185
```

**What these numbers mean:**
- **158 unique customer strings** — our 20 real customers appear under 158 different spellings in the raw data. This is the "dirtiness" Phase 2 must clean.
- **34 unique region strings** — our 6 real regions appear under 34 variants.
- **185 nulls in revenue** — roughly 3.7% of rows have missing revenue values.

These numbers are approximately what you'll see. They won't be exactly these numbers because the random seed mixes all the functions together — but they'll be in the same ballpark.

### Checklist for Completing Phase 1

Before you move to Phase 2, make sure:

1. ☐ You've installed Python 3.11 or later on your machine
2. ☐ You've created a virtual environment (`python -m venv .venv`)
3. ☐ You've activated the virtual environment (`source .venv/bin/activate` on Mac/Linux, or `.venv\Scripts\activate` on Windows)
4. ☐ You've installed pandas (`pip install pandas`)
5. ☐ You've run `python src/generate_dirty_data.py` successfully
6. ☐ The file `data/raw_transactions.csv` exists and has ~5,001 lines (5,000 data rows + 1 header)
7. ☐ You've opened the CSV in Excel or VS Code and actually **looked** at the dirtiness — you can see "Acme Industrial Corp" alongside "ACME INDUSTRIAL CORP" and other variants
8. ☐ You've initialized a git repo and pushed to GitHub

---

## Part 3: Phase 2 — The AI Cleaning Module

### Goal of Phase 2

Take the messy CSV from Phase 1 and produce a cleaned CSV (`data/clean_transactions.csv`) where:
- All spelling variants of each customer collapse to a single canonical name
- All region abbreviations collapse to one of 6 standard regions
- All industry segment variants collapse to one of 6 standard segments
- All date formats parse to real `datetime` objects
- All revenue values become proper floats (nulls stay null, strings like `"$1,234"` become `1234.00`)

### Files Involved in Phase 2

| File | Role |
|---|---|
| `src/cleaner.py` | The main cleaning script |
| `tests/test_cleaner_offline.py` | Tests for the deterministic parts (no API needed) |
| `.env` | Your private Groq API key (never committed to git) |
| `data/.cache/customers.json` | Cache of every customer name the AI has already cleaned |
| `data/.cache/regions.json` | Cache of every region the AI has already cleaned |
| `data/.cache/segments.json` | Cache of every segment the AI has already cleaned |
| `data/clean_transactions.csv` | **Output** — the cleaned dataset |
| `data/cleaning_report.json` | **Output** — metrics showing before/after |

### Key Concept: Two Kinds of Cleaning

Phase 2 uses two different techniques:

**1. Deterministic cleaning** (no AI needed) — for things that can be solved with rules:
- Date parsing → pandas' `to_datetime` with `format='mixed'` handles this
- Revenue coercion → strip `$` and `,`, then convert to float
- Null handling → pandas built-in

**2. AI cleaning** (LLM required) — for things that need judgment:
- Customer name deduplication (needs to understand that "Acme Industrial Cor" is a typo of "Acme Industrial Corp")
- Region standardization (needs to know that "NE" and "N.E." and "Northeastern" all mean "Northeast")
- Segment normalization (needs to understand that "Timber" and "Lumber" both fall under "Wood Products")

**Why not use AI for everything?** Because dates and currency can be solved reliably with code. Using an LLM for them would be slower, cost money, and occasionally make mistakes on trivial cases. **Use AI only for problems that genuinely need it.**

**Why not use regex for everything?** Because regex can handle formatting differences (spacing, capitalization) but falls apart on semantic equivalence. A regex can't tell you that "Timber" and "Wood Products" are the same thing.

### Walking Through `cleaner.py`

#### 1. Setting up the Groq client

```python
def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    ...
    from openai import OpenAI
    _client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    return _client
```

**What this does:** Creates an API client that talks to Groq, but does so **lazily** — only when actually needed. If you just import the cleaner module for testing, no client is built, and no API key is required.

**Why the OpenAI SDK?** Groq implemented an **OpenAI-compatible API**. That means Groq's endpoints accept the exact same requests that OpenAI's do — they just live at a different URL (`api.groq.com/openai/v1` instead of `api.openai.com/v1`). So we use OpenAI's Python library but point it at Groq's URL. This is a common pattern and saves everyone from writing provider-specific code.

#### 2. The core LLM call

```python
def _llm_json(system, user, max_tokens=2000):
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
```

**Line by line:**

- `model=MODEL` — which LLM to use. We picked `llama-3.1-8b-instant`. The "8b" means 8 billion parameters; the "instant" means it's tuned for speed. Groq's free tier allows 14,400 requests per day on this model, vs. 1,000 for the 70B model.

- `messages=[{system}, {user}]` — an LLM conversation is a list of messages. The "system" message tells the AI *how* to behave (its instructions). The "user" message is the actual input. This two-part structure lets you reuse the same instructions across many inputs.

- `temperature=0` — controls randomness. At 0, the model gives the most likely answer every time. At 1, it's more creative but less predictable. For data cleaning, **we want deterministic output** — running the script twice should give identical results. Always use `temperature=0` for structured tasks.

- `response_format={"type": "json_object"}` — forces the model to output valid JSON. Without this, the model might return "Here's your mapping: {...}" and crash our JSON parser. With it, we're guaranteed parseable output.

- `max_tokens=2000` — cap on how long the response can be. Important because Groq counts tokens against your rate limit. 2000 tokens is plenty for 50 mappings.

#### 3. The caching pattern

```python
def clean_customer_names(dirty_names):
    cache = _load_cache("customers")
    unique_dirty = sorted(set(...))
    to_process = [n for n in unique_dirty if n not in cache]
    
    if not to_process:
        print(f"  [customer] All {len(unique_dirty)} names already cached.")
        return cache
    
    ...process only the new ones...
    _save_cache("customers", cache)
```

**What this does:**
1. Load whatever we've cleaned before from `data/.cache/customers.json`
2. Find only the names we *haven't* seen before
3. Send those to the LLM in batches
4. Save the updated cache back to disk

**Why this matters:** The first time you run the cleaner, it processes 158 names via the API. The second time you run it — even if the dataset hasn't changed — it processes **zero** names. All 158 are in the cache.

**This is huge** because:
- Interview demos don't fail due to rate limits
- You can iterate on later phases (analyzer, reporter) without re-cleaning every time
- If Groq goes down, the cached data still works
- You save on API quota for actual new work

**Why JSON for the cache?** Because it's human-readable. You can open `data/.cache/customers.json` in any text editor and literally see what the AI decided for each name. If you disagree with a mapping, you can edit the JSON directly.

#### 4. Batching

```python
for i in range(0, len(to_process), BATCH_SIZE):
    batch = to_process[i:i + BATCH_SIZE]
    ...one API call per batch...
    time.sleep(SLEEP_BETWEEN_BATCHES)
```

**What this does:** Splits 158 names into batches of 50 and sends one API call per batch. That's 4 API calls total instead of 158.

**Why batching works:** LLMs can process many similar items in one call because the instructions are shared. The model reads the system prompt once and then applies it to all 50 names. This is dramatically more efficient than sending 50 separate calls.

**Why `time.sleep(2.5)`?** Groq's free tier allows 30 requests per minute. That's one request every 2 seconds. Sleeping 2.5 seconds between batches keeps us safely under the rate limit.

**Why not send all 158 in one call?** Two reasons: (1) Very long prompts use more tokens, and the free tier has a 6,000 tokens-per-minute limit. (2) If one call fails, you only lose 50 names, not 158.

#### 5. Two prompt strategies

**Open-vocabulary prompt (customers):**

```python
system = (
    "You are a data-cleaning assistant. You receive a list of messy company "
    "names... Map each messy name to a single canonical company name. "
    "Names that refer to the same real company must map to IDENTICAL "
    "canonical strings."
)
```

**Why "open"?** We don't tell the LLM what the 20 real customer names are. It figures out the canonical form by clustering the input itself. This is realistic because in real projects, you often don't have a master list of customers — you're trying to build one.

**Closed-vocabulary prompt (regions and segments):**

```python
system = (
    f"Allowed values: {CANONICAL_REGIONS}. "
    "Every canonical value MUST be one of the allowed values -- no exceptions."
)
```

**Why "closed"?** For regions and segments, we know the allowed values. Telling the LLM the exact allowed values constrains it to only produce those values. Much more reliable than asking it to invent its own.

#### 6. The fallback matcher

```python
def _fallback_match(dirty, allowed):
    dirty_lower = dirty.lower()
    for canonical in allowed:
        if canonical.lower() in dirty_lower or dirty_lower in canonical.lower():
            return canonical
    return allowed[0]
```

**What this does:** If the LLM returns a value that isn't in our allowed list (which can happen occasionally), we try to rescue it with simple substring matching. If that fails, we default to the first allowed value.

**Why this matters:** Defensive programming. LLMs are probabilistic — they occasionally produce unexpected output. A good pipeline has fallbacks for when the primary method fails. In production, you'd also log these cases so a human can review.

#### 7. Deterministic cleaning (dates and revenue)

```python
def clean_dates(series):
    return pd.to_datetime(series, format="mixed", errors="coerce")

def clean_revenue(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None
```

**`clean_dates` explained:**
- `format="mixed"` — tells pandas to try multiple formats until one works
- `errors="coerce"` — if a date can't be parsed, return `NaT` (Not a Time) instead of crashing

**`clean_revenue` explained:**
- If the value is already null → return None
- If it's already a number → return it as a float
- Otherwise convert to string, strip `$` and commas, try to parse as float, return None if it fails

**Why no AI here?** These problems have clear, unambiguous rules. AI would be overkill.

#### 8. The orchestrator

```python
def clean_pipeline(input_path, output_path, report_path):
    df = pd.read_csv(input_path)
    
    # Before metrics
    before = {...}
    
    # AI cleaning
    cust_map = clean_customer_names(...)
    df["customer_name_clean"] = df["customer_name"].map(cust_map)
    ...
    
    # Deterministic cleaning
    df["order_date_clean"] = clean_dates(df["order_date"])
    df["revenue_usd_clean"] = df["revenue_usd"].apply(clean_revenue)
    
    # After metrics
    after = {...}
    
    # Write outputs
    df.to_csv(output_path, index=False)
    Path(report_path).write_text(json.dumps(report, indent=2))
```

**Key design choice:** We add `_clean` columns alongside the original dirty columns rather than overwriting them. This means the output CSV has both `customer_name` (dirty, original) and `customer_name_clean` (cleaned). You can see exactly what the AI changed.

**Why measure before/after?** Because measurement is the whole point. Without measurement, we can't honestly put percentages on your resume. With measurement, we can say "reduced 158 variants to 20 canonical names — 87% deduplication" with full confidence.

### What Phase 2 Produces

When you run `python src/cleaner.py` with a valid Groq key, you see:

```
============================================================
CLEANING REPORT
============================================================
Metric                      Before      After    Reduction
------------------------------------------------------------
Unique customers               158         20         87.3%
Unique regions                  34          6         82.4%
Unique segments                 26          6         76.9%
```

And on disk you get:
- `data/clean_transactions.csv` — 5,000 rows with cleaned columns added
- `data/cleaning_report.json` — these same metrics as JSON, usable in Phase 4 reports
- `data/.cache/*.json` — three cache files that make future runs free

### Checklist for Completing Phase 2

Before you move to Phase 3, make sure:

1. ☐ Phase 1 is fully complete (`data/raw_transactions.csv` exists)
2. ☐ You've installed all dependencies (`pip install -r requirements.txt`)
3. ☐ You've signed up for a Groq account at [console.groq.com](https://console.groq.com) and generated an API key
4. ☐ You've created a `.env` file in the project root with `GROQ_API_KEY=gsk_...`
5. ☐ You've run the offline tests successfully (`python tests/test_cleaner_offline.py`)
6. ☐ You've run `python src/cleaner.py` successfully and seen the cleaning report
7. ☐ The file `data/clean_transactions.csv` exists and has the extra `_clean` columns
8. ☐ The file `data/cleaning_report.json` exists with before/after metrics
9. ☐ You've opened the cleaned CSV and verified that "Acme Industrial Corp" variants all map to the same canonical name
10. ☐ You've committed your Phase 2 work to git

---

## Part 4: Glossary of Unfamiliar Terms

If any of these terms confused you while reading, here's a plain-English definition:

**API (Application Programming Interface)** — A way for programs to talk to each other. Groq's API is a URL you send data to; it returns an AI-generated response.

**API key** — A secret password that identifies you to an API provider. You must keep it private (never in git).

**Batch / batching** — Grouping multiple items together and processing them in one operation instead of one at a time. More efficient for network calls.

**Cache** — A place where results are stored so you don't have to compute them again. Our cache is JSON files on disk.

**Canonical form** — The "correct" or "standard" version of a value. "Northeast" is the canonical form of "NE", "N.E.", "northeastern", etc.

**CSV (Comma-Separated Values)** — A simple text file format for tabular data. Excel can open it directly.

**DataFrame** — pandas' in-memory representation of a table. Rows and columns, like a spreadsheet.

**Deterministic** — Always produces the same output for the same input. Opposite of random.

**Environment variable** — A value stored outside your code (in the shell or a `.env` file) that your code can read. Good for secrets like API keys.

**ERP (Enterprise Resource Planning)** — Business software that tracks inventory, orders, customers, finance. SAP and Oracle NetSuite are examples.

**JSON (JavaScript Object Notation)** — A text format for structured data. Like Python dictionaries but for sharing between programs.

**LLM (Large Language Model)** — An AI model trained on text that can understand and generate language. GPT-4, Llama, and Claude are LLMs.

**Pareto distribution / 80-20 rule** — A pattern where 80% of outcomes come from 20% of causes. Common in business: 80% of revenue from 20% of customers.

**Prompt** — The instructions and input you send to an LLM. Good prompts are specific, constrained, and give examples.

**Rate limit** — A cap on how many API calls you can make in a time window. Groq free tier: 30 per minute.

**Seed (random seed)** — A starting number for a random number generator. Fixing the seed makes random operations reproducible.

**Temperature** — A setting that controls LLM randomness. 0 = deterministic, 1 = creative.

**Token** — An LLM's unit of text (roughly 3/4 of a word). Rate limits and costs are measured in tokens.

**Venv (virtual environment)** — An isolated Python installation for one project. Prevents dependency conflicts between projects.

---

## Part 5: What to Actually Do Next

Your plan, in order:

1. **Finish Phase 1 on your machine.** Generate the CSV. Open it. Look at the dirtiness. Once you can point to specific dirty values, you understand Phase 1.

2. **Take your own notes.** Rewrite sections of this document in your own words. Teaching something is the best way to prove you understand it. This will also prepare you for interview questions like "walk me through your data cleaning logic."

3. **Set up Phase 2.** Get your Groq key, make a `.env`, install requirements, run the offline tests.

4. **Run the cleaner.** Watch the API calls happen. Look at the cleaning report. Open `data/.cache/customers.json` and read what the AI decided.

5. **Tell me when you're done** — share the output of your cleaning report, or any error messages, or just confirm that it worked. Then we build Phase 3.

**Do not move to Phase 3 until Phase 2 runs successfully on your machine.** You won't understand the analyzer's output if you don't understand the cleaner's output.
