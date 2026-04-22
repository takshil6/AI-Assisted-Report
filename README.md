# AI-Assisted Data Quality & Reporting Pipeline

An end-to-end pipeline that ingests messy industrial transaction data, uses AI to clean and standardize it, runs 80/20 Pareto analysis, generates weekly reports, and provides a natural-language query interface for non-technical stakeholders.

## Why This Exists

In industrial B2B companies (like Kadant), transaction data is notoriously dirty: customer names are spelled 15 different ways, regions are inconsistent, product categories are free-text. Before any analysis can happen, someone spends hours cleaning it by hand. This pipeline automates that cleaning with an LLM and then runs the 80/20 analysis that finance and corporate development teams need weekly.

## Architecture

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  Raw Data    │───▶│ AI Cleaner   │───▶│  Analyzer    │───▶│  Reporter    │
  │  (CSV/XLSX)  │     │  (Groq API)  │     │ (80/20)      │     │ (XLSX+Charts)│
  └──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                          │
                              ┌───────────────────────────────────────────┤
                              ▼                                           ▼
                    ┌──────────────────┐                        ┌──────────────────┐
                    │ SharePoint /     │                        │ NL Query Agent   │
                    │ Local /reports   │                        │ (LangChain)      │
                    └──────────────────┘                        └──────────────────┘
```

## Phase Plan

- [x] **Phase 1** — Project skeleton + synthetic messy dataset
- [x] **Phase 2** — AI cleaning module (Groq API, Llama 3.1 8B)
- [x] **Phase 3** — 80/20 Pareto analysis engine
- [ ] **Phase 4** — Weekly report generator
- [ ] **Phase 5** — SharePoint / local delivery
- [ ] **Phase 6** — Natural-language query interface (Streamlit)

## Quickstart

```bash
git clone <your-repo>
cd ai-data-quality-pipeline
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # add your Groq API key

# Phase 1: Generate the synthetic dirty dataset
python src/generate_dirty_data.py

# Phase 2: Clean it using Groq
python src/cleaner.py

# Inspect the cleaning results
python -c "import json; print(json.dumps(json.load(open('data/cleaning_report.json')), indent=2))"
```

## Project Structure

```
ai-data-quality-pipeline/
├── data/                       # Raw and cleaned data
│   ├── raw_transactions.csv    # Dirty input (generated)
│   └── clean_transactions.csv  # Output of Phase 2
├── src/
│   ├── generate_dirty_data.py  # Phase 1: synthetic data generator
│   ├── cleaner.py              # Phase 2: AI cleaning
│   ├── analyzer.py             # Phase 3: 80/20 analysis
│   ├── reporter.py             # Phase 4: Excel reports
│   ├── delivery.py             # Phase 5: SharePoint upload
│   └── query_app.py            # Phase 6: Streamlit NL query UI
├── reports/                    # Generated weekly reports
├── tests/
├── docs/
├── requirements.txt
├── .env.example
└── README.md
```

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Data | pandas, openpyxl |
| AI | Groq API (`llama-3.1-8b-instant`) via OpenAI-compatible SDK |
| NL querying | LangChain + pandas agent |
| Reporting | openpyxl with charts |
| UI | Streamlit |
| Delivery | Office365-REST-Python-Client |

### Why Groq?
Free tier (no credit card), OpenAI-compatible API (swap `base_url` only),
and very fast inference on Llama 3.1 8B which is more than capable for
structured cleaning tasks. Rate limits: 30 req/min, 14,400 req/day on
the 8B model. Our batching strategy (~50 items per call) means the full
dataset cleans in ~3 API calls.
