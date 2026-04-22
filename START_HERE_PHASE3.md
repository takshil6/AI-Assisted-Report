# START HERE — Phase 3

You've completed Phase 2 (Groq cleaning). Now we analyze.

## Phase 3 at a Glance

- **No API calls.** Pure pandas.
- **Runs in under a second** on your 5,000-row dataset.
- Produces **5 output files** ready for Phase 4's report generator.

## Steps (in order)

### 1. Verify Phase 2 output exists
```bash
ls -lh data/clean_transactions.csv
```
File should be ~1 MB. If missing, re-run `python src/cleaner.py` first.

### 2. Read the concepts (optional but recommended)
Open `docs/PHASE3_EXPLAINED.md` — covers what Pareto analysis is, why we use `groupby` and `cumsum`, and how to explain this in an interview.

### 3. Run the offline tests
```bash
python tests/test_analyzer_offline.py
```
You should see **6 green checkmarks**. This validates the math on a tiny hand-crafted dataset where the correct answers are obvious.

### 4. Run the analyzer
```bash
python src/analyzer.py
```
You should see:
- A note about dropping null + negative revenue rows
- The printed `ANALYSIS REPORT` with total revenue, Pareto %, top 5 segments/regions, weekly stats

### 5. Inspect the outputs
Open these in Excel:
- `data/customer_pareto.csv` — every customer ranked, with the `is_pareto_80` flag
- `data/segment_breakdown.csv` — revenue by industry segment
- `data/region_breakdown.csv` — revenue by region
- `data/weekly_revenue.csv` — week-by-week totals with WoW change

And the master JSON that Phase 4 will consume:
- `data/analysis_results.json`

### 6. Report back

Paste me:
- The full terminal output of `python src/analyzer.py`
- Open `data/analysis_results.json` and paste the `pareto_summary` and `dataset_summary` sections

### 7. Commit
```bash
git add .
git commit -m "Phase 3: 80/20 Pareto analysis engine"
git push
```

## What's Coming in Phase 4

Once your analyzer output looks right, Phase 4 will build `src/reporter.py` — which takes `analysis_results.json` and produces a **professional Excel report** with:
- Executive summary sheet
- Pareto customer list
- Segment/region breakdown tables
- Embedded charts (revenue trend, Pareto curve)

That's the deliverable a sales leader at Kadant would actually look at every week.
