# whereismymoney: execution plan

Written 2026-11-15, updated the same day with the owner's decisions. A separate project from the Finland vs. EU dashboard. Current state and next steps: `HANDOFF.md`.

## Status
Updated 2026-11-15.

- **Phase 0 (data recon): done, pending owner review.** Findings are in `data-inventory.md`. Six of nine sources are confirmed live (budget, both Kela datasets, invoices, StatFin, STEA). Three are partial or open: the company register (misses most large associations and foundations), Tax Administration (listed, not queried), and Tutkiavustuksia (a dashboard with no documented bulk file or API). The owner's answers to the three open questions are at the end of the inventory.
- **Follow-up the same day:** STEA turned out to have an official open Excel (CC BY 4.0, 2017 to 2026, business ID on every row from 2021). Its 2024 total equals the Treasury budget item 339050 to the euro. The 2024 invoice file is 39% state and 61% a few other organisations, mostly Helsinki, so municipalities get a separate, partial-coverage category.
- **What changed in the plan because of it:**
  - The budget CSV link was dead. The budget and actuals come from the State Treasury API `api.tutkihallintoa.fi/valtiontalous/v1`, open and without a key, with a 3-year limit per request.
  - Kela files cannot be summed as they are. They hold rollup rows and several time grains. With the rollup filter, Kela's 2024 totals match the Treasury's actuals within 1.1% (asumistuki) and 0.4% (opintotuki).
  - The invoice data has anonymised rows (supplier `NA`, "Salassa pidettävä"), counted as "not traced". Whether whole confidential purchases are excluded cannot be shown from a sample, so the page still says they are.
  - File sizes are larger than listed on the open data portal (a 2024 Kela file is 306 MB, a 2024 invoice file 807 MB).
- **First deploy failed, fixed in commit `17aaf6b`; the owner reports the site now deploys (after setting the Pages source to "GitHub Actions"):** `avoindata.suomi.fi` answers 403 to GitHub Actions runners, so CI cannot download the 1.5 GB of Kela files. CI now reads `data-pipeline/snapshots/kela.json` (checked aggregates with each source file's URL, SHA-256, size and date) and still reconciles against the Treasury; `python -m wimm.build --kela download` refreshes it by hand from a normal connection. The Sources page lists the raw files. 30 pipeline tests now. See `HANDOFF.md` for how to run and refresh.
- **Phase 1 (thin vertical slice): built, merged to `main` and deployed (owner-reported).** Budget actuals 2021 to 2025 (State Treasury API) with Kela housing allowance and student aid traced against their budget items; search with suggestions in English and Finnish; year selector; coverage meter; sources page; pipeline tests, an EN/FI parity check and 13 headless browser tests; a GitHub Actions workflow that runs all of them before deploying. In 2024, 2.5% of state spending is traced (2.19 bn of 86.76 bn); in 2025, 2.2%. Treasury and Kela agree within 0.6% for student aid and between −3.4% and +1.3% for housing allowance (2021 to 2025); the guard fails the build beyond 5%, and every gap is published on the sources page. State spending jumps in 2023 (63.6 bn in 2021, 91.9 bn in 2023) because the state began funding the wellbeing services counties; the sources page says so. Decisions made: chart library is ECharts (it has the treemap and later the Sankey; Chart.js has neither); the browser reads Parquet through DuckDB-WASM, loaded as in-memory buffers (the files are 25 KB at this stage). Known cost: DuckDB-WASM is 34 MB, about 8 MB gzipped, on first load. Coverage rule decided (owner: keep it simple): traced is capped at the actual and never negative, the source's own figure is kept and any overage is flagged, so nothing is hidden. Page wording now treats ministry to budget item as the main view (100% of spending) and the breakdown inside an item as the part that grows as sources are added. 
- **Next (owner's direction, 2026-11-15: ship, then deepen):** Phase 1 is merged and deployed. Add the biggest breakdowns one at a time so the broken-down share grows: wellbeing county and municipal transfers (Treasury Kuntatalous API, not yet checked), pensions and other benefits, STEA and other grants, supplier invoices. Full 100% is not possible (confidential purchases and individual payments are not published); the remainder is shown honestly as not traced.

## Goal
A web app for browsing where Finland's public money comes from and where it goes, down to the most detailed level the public data allows: benefit by benefit, grant by grant, supplier by supplier. Everything is searchable under broad terms with working suggestions, and filterable by year, sector and so on. The owner wants to be able to say "each euro accounted for when possible", so the app also has to show honestly where it can't trace a euro.

## What the owner asked for
- Web app, usable on any device.
- As broad as the data goes, with very low-level detail (for example asumistuki vs. opintotuki, which companies get which money, how much each järjestö gets directly from the state), alongside the big headline numbers.
- Free-text search with a suggestion bar that works, plus filtering (sector and more, to be defined as we go).
- Pick a year or range if possible, otherwise start with the most recent data.
- Look clean, with some design effort.

## Decisions (2026-11-15)
1. **Stack:** Vite + TypeScript, as in the Finland vs. EU dashboard (that one uses Chart.js). Chart library: ECharts (decided in Phase 1). Chart.js is fine for line and bar charts but has no treemap or Sankey; ECharts has both.
2. **Backend:** owner is fine with a backend if it's needed. Current judgement: not needed at the start. Data is published yearly or monthly, so a scheduled build can precompute everything, and the browser can query Parquet files with DuckDB-WASM. Revisit in Phase 5 (supplier invoices, the biggest data) if the files get too large for the browser or search gets slow. No accounts, keys or paid services are needed for this.
3. **Municipalities and wellbeing counties:** out of the first release as their own subject. Only include them where the state sends them money for a specific purpose (state transfers to municipalities), as a recipient in the flow table.

## Data: what exists, at which depth
Researched 2026-11-15 from a cloud session with no direct access to the sites, then checked against the live sources in Phase 0 (see `data-inventory.md`, which overrides this section where they differ). Entries marked "verify" below were tested unless the inventory says otherwise.

### Level 1: top-down (whole public sector, by category)
- **Statistics Finland StatFin (PxWeb API, pxdata.stat.fi):** general government expenditure by function (COFOG, table 12a6), revenue and expenditure (11zf quarterly, 15ah annual back to 1975), deficit and debt. Caveat: StatFin changed identifiers and variable codes on 2026-06-08, so older example queries break. Series break in 2023 when health and social services moved to wellbeing services counties.
- **Eurostat:** the same COFOG structure for all member states (gov_10a_exp).
- Use: the headline view and the Finland-vs-EU context.

### Level 2: the state budget, line by line (planned and actual)
- **Ministry of Finance, budjetti.vm.fi:** dead. The old open data URL now 404s and redirects to the ministry homepage; the avoindata.fi records for it are stale. Use the Treasury API below.
- **State Treasury, avoindata.tutkihallintoa.fi:** REST API "Valtion talous v1" at `https://api.tutkihallintoa.fi/valtiontalous/v1/`, CSV output, open and without a key (confirmed). Budget and actual figures by momentti and month, with a 3-year limit per request. Transactions work for 2010 onwards in tests; how far back items can be joined is open. Documentation mostly in Finnish.
- Use: the backbone. Every other dataset should hang off a budget item where possible.

### Level 3: recipient level
| Question | Source | What it really gives | Limits |
|---|---|---|---|
| asumistuki, opintotuki, toimeentulotuki and other Kela benefits | Kela open data (Kelasto) on avoindata.suomi.fi, CC BY 4.0 | Totals paid and recipient counts by benefit, month/year, region and other splits. Housing allowance annual from 1994, monthly from 2018. Student aid annual from 2005, monthly from 2018. Basic social assistance from 2017 (not checked in Phase 0). | Aggregates only, never individuals. Groups under four people are suppressed into municipality 199 / "Tuntematon". Housing allowance has no recipient counts, student aid does. Files contain rollup rows and several time grains; summing them naively overcounts by 20 to 36 times, so a strict filter is required (inventory, sources 2 and 3). Files are 100 to 300 MB per year. |
| Grants to järjestöt and others | Tutkiavustuksia.fi (State Treasury's central grants register); STEA grants at avustukset.stea.fi; some ministries publish lists on their own sites | Recipient, amount, purpose, grant authority. STEA alone: €273.9m to 766 organisations in 2026 (the earlier "686" was wrong). The register covers a few billion euros a year across dozens of grant authorities. | Checked: STEA offers an official open Excel download (avustukset.stea.fi/download, CC BY 4.0, 2017 to 2026, with business ID) that reconciles with the budget. Tutkiavustuksia (a dashboard at tutkihallintoa.fi/valtionavustukset) shows no documented bulk download or API, and no other national grants dataset was found; unresolved, see the inventory. Its own material lists things to keep in mind (state transfers to municipalities, loans and guarantees, tax reliefs and similar are not "grants"). Data arrives up to 3 months late and older years may be patchy. |
| Payments to companies and other suppliers | Tutkihankintoja.fi / OpenProcurement.fi data on avoindata.suomi.fi | Central government invoices from 2016, yearly files (semicolon-delimited despite the TSV/CSV label, one row per accounting row), vendor business ID where it was on the invoice, procurement categories. Files run from 272 MB (2017) to over 800 MB (2024, 2025). | State budget economy (plus a few cities and some others; the dataset title mentions municipalities, the `sektori` column should separate them, not yet checked). Confidential purchases are left out, and some rows are anonymised (supplier ID `NA`, name "Salassa pidettävä"). Not the whole public sector. |
| The rest of the public sector's purchases | National procurement data repository, run by the State Treasury | Planned to cover state, municipalities, wellbeing counties and Kela. | Not available yet: state agencies start supplying data in May 2027, municipalities in August 2028. Treat as future work, not a dependency. |
| Tax and other income by source | StatFin, Treasury, Tax Administration statistics | Revenue by tax type. | Tax revenue by type is already in the Treasury budget (main class 11). Tax Administration has open CSVs of public corporate tax data and a PxWeb database (`vero2.stat.fi`), listed but not queried in Phase 0. |

### Not available (say so in the app)
Anything that is not published: confidential purchases, individual-level payments, much of municipal and wellbeing-county spending until the new repository fills up, and pension funds outside the state budget. The app should show this as a visible gap, not hide it.

## Core idea: the coverage meter
Each budget item (or Kela benefit, or COFOG function) shows two numbers: the total, and how much of it is traced to named recipients, categories or suppliers in the data. The rest is shown as "not traced in public data". That is what makes "each euro accounted for" honest, and it is the feature that sets the project apart.

## Architecture
- **Python data pipeline** fetches the sources, cleans them, and writes a unified model plus Parquet files. CI runs it on a schedule, as in the dashboard project.
- **Unified "flow" table:** year, payer (ministry / budget item / Kela), recipient type (benefit category, organisation, company, municipality, other), recipient id (business ID where possible), amount in euros, source dataset, coverage level, source URL.
- **Entity table:** business ID, name, sector, type, for joining grants and invoices to the same organisation (needs the open company register; verify).
- **Static front end, no backend (for now):** Vite + TypeScript on GitHub Pages. Large tables are queried in the browser with DuckDB-WASM over Parquet files. Search suggestions come from a small prebuilt index of entity and budget-item names (a client-side search library). If the files get too big, aggregate at build time (supplier × unit × year × category) and keep row-level data optional.
- **Views:** headline treemap/Sankey by year; drill-down through budget items; benefit comparison (asumistuki vs opintotuki, etc.); organisation and company pages ("everything this entity received, by source"); search results with filters.
- Bilingual EN/FI from the start, as in the dashboard project. The data is mostly Finnish, so names and categories stay Finnish with translations where they exist.
- Design: aim for a clean, restrained look; accessible colours (colour-blind-safe, as in the dashboard), mobile first.

## Phases
Each phase ends with something deployed and usable.

0. **Data recon (time-boxed, first, on the owner's machine in Claude Code so the sources can be reached).** Download a small sample of each source, confirm schemas, licences and the current URLs. Settle the open "verify" items above. Output: a short data inventory in the repo (`docs/data-inventory.md`).
1. **Thin vertical slice.** One path end to end: budget items + Kela asumistuki and opintotuki + a working search bar and year selector, deployed. This proves the architecture before volume. Also settle the chart library.
2. **Top-down view.** COFOG and revenue from StatFin/Eurostat; budget drill-down; the coverage meter.
3. **All Kela benefits.** Month/year/region filters.
4. **Grants.** STEA first (clear data), then the Tutkiavustuksia register and ministry lists. Organisation pages.
5. **Supplier payments.** Invoice data aggregated by supplier; link to organisation pages through business ID. Backend decision point.
6. **Search and filters, properly.** Unified index across budget items, benefits, organisations, companies; suggestions; filters by sector, year range, source.
7. **Polish.** Methodology and "what is not covered" pages, tests, README with sources and licences, case study (how AI was used, what was decided).

## Never cut
Source links for every number, the coverage meter, the methodology page, tests for the data pipeline (especially that totals reconcile with the budget), licence credits (Kela requires attribution).

## Rule carried over from the dashboard
A dataset counts as done only when its source URL, fields and filters are confirmed against the live source, it has a pipeline test, and it has a row in the Sources section. The dashboard's first commit had three wrong dataset codes, so nothing is trusted until it has been checked.

## Risks
- Coverage will never be complete; the plan treats that as a feature to show, not a bug to hide.
- Entity matching (the same organisation under different names or business IDs) will be messy.
- Source formats and URLs change (StatFin did in June 2026); the pipeline needs tests and clear failure messages.
- Data size on static hosting; mitigated by aggregation at build time, with a backend as the fallback.

## Sources
- State Treasury API portal ("Valtion talous v1" and five other APIs), confirmed live in Phase 0: https://avoindata.tutkihallintoa.fi/apis
- State Treasury API base URL used: https://api.tutkihallintoa.fi/valtiontalous/v1/
- Exploreadministration.fi APIs: https://www.exploreadministration.fi/application-program-interfaces/
- State Treasury API info: https://valtiokonttori.fi/en/application-program-interfaces-to-public-sector-data
- Superseded: Open Knowledge Index, Finland budget (2015): https://2015.index.okfn.org/place/finland/budget/
- Superseded: Avoindata.fi, State Treasury budget dataset (only links to netra.fi): https://www.avoindata.fi/data/en_GB/dataset/groups/valtion-budjettitalous
- Company register (PRH YTJ open data API v3): https://avoindata.prh.fi/opendata-ytj-api/v3/companies
- Tax Administration open data: https://www.vero.fi/tietoa-verohallinnosta/tilastot/avoin_dat/
- Tax Administration statistics database (PxWeb): https://vero2.stat.fi/PXWeb/api/v1/fi/Vero
- Tutkiavustuksia (State Treasury grants dashboard): https://www.tutkihallintoa.fi/valtionavustukset/
- STEA grants site: https://avustukset.stea.fi/
- StatFin: https://pxdata.stat.fi/PXWeb/pxweb/en/StatFin/
- Kela open data: https://tietotarjotin.fi/en/open-data
- Kela housing allowance expenditure: https://avoindata.suomi.fi/data/en/dataset/maksetut-yleiset-asumistuet1
- Kela student financial aid: https://avoindata.suomi.fi/data/en/dataset/opintotuen-saajat-ja-maksetut-tuet
- Tutkihankintoja.fi data: https://avoindata.suomi.fi/data/en_GB/dataset/tutkihankintoja-data/resource/5467d131-d495-4e2f-8377-86d3e8e67668
- National procurement data repository (Ministry of Finance): https://valtioneuvosto.fi/-/10623/valtiovarainministerio-valmistelee-avointa-nakymaa-julkisiin-hankintoihin-ja-ostolaskutietoihin
- Rollout timetable: https://www.yrittajat.fi/ajankohtaista/tiedotteet/yrittajat-ja-ek-hankintatietovaranto-avaa-markkinoita-ja-lisaa-luottamusta-julkisiin-ostoihin/
- Discretionary government grants (Ministry of Finance): https://vm.fi/en/discretionary-government-grants
- Tutkiavustuksia presentation, State Treasury (30.9.2025): https://api.hankeikkuna.fi/asiakirjat/07ee9e85-8e51-40f7-a5aa-fed562a7bb2e/ff1539c9-0605-44c7-895d-cfc16e76b97d/LIITE_20260203075853.PDF
- STEA grants 2026: https://valtioneuvosto.fi/-/1271139/sosiaali-ja-terveysalan-jarjestojen-toimintaan-274-miljoonaa-euroa-vuonna-2026
