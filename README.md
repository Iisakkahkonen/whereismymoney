# whereismymoney

Where is all of Finland's money going? An open source tool for browsing public numbers about Finnish public finances: where the money comes from, and where it goes, down to benefits, grants to organisations and payments to companies, as far as the public data allows.

The main idea is a **coverage meter**: for every budget item it shows how much of the money can be traced to a source that says where it went, and how much is "not traced in public data". Nothing is estimated or filled in.

Status: Phase 1 (thin vertical slice). The state budget's actual spending for 2021 to 2025, with Kela's housing allowance and student aid traced against it, a search bar, a year selector, and English and Finnish text. See [`docs/PLAN.md`](docs/PLAN.md) for the plan, [`docs/HANDOFF.md`](docs/HANDOFF.md) for the current state and [`docs/data-inventory.md`](docs/data-inventory.md) for what each data source really contains.

## How it works

- `data-pipeline/` (Python): fetches the sources, runs the data checks (the build stops on ambiguous rows, on totals that do not add up, and on a Kela-to-budget gap above 5 percent), and writes Parquet files, a search index and a manifest. Kela figures come from `data-pipeline/snapshots/kela.json` (checked aggregates with each raw file's URL and SHA-256), because the Kela host refuses CI runners.
- `web/` (Vite, TypeScript): a static site. The browser queries the Parquet files with DuckDB-WASM, draws charts with ECharts and searches with MiniSearch. No backend.
- `e2e/` (Python, Playwright): headless browser tests against the built site.
- `.github/workflows/deploy.yml`: runs every test, then deploys to GitHub Pages. It also runs monthly to pick up new Treasury actuals; Kela is refreshed by hand (see below).

## Run it locally

```bash
# 1. Build the data (Treasury fetched fresh from the API, Kela from the committed snapshot; add --use-cache for a cache-only run that makes no request and stops if a file is missing)
pip install pyarrow requests pytest
cd data-pipeline && python -m pytest && python -m wimm.build --out ../web/public/data

# 1b. Refresh the Kela snapshot (downloads about 1.5 GB again into data-pipeline/cache; run on a normal connection;
#     --kela recompute re-aggregates the files already there, offline)
python -m wimm.build --kela download --out ../web/public/data

# 2. Run the site
cd ../web && npm install && npm run dev

# 3. Run all checks as CI does
npm run check:i18n && npm run build
pip install playwright && python -m playwright install chromium
cd .. && python -m pytest e2e
```

## Sources and licences

- State budget and actuals: State Treasury, Valtion talous API (https://avoindata.tutkihallintoa.fi/apis).
- Housing allowance and student aid: Kela (Kelasto), licensed CC BY 4.0. Source: Kela (Kelasto), licensed CC BY 4.0.

The code is Apache 2.0. Each data source's own licence and credit requirements apply.
