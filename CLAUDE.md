# whereismymoney

Open source web app for browsing where Finland's public money comes from and where it goes.

Stack: Python data pipeline (`data-pipeline/`), Vite + TypeScript front end (`web/`), Parquet output, GitHub Pages deploy via GitHub Actions.

Read first: `docs/HANDOFF.md` (state of things, what to do next), then `docs/PLAN.md` (full plan, data inventory, sources).

Rules:
- A dataset is "done" only when its URL, fields and filters are confirmed against the live source, it has a test, and it is in the Sources section.
- The build must fail on ambiguous series (more than one value per key and year).
- Tests (pytest + headless browser) gate every deploy.
- Never fill in missing data; show gaps and the "not traced" share.
- Every number links to its source. Credit Kela (CC BY 4.0).
- EN/FI parity for all UI text.
- Small commits with clear messages.
