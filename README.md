# AI-Assisted Data Quality & Reporting Pipeline

An end-to-end pipeline that ingests messy industrial transaction data, uses AI to clean and standardize it, runs 80/20 Pareto analysis, generates weekly reports, and provides a natural-language query interface for non-technical stakeholders.

## Why This Exists

In industrial B2B companies (like Kadant), transaction data is notoriously dirty: customer names are spelled 15 different ways, regions are inconsistent, product categories are free-text. Before any analysis can happen, someone spends hours cleaning it by hand. This pipeline automates that cleaning with an LLM and then runs the 80/20 analysis that finance and corporate development teams need weekly.

## Architecture

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  Raw Data    │───▶│ AI Cleaner   │───▶│  Analyzer    │───▶│  Reporter    │
  │  (CSV/XLSX)  │     │ (OpenAI API) │     │ (80/20)      │     │ (XLSX+Charts)│
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
- [ ] **Phase 2** — AI cleaning module (OpenAI API)
- [ ] **Phase 3** — 80/20 analysis engine
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
cp .env.example .env             # add your OpenAI API key

# Generate the synthetic dirty dataset
python src/generate_dirty_data.py

# Inspect what was generated
python -c "import pandas as pd; print(pd.read_csv('data/raw_transactions.csv').head(20))"
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
| AI | OpenAI API (gpt-4o-mini) |
| NL querying | LangChain + pandas agent |
| Reporting | openpyxl with charts |
| UI | Streamlit |
| Delivery | Office365-REST-Python-Client |
