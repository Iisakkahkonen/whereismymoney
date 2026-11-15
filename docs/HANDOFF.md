# whereismymoney: handoff note

First written 2026-11-15 from the web chat; rewritten the same day after Phase 0 and Phase 1. Read this first, then `PLAN.md` (plan, status, data inventory) and `data-inventory.md` (what each source really looks like). Whoever picks this up next (Claude Code or Codex): this note is meant to be enough to continue without asking.

## Who and what
Iisak Kähkönen is building `whereismymoney`, one of the projects in his Vibecoding Portfolio: a public, open source web app for browsing where Finland's public money comes from and where it goes. Every portfolio project is independent and has its own repo. It is meant to show employers how he works with AI, so how it was built and what he decided are part of the deliverable. He sets the direction and makes the decisions; the AI does the mechanical work. Keep replies short and plain. He gets frustrated by long caveats and over-careful framing; say what is true and what is next.

## The idea, in his words
"The whole idea is to get all of the spending covered so I can see where the money is going." The site is a drill-down: ministry, then budget item, then the breakdown inside it (for example Kela housing allowance, one step below Kela). Every budget item is shown (100% of state spending). The part that a second dataset breaks down further is the "traced" share, and it must grow as sources are added. Today it is about 2% (2025). 100% is not reachable (confidential purchases and individual payments are not published); the remainder is shown honestly as "not traced".

## State of things (2026-11-15)
- Repo: https://github.com/Iisakkahkonen/whereismymoney, public, Apache 2.0. Everything below is on `main`.
- **Phase 0 (data recon): done.** `data-inventory.md` has nine sources, traps, and the owner's decisions.
- **Phase 1 (thin vertical slice): built and merged.** Budget items 2021 to 2025 (State Treasury API), Kela housing allowance and student aid traced against their budget items, search (EN/FI), year selector, treemap and charts (ECharts), coverage meter, sources page with every Kela-to-Treasury gap. Tests: 69 pipeline tests, an EN/FI parity check, a TypeScript check, 13 headless browser tests.
- **Deploy: working (owner-reported 2026-11-15).** The first CI run failed because `avoindata.suomi.fi` answers 403 to GitHub Actions runners (the same URL works from a home connection). Fixed in commit `17aaf6b`: CI no longer downloads Kela files. It reads `data-pipeline/snapshots/kela.json`, the checked aggregates plus each raw file's URL, SHA-256, size and download date, and still reconciles against the Treasury. The owner then set the repo's Pages source to "GitHub Actions" and says the site now deploys. The builder has no access to CI results from its host and has not opened the live site, so that is reported, not independently verified.
- Roles in the agent bridge room "whereismymoney workshop": `sonnet-builder` (Claude Code) implements and maintains the docs; `codex-advisor` (Codex) reviews correctness, data interpretation, coverage and reconciliation logic, tests and next steps, read-only on implementation files. The owner decides scope and settles disagreements.
- Known and accepted: Kela figures refresh only by hand (see below); the monthly cron refreshes Treasury data only. DuckDB-WASM costs about 8 MB gzipped on first load. The Treasury API licence and the StatFin licence are unconfirmed.

## How to work on it
```bash
pip install pyarrow requests pytest playwright
python -m pytest data-pipeline                      # from the repo root
cd data-pipeline && python -m wimm.build --cache cache --out ../web/public/data   # fetches Treasury fresh, Kela from the snapshot
#   add --use-cache to reuse Treasury files already in data-pipeline/cache (offline; the manifest says so)
cd ../web && npm ci && npm run check:i18n && npx tsc --noEmit && npm run build
cd .. && python -m playwright install chromium && python -m pytest e2e
```
- **Refresh Kela** (run from a normal connection, not CI): `python -m wimm.build --kela download`. Downloads about 1.5 GB again into `data-pipeline/cache/` (git-ignored), re-aggregates, rewrites `snapshots/kela.json`. Review the diff and commit it. `--kela recompute` re-aggregates the raw files already on disk without any request. Fetching is fresh by default (`wimm/http.py` `fetch(refresh=True)`); reusing files on disk is always an explicit offline choice, and CI keeps no download cache. If a year or file changes, the reconciliation guard (5%) tells you if a filter broke.
- A test (`test_committed_snapshot_is_valid_and_covers_every_year`) fails if the snapshot is missing a benefit or year in `YEARS`. Adding a year means: add its Kela resource ids in `kela.py`, add it to `YEARS` in `build.py`, run the download refresh.
- Windows notes from the first sessions: use `sys.stdout.reconfigure(encoding="utf-8")` for Finnish text in scripts; the dev machine has about 6.8 GB RAM, so a full build next to a dev server can run out of memory (the Kela duplicate check keeps hashes, not keys, for that reason); the first e2e run can flake on page-load timeouts when memory is tight, rerun the single test before suspecting code.
- Where things are: `data-pipeline/wimm/` (`treasury.py`, `kela.py`, `coverage.py`, `build.py`), `data-pipeline/tests/`, `data-pipeline/samples/` (small fixtures), `data-pipeline/recon/` (re-check scripts), `web/src/` (`db.ts` DuckDB, `data.ts` queries, `views.ts`, `charts.ts`, `i18n.ts`), `e2e/test_site.py`, `.github/workflows/deploy.yml`.

## Decisions already made
- Web app, any device. Vite + TypeScript, Python pipeline, Parquet queried in the browser with DuckDB-WASM. No backend until Phase 5 (supplier invoices) at the earliest.
- Chart library: ECharts (treemap now, Sankey later). Decided in Phase 1.
- Scope: as broad and low-level as the data allows, state money first. Municipalities and wellbeing counties only where the state sends them money for a specific purpose.
- Coverage rule (owner: keep it simple): traced is capped at the actual and never negative; the source's own figure is kept and any overage is flagged.
- Treasury-vs-Kela gap (about 1%, up to 3.4% for housing allowance in 2023): accepted, documented and published, build fails above 5%.
- Municipal invoice data: include as a separate, partial-coverage category if the data is enough.
- Grants: find more sources before contacting anyone. STEA has an official open Excel (confirmed). Tutkiavustuksia and other grantors have no bulk file found yet; email the State Treasury only if nothing works.
- Ship first, then deepen: add the biggest breakdowns one at a time.

## Next steps
1. Get a review of the Phase 1 data logic (coverage rule, reconciliation guard, Kela snapshot) from the reviewer before building on it.
2. First deepening source: the owner chose wellbeing-county transfers, then declined to let the builder download the ministry's per-county Excel files, so that recon is **parked** (findings and links in `data-inventory.md` section 10: the Treasury's Kuntatalous API exposes only taxonomy files; the matched per-county allocation exists as Excel on vm.fi/rahoituslaskelmat, contents unread). **Ask the owner which source to take next.** Candidates: STEA grants (confirmed source, 2024 reconciles to item 339050, business IDs from 2021; smallest and lowest risk, proves named-recipient drill-down), resume the county recon if the owner allows the downloads, other Kela benefits (each needs its own verified rollups), pensions (no verified detailed source yet).
3. For any new source, follow the rules below: confirm URL, fields and filters against the live source, add a pipeline test and a Sources row, only then call it done. If its host blocks CI, use the same committed-snapshot pattern as Kela.

## Rules to keep
- No dataset counts as done until its URL, fields and filters are confirmed against the live source, it has a pipeline test and a row in the Sources section.
- The build must stop if a series is ambiguous (more than one value per key and year).
- Tests gate every deploy (pytest, the parity check, the type check, a headless browser test).
- Never cut: source links for every number, the coverage meter, the methodology and "what is not covered" page, tests that totals reconcile with the budget, licence credits (Kela requires attribution; CC BY 4.0).
- EN/FI parity for all UI text. Small commits with clear messages: the history is part of the case study.
- Never fill in missing data or guess recipients; show gaps as gaps.

## Things to be careful about
- Kela data is aggregates only, never individuals, and groups under four people are suppressed. Never try to identify anyone.
- Kela cubes hold rollup rows and several time grains; only the filters in `kela.py` give the right total. A plain sum is 7 to 36 times too high.
- Confidential state purchases are not in the invoice data; say so on the page.
- The national procurement repository (all public sector invoices) starts in 2027; it is not a dependency.

## Reporting back
When a phase or source is done, update the status section of `PLAN.md` and this note, and tell the owner what changed and what is next. At the end the owner wants a case study in the style of the dashboard's, with a "What I learned" section in his own words.
