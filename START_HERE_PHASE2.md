# START HERE — Phase 2

Welcome back. You've finished Phase 1; now let's set up Phase 2 carefully.

## Before You Do Anything Else — Verify Phase 1

Run this first. It checks that your dirty dataset from Phase 1 looks healthy, so you don't burn Groq API calls debugging a broken input:

```bash
python tests/verify_phase1.py
```

Expected output: **7 green checkmarks**. If any fail, regenerate with `python src/generate_dirty_data.py` before continuing.

## Then Follow These Steps In Order

1. **Read** `docs/PHASE1_AND_PHASE2_EXPLAINED.md` (if you haven't already)
   — This is your study document. Understand Phase 2 before running it.

2. **Follow** `docs/PHASE2_SETUP.md`
   — Step-by-step Groq setup: getting the API key, creating `.env`, installing deps.

3. **Run the offline tests** (no API key needed yet):
   ```bash
   python tests/test_cleaner_offline.py
   ```
   If these fail, your Python environment has a problem. Fix that before spending API calls.

4. **Run the cleaner:**
   ```bash
   python src/cleaner.py
   ```

5. **Inspect the results:**
   - Open `data/clean_transactions.csv` in Excel — look at the `_clean` columns
   - Open `data/cleaning_report.json` — these are your resume-worthy metrics
   - Open `data/.cache/customers.json` — read what the AI decided

6. **Commit to git:**
   ```bash
   git add .
   git commit -m "Phase 2: AI cleaning module with Groq + caching"
   git push
   ```

7. **Report back to me** — tell me what your cleaning report says, or paste any error. Only then do we start Phase 3.

## Files Added in Phase 2

| File | Purpose |
|---|---|
| `src/cleaner.py` | The AI cleaning module |
| `tests/test_cleaner_offline.py` | Tests the deterministic parts (no API needed) |
| `tests/verify_phase1.py` | Sanity-checks Phase 1 output before Phase 2 runs |
| `docs/PHASE2_SETUP.md` | Step-by-step Groq setup instructions |
| `docs/PHASE1_AND_PHASE2_EXPLAINED.md` | Deep conceptual walkthrough |
| `.env.example` | Template for your `GROQ_API_KEY` |

## Something Not Working?

Don't guess — ask me. Paste the exact error message and I'll walk you through it. That's what we're here for.
