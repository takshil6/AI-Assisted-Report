# Phase 2 Setup Guide — Running the AI Cleaner with Groq

This guide takes you from "I have Python installed" to "the AI has cleaned my data."

## Step 1 — Get a Groq API Key (2 min, free, no credit card)

1. Go to **https://console.groq.com/keys**
2. Sign up with Google or email
3. Click **Create API Key**, give it a name like "data-pipeline"
4. **Copy the key immediately** — it looks like `gsk_abc123...`. You won't see it again.

## Step 2 — Put the Key in a `.env` File

In your project folder, copy the example file:

```bash
cp .env.example .env
```

Then open `.env` in a text editor and replace the placeholder:

```
GROQ_API_KEY=gsk_paste_your_real_key_here
```

**Important:** `.env` is in `.gitignore` — it will never be pushed to GitHub. That's intentional. Never commit API keys.

## Step 3 — Install Python Dependencies

From the project folder with your virtual environment activated:

```bash
pip install -r requirements.txt
```

This installs `pandas`, `openai` (Groq uses this same SDK), `python-dotenv`, `openpyxl`, and the other libraries we'll need in later phases.

## Step 4 — Verify Your Environment Without Spending API Calls

Run the offline test first. It validates your Python setup without touching the Groq API:

```bash
python tests/test_cleaner_offline.py
```

Expected output:
```
✓ test_dates passed
✓ test_revenue passed
✓ test_fallback_match passed

All offline tests passed. Safe to run the real pipeline.
```

If this fails, the issue is local (wrong Python version, missing pandas, etc.) — **fix it here** before burning API calls debugging.

## Step 5 — Make Sure Phase 1 Data Exists

```bash
# If you haven't generated the dirty data yet, or want to regenerate it:
python src/generate_dirty_data.py
```

You should see:
```
✓ Generated 5,000 rows
✓ Unique (dirty) customer strings: 158
...
```

## Step 6 — Run the AI Cleaner

```bash
python src/cleaner.py
```

What you should see (roughly):

```
Loading data/raw_transactions.csv...
  5,000 rows, 10 columns

Cleaning customer names via Groq...
  [customer] 158 new names to clean (cached: 0)
  [customer] Batch 1: 50 names...
  [customer] Batch 2: 50 names...
  [customer] Batch 3: 50 names...
  [customer] Batch 4: 8 names...

Cleaning regions via Groq...
  [region] 34 new regions to clean

Cleaning industry segments via Groq...
  [segment] 26 new segments to clean

Parsing dates and revenue (deterministic)...

============================================================
CLEANING REPORT
============================================================
Metric                      Before      After    Reduction
------------------------------------------------------------
Unique customers               158         20         87.3%
Unique regions                  34          6         82.4%
Unique segments                 26          6         76.9%
------------------------------------------------------------
Saved cleaned data ->  data/clean_transactions.csv
Saved report       ->  data/cleaning_report.json
```

**Total API calls used: ~7** (well under the 1,000/day free-tier limit). **Total time: ~30 seconds.**

## Step 7 — Verify the Results

Open `data/clean_transactions.csv` in Excel. Compare the `customer_name` column (dirty) to `customer_name_clean` (cleaned). You should see 158 variant strings collapsed to 20 canonical forms.

Also open `data/cleaning_report.json` — **these numbers are what you'll cite on your resume.**

## Step 8 — Re-Run Is Free (Caching Works)

Run `python src/cleaner.py` again. This time, you'll see:

```
  [customer] All 158 names already cached.
  [region] All 34 regions already cached.
  [segment] All 26 segments already cached.
```

**Zero API calls the second time.** This matters because: (a) your demo in an interview won't hit rate limits, (b) you can iterate on the analyzer/reporter in Phase 3–4 without re-cleaning every time.

The cache lives in `data/.cache/`. Delete that folder if you want to force a fresh run.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `GROQ_API_KEY not set` | Check `.env` file exists in project root and has no typos |
| `ModuleNotFoundError: openai` | Run `pip install -r requirements.txt` again inside your venv |
| `429 rate limit` | Wait 60 seconds and re-run — the cache means you won't redo finished work |
| JSON parse error from LLM | Already handled: the code retries once. If it persists, the model may be overloaded — try again in a minute |
| Cleaned customer count > 25 | LLM clustered some variants too aggressively. Delete `data/.cache/customers.json` and re-run. |

## What's Next

Once the cleaner runs successfully and you see the 87%+ reduction numbers, you're ready for **Phase 3: 80/20 Pareto Analysis** — where we identify the 20% of customers driving 80% of revenue, compute segment concentration, and produce the metrics that go into the weekly report.
