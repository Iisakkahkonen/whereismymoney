# whereismymoney: handoff note for the Claude Code session

Written 2026-11-15, from the web chat. Read this first, then `PLAN.md` (the full plan, data inventory and sources).

## Who and what
Iisak Kähkönen is building `whereismymoney`, one of the projects in his Vibecoding Portfolio: a public, open source web app for browsing where Finland's public money comes from and where it goes, as deep as the public data allows (benefits, grants to organisations, payments to companies), with real search and filters. Every portfolio project is independent and has its own repo. It is meant to show employers how he works with AI, so how it was built and what he decided are part of the deliverable. He sets the direction and makes the decisions; Claude does the mechanical work.

## State of things
- Repo: https://github.com/iisakkahkonen/whereismymoney, public, Apache 2.0, Python .gitignore. This commit adds the README stub, `CLAUDE.md`, and these docs.
- Nothing is built. No code, no data, no CI.
- The plan and decisions are in `PLAN.md`. The data research was done in a web chat session that could not reach the sites directly, so no endpoint or file has been tested. Everything marked "verify" in the plan is unchecked.

## Decisions already made
- Web app, usable on any device.
- Stack: Vite + TypeScript, like the Finland vs. EU dashboard. Python pipeline for data.
- No backend at the start; a scheduled CI build precomputes the data, and the browser queries Parquet files (DuckDB-WASM). The owner is open to a backend if it is really needed; revisit at Phase 5 (supplier invoices). Don't build one before then.
- Scope: as broad and low-level as the data allows, state money first. Municipalities and wellbeing counties only where the state sends them money for a specific purpose.
- Year or range selection if possible; otherwise latest data first.
- Looks clean and restrained, bilingual EN/FI, mobile friendly.
- The main feature: a coverage meter on each budget item showing how much is traced to named recipients and how much is "not traced in public data".

## Open choices
- Chart library: Chart.js (used in the dashboard) vs. ECharts or D3 for treemap/Sankey views. Proposal: ECharts for the flow views. Decide in Phase 1.

## What to do first (Phase 0, then Phase 1)
1. **Phase 0, data recon (time-boxed):** from the owner's machine, where the sites can be reached, download a small sample of each source and write down the real schema, licence and current URL in `docs/data-inventory.md`:
   - budjetti.vm.fi budget CSV/XML (link in the plan is from 2015; find the current one via Avoindata.fi)
   - State Treasury APIs (avoindata.tutkihallintoa.fi): budget and actuals
   - Kela open data: general housing allowance expenditure, student financial aid (avoindata.suomi.fi)
   - STEA grants (avustukset.stea.fi) and Tutkiavustuksia.fi: is there bulk data or an API?
   - Tutkihankintoja invoice data (one yearly file is enough for the sample)
   - StatFin tables 12a6, 11zf, 15ah (identifiers changed on 2026-06-08)
   - The open company register, for matching business IDs to organisation names
   - Tax Administration open data on tax revenue
2. **Phase 1, thin vertical slice:** budget items + asumistuki and opintotuki + a working search bar + year selector, tested and deployed to GitHub Pages through Actions. Do this before adding volume.

## Rules to keep (from the dashboard project)
- No dataset counts as done until its URL, fields and filters are confirmed against the live source, it has a pipeline test and a row in the Sources section. The dashboard's first commit had three wrong dataset codes.
- The build must stop if a series is ambiguous (for example more than one value per key and year). That check caught a real bug in the dashboard.
- Tests gate every deploy (pytest for the pipeline, a headless browser test for the UI).
- Never cut: source links for every number, the coverage meter, the methodology and "what is not covered" page, tests that totals reconcile with the budget, licence credits (Kela requires attribution; its data is CC BY 4.0).
- Commit history is part of the case study, so commit in small steps with clear messages.

## Things to be careful about
- Kela data is aggregates only, never individuals, and groups under four people are suppressed. Never try to identify or re-identify anyone.
- Don't fill in missing values or guess recipients; show gaps as gaps.
- Confidential state purchases are not in the invoice data; say so on the page.
- The national procurement repository (all public sector invoices) starts in 2027; it's not a dependency.

## Reporting back
When a phase is done, update the status section of `PLAN.md` (as in the dashboard plan) and tell the owner what changed and what is next. The owner also wants a case study at the end, in the same style as the dashboard's, with a "What I learned" section in his own words.
