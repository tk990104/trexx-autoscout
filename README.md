# T-Rexx AutoScout

A local-first CarMax research MVP for importing Apify dataset exports, keeping an immutable SQLite scan history, ranking potential deals, detecting new listings and price movements, and producing source-grounded Markdown for NotebookLM.

This first version deliberately supports **file imports only**. Live Apify collection is marked with explicit TODOs in `collectors/carmax.py`, so you can validate the research workflow before connecting credentials or paying for actor runs.

## What works now

- Import CarMax/Apify `.json` and `.csv` exports.
- Normalize common field-name variants into one listing shape.
- Ignore invalid rows that do not contain both a VIN and a price.
- Save every import as an immutable scan in SQLite.
- Calculate a transparent starter Deal Score from 0–100.
- Detect first-seen VINs and price changes against their prior observations.
- Write NotebookLM-ready Markdown with top deals, changes, cautions, and suggested questions.
- Run entirely on Windows with Python's standard library.

## Project map

```text
trexx-autoscout/
├── collectors/carmax.py       # JSON/CSV import, normalization, Apify TODO
├── scoring/deal_score.py      # Basic 0–100 ranking
├── analysis/price_history.py  # New-listing and price-change queries
├── analysis/market_comps.py   # Same-model median benchmarks
├── reports/notebooklm.py      # NotebookLM-ready Markdown
├── config/searches.json       # Future live-search definitions
├── sample_data/               # Synthetic, non-production sample
├── tests/                     # Standard-library smoke tests
├── database.py                # SQLite schema and snapshot persistence
├── app.py                     # Command-line entrypoint
├── .env.example               # Credential names only; no secrets
└── requirements.txt           # No third-party packages for the MVP
```

## Windows quick start

Open PowerShell in the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py ingest sample_data\carmax_sample.json --report reports\output\sample.md
```

The command creates `data\autoscout.db` and `reports\output\sample.md`. Both locations are ignored by Git.

If PowerShell blocks local activation scripts, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe app.py ingest sample_data\carmax_sample.json --report reports\output\sample.md
```

## Import your CarMax/Apify export

Export an Apify dataset as JSON or CSV, then run:

```powershell
python app.py ingest C:\path\to\carmax-results.json --search-name "home-100mi" --report reports\output\latest.md
```

Import a later export with the same command. AutoScout compares each VIN with its most recent older observation and reports any price movement. To rebuild a report for the latest saved scan:

```powershell
python app.py report --output reports\output\latest.md
```

Use a different database without changing code:

```powershell
python app.py --database D:\AutoScout\autoscout.db ingest C:\path\to\results.csv
```

## Expected input

The normalizer accepts common variants such as `vin`/`VIN`, `price`/`currentPrice`, `mileage`/`miles`, `storeName`/`location`, `transferFee`, and `listingUrl`/`url`. JSON may be a top-level array, a single listing object, or an object containing an `items`, `results`, or `data` array.

At minimum, each usable row needs a VIN and a numeric price. Unknown source fields are preserved in `raw_json` for later remapping.

## Deal Score

The starter score is a research ranking, not a buying recommendation:

- 55 points: price versus the median of at least two same-make/model listings within two model years.
- 25 points: lower mileage.
- 10 points: lower transfer fee.
- 10 points: advertised reduction from original price.

When there are not enough comparable listings, the price component stays neutral. Future versions should add trim-aware comps, local-market baselines, vehicle-history data, option packages, days listed, condition, and confidence bands.

## Configure future searches

Edit `config/searches.json` and replace `YOUR_ZIP_CODE`. This file documents the intended search filters but is not sent anywhere in the file-import MVP.

For the future Apify connection, copy `.env.example` to `.env` and fill values only on your own computer:

```dotenv
APIFY_API_TOKEN=your-local-token
APIFY_ACTOR_ID=your-approved-actor-id
DATABASE_PATH=data/autoscout.db
```

`.env` is ignored by Git. Never paste or commit a real API token. The next integration step is to implement `fetch_from_apify()` with timeouts, retries, rate-limit handling, dataset validation, and an explicit actor choice.

## Verify the MVP

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py database.py collectors scoring analysis reports
```

## Research cautions

CarMax availability and prices can change quickly. AutoScout does not inspect vehicles, verify listing accuracy, retrieve accident history, calculate taxes or financing, or guarantee market value. Confirm the VIN, equipment, fees, recalls, title/history, and mechanical condition before making a decision.

