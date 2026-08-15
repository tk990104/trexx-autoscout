# T-Rexx AutoScout

A local-first CarMax research MVP for collecting or importing Apify datasets, keeping an immutable SQLite scan history, ranking potential deals, detecting new listings and price movements, and producing source-grounded Markdown for NotebookLM.

You can validate the full workflow with synthetic sample data before connecting an Apify account or starting a paid Actor run.

## What works now

- Import CarMax/Apify `.json` and `.csv` exports.
- Run a configured CarMax Actor through Apify's official synchronous API.
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
├── collectors/carmax.py       # JSON/CSV import, normalization, live Apify client
├── scoring/deal_score.py      # Basic 0–100 ranking
├── analysis/price_history.py  # New-listing and price-change queries
├── analysis/market_comps.py   # Same-model median benchmarks
├── reports/notebooklm.py      # NotebookLM-ready Markdown
├── config/searches.json       # Local live-search definitions
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

## Connect live CarMax data

The documented default is Apify's maintained `e-commerce/carmax-zipcode-search-scraper` Actor. Actor availability, output, and pricing can change, so review its Apify Store page before each first run.

1. Create or sign in to your Apify account and add the CarMax ZIP-code Actor.
2. Copy `.env.example` to `.env` if you have not already done so.
3. Get your token from Apify Console's **Settings → Integrations** page and put it in `.env` on your computer only.
4. Replace `YOUR_ZIP_CODE` in `config/searches.json`. You can also add makes or change the supported radius.
5. Start with the default safety limits, then run the collection command.

```powershell
Copy-Item .env.example .env
notepad .env
notepad config\searches.json
python app.py collect
```

The local `.env` file should look like this:

```dotenv
APIFY_API_TOKEN=your-local-token
APIFY_ACTOR_ID=e-commerce/carmax-zipcode-search-scraper
APIFY_MAX_ITEMS=100
DATABASE_PATH=data/autoscout.db
```

`.env` is ignored by Git. Never paste or commit a real API token. The token is sent in an authorization header, not in the URL. AutoScout deliberately does not retry a timed-out Actor run because the original run may still have incurred usage.

The default search also sets `maxRequestsPerCrawl` to 5, and AutoScout sends a paid-result safety cap of 100. These are cautious starting values, not a guarantee of zero cost. Review the Actor's current pricing and your Apify usage dashboard.

To use a different cap for one run:

```powershell
python app.py collect --max-items 25 --report reports\output\latest.md
```

## Verify the MVP

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py database.py collectors scoring analysis reports
```

## Research cautions

CarMax availability and prices can change quickly. AutoScout does not inspect vehicles, verify listing accuracy, retrieve accident history, calculate taxes or financing, or guarantee market value. Confirm the VIN, equipment, fees, recalls, title/history, and mechanical condition before making a decision.
