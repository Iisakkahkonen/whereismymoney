# Data inventory (Phase 0 recon)

Checked 2026-11-15 from the owner's machine against the live sources. Everything here was fetched or queried, not read from memory. Two status labels only, because CLAUDE.md says a dataset is "done" only when it also has a pipeline test and a row in the Sources section, and none has yet:

- **confirmed live**: URL, fields and the filter needed were checked against the live source.
- **partial / open**: something is unresolved. The entry says what.

Small fixtures from the live sources are in `data-pipeline/samples/`. The rollup checks below can be re-run with `data-pipeline/recon/check_kela_rollups.py`.

## Summary

| # | Source | Status | Headline |
|---|---|---|---|
| 1 | State budget, Treasury API "Valtion talous" | confirmed live | Open, no key. Replaces the dead budjetti.vm.fi link. Reconciles with Kela to about 1%. |
| 2 | Kela asumistuki | confirmed live | Total checks out against the budget, but only with a strict rollup filter. A naive sum is about 21 times too high. |
| 3 | Kela opintotuki | confirmed live | Same trap. Checks out against the budget to 0.4%. |
| 4 | Tutkihankintoja invoices | confirmed live (sample) | Schema stable 2016 to 2026. Includes municipalities. Confidential suppliers appear as `NA`. |
| 5 | StatFin (12a6, 11zf, 15ah) | confirmed live | PxWeb v1 still works at new paths. Licence not checked. |
| 6 | Company register (PRH YTJ) | partial / open | Works for companies. Coverage of associations and foundations is mixed. |
| 7 | Tax Administration | partial / open | Open CSV and a PxWeb database exist. Neither was queried beyond listing. |
| 8 | STEA grants | partial / open | Public web UI only. No documented bulk file or API. |
| 9 | Tutkiavustuksia register | partial / open | Embedded dashboard only. No documented bulk file or API. |

## Traps that will bite if ignored

1. **Kela files are cubes with rollup rows.** Summing a file gives nonsense. Asumistuki 2024: all rows sum to €35.02 bn, the yearly rows alone to €11.67 bn, the correct total is €1.68 bn. The exact filters are under sources 2 and 3. The build must fail if a key has more than one value (rule from CLAUDE.md); the check for Kela is "rollup filter total equals the sum of its parts".
2. **Several time grains live in one Kela file.** Asumistuki has `Kuukausi`, `Neljännesvuosi`, `Vuosi`. Opintotuki has `Kuukausi`, `Vuosi`, `Lukuvuosi`. They hold the same money at different grains. `Lukuvuosi` is the academic year (August to July) and does not equal the calendar year.
3. **Suppression leaves residue.** Kela groups under four people are folded into municipality `199` / `Tuntematon`. That bucket can net negative (asumistuki 2024: −€42.1 m) because refunds are negative. 29,660 rows in the asumistuki 2024 file are negative. Show it as "not traced to a municipality", never drop or net it away.
4. **CKAN `size` fields are wrong.** Asumistuki 2024 is listed as 17 MB and is 306 MB. Real sizes need `curl -r 0-0 -D -` and the `Content-Range` header. HEAD requests to the download URLs return 403.
5. **Tutkihankintoja is semicolon-delimited** although the resources are labelled TSV or CSV. The `lasku_id` format changed after 2016 (plain number, then `vo|fab|number|unit|date`).
6. **Confidential suppliers do appear** in the invoice data, as supplier ID `NA` and name `Salassa pidettävä`. The plan said they are "left out"; that is only partly true. Count them as "not traced".
7. **Tutkihankintoja includes municipalities** (the dataset is titled "valtion ja kuntien ostolaskut"). Use the `sektori` column to separate state from the rest. The plan assumed state only.
8. **Dead or stale URLs:** `budjetti.vm.fi/indox/opendata/` (404, redirects to the ministry homepage), the PRH v1 company API (404), and the avoindata.fi records for the budget (`valtion-budjettitalous` only links to netra.fi) and the Ministry's budget proposals (last updated 2018). Do not use them.
9. **StatFin paths changed.** Old `statfin_*_pxt_*.px` style paths return 400. The working paths are in source 5.
10. **Treasury `hallinnonalat` has two blank rows** at the top of the CSV.

---

## 1. State budget and actuals: Treasury API "Valtion talous v1"

**Status: confirmed live.**

- Portal: https://avoindata.tutkihallintoa.fi/ (Azure API Management developer portal; the API list loads client-side, so a plain fetch shows nothing). Six APIs: Valtion talous, Tilikartta, Valtion henkilöstö, Kuntatalous, Central government debt, Financing and loans.
- Base URL: `https://api.tutkihallintoa.fi/valtiontalous/v1/`. No key or login needed.
- Endpoints (all return CSV, UTF-8): `budjettitaloudentapahtumat` (transactions), `budjettitaloudentapahtumat-tiedostot` (files, not tried), `hallinnonalat`, `kirjanpitoyksikot`, `luvut`, `momentit`, `paaluokat`, `talousarviokirjanpitotilit`.
- Transactions query parameters: `momentti`, `luku`, `paaluokka`, `takptili`, `tililaji`, `tiliryhma`, `ylatiliryhma`, `tililuokka`, `lkptili`, `hallinnonala`, `tilivirasto`, `monthFrom`, `monthTo`, `yearFrom`, `yearTo`.
- **Constraint:** the time span may be at most 3 years. A call without a year range returns HTTP 400 with `Haun aikajänne saa olla enintään 3 vuotta`, although the portal text says it should return the last three years. The pipeline must request in 3-year windows.
- Transactions columns: `Vuosi, Kk, Ha_Tunnus, Hallinnonala, Tv_Tunnus, Kirjanpitoyksikkö, PaaluokkaOsasto_*, Luku_*, Momentti_*, TakpT_*, Tililuokka_*, Ylatiliryhma_*, Tiliryhma_*, Tililaji_*, LkpT_*, Alkuperäinen_talousarvio, Lisätalousarvio, Voimassaoleva_talousarvio, Käytettävissä, Alkusaldo, Nettokertymä_ko_vuodelta, NettoKertymaAikVuosSiirrt, Nettokertymä, Loppusaldo`.
- **What counts as "actual":** summing `Nettokertymä` over all rows of a momentti and year reconciles with Kela (see below). Rows are per month, account and unit, and monthly figures do not climb over the year, so they are flows, not year-to-date totals. `Alkusaldo` and `Loppusaldo` behave oddly (Loppusaldo equals Nettokertymä from month 2 on) and are **not understood yet; do not use them**. Budget columns (`Alkuperäinen_talousarvio`, `Voimassaoleva_talousarvio`) are filled on only some rows, not every month; sum, do not average.
- Some rows are marked `Tapahtumia: vain talousarviokirjanpidossa` (budget-only rows with no ledger account). Keep them, they carry the budget amount.
- History: queries for 2010, 2015, 2020 and 2024 work. A query for 1998 returned no rows for the test momentti, probably because momentti codes were renumbered. The structure tables (`paaluokat`, `luvut`, `momentit`) only list 2021 to 2026. How far back transactions can be joined to a stable item is open.
- Names change case between years (for example `Verot ja veronluonteiset tulot` until 2024, `VEROT JA VERONLUONTEISET TULOT` from 2025). Normalise before grouping.
- **Reconciliation with Kela, 2024:**

  | Benefit | Treasury momentti | Treasury (sum of Nettokertymä) | Kela (rollup filter) | Gap |
  |---|---|---|---|---|
  | Asumistuki | 331054 | €1,696,100,000 | €1,676,928,570 | +1.1% |
  | Opintoraha ja asumislisä | 297055 | €515,503,552 | €517,674,718 | −0.4% |

  Close but not equal. Likely causes (not verified): payment timing between ledger and Kela's statistics, and Kela statistics counting only some payment types. The reconciliation test in the pipeline needs a tolerance and a written reason, not a silent pass. Note momentti 331054 has no month 12 rows in 2024 and 297055 only has months 1, 3, 5, 7, 8, 10, 12.
- Licence: the avoindata.fi record for the Treasury budget data says CC BY 4.0. The licence of the API itself was not found on the portal pages. Confirm before publishing derived data.
- Fixtures: `data-pipeline/samples/treasury_331054_asumistuki_2024.csv`, `treasury_297055_opintoraha_ja_asumislisa_2024.csv`.

The Ministry of Finance's own budget-proposal data (`valtion-talousarvioesitykset` on avoindata.fi) points to the dead budjetti.vm.fi URL. Not needed: the Treasury API gives the adopted budget plus actuals. Budget proposals are out of scope.

## 2. Kela: paid general housing allowance (asumistuki)

**Status: confirmed live.**

- Dataset: https://avoindata.suomi.fi/data/en/dataset/maksetut-yleiset-asumistuet1 (CKAN API id `maksetut-yleiset-asumistuet1`). Licence CC BY 4.0, maintainer Kela tilastot. Updated monthly by the 20th.
- Files: `data_1994_2005.csv`, `data_2006_2017.csv`, `data_2018.csv` … `data_2026.csv`, plus `package.json` (Frictionless data package with field descriptions and allowed values). Resource URLs are in the CKAN record. Measured sizes: 2024 is 306 MB, 2025 is 226 MB. Other years were not measured, and the CKAN size fields cannot be trusted.
- Columns: `aikatyyppi, kuukausi_nro, vuosikuukausi, vuosi, kunta_nro, kunta_nimi, ikaryhma, ruokakuntatyyppi, hallintamuoto, elamantilanne, maksettu_eur`. **No recipient counts**, only euros.
- Grain: yearly from 1994, monthly and quarterly from January 2018.
- **Correct total (calendar year):** rows where `ruokakuntatyyppi == "Yhteensä"` and `hallintamuoto == "Yhteensä"`, summed over `ikaryhma`, `elamantilanne` and `kunta_nro`. This is identical on all three time grains.
  - 2024: **€1,676,928,570.45** (`Vuosi`, `Kuukausi` and `Neljännesvuosi` all give the same to the cent).
  - The parts add up: the five `ruokakuntatyyppi` parts (`Yksin asuvat`, `Lapsettomat parit`, `Lapsiperheet yhteensä`, `Muut`, `Tieto puuttuu`) at `hallintamuoto == "Yhteensä"` sum to the same figure.
- Hierarchy inside the columns: `ruokakuntatyyppi` has `-Kahden huoltajan perheet` and `-Yhden huoltajan perheet` as children of `Lapsiperheet yhteensä` (leading dash). `hallintamuoto` has `Omistusasunnot yhteensä` and `Vuokra-asunnot yhteensä` over the dashed children. `elamantilanne` is a plain partition with no total row. In the 2024 yearly rows `ikaryhma` has no `Yhteensä` row at all, even though the schema lists one for other years; always sum over age groups and check the partition, do not assume.
- Municipality: `kunta_nro` `199` / `kunta_nimi` `Tuntematon` means fewer than four recipients or missing. `kunta_nimi` holds the number for municipalities that ceased before 2014. Municipality is the municipality at the time of payment.
- No duplicate keys in the 2024 file across the full dimension key.
- Attribution required (CC BY 4.0): credit Kela.
- Fixture: `data-pipeline/samples/kela_asumistuki_2026_first_rows.csv`.
- Check: `python -I data-pipeline/recon/check_kela_rollups.py asumistuki data_2024.csv`.

## 3. Kela: student financial aid (opintotuki)

**Status: confirmed live.**

- Dataset: https://avoindata.suomi.fi/data/en/dataset/opintotuen-saajat-ja-maksetut-tuet (CKAN id `opintotuen-saajat-ja-maksetut-tuet`). CC BY 4.0. Updated monthly by the 20th.
- Files: `data_2005_2017.csv`, `data_2018.csv` … `data_2026.csv`, `package.json`. Measured sizes: 2024 is 113 MB, 2025 is 88 MB.
- Columns: `aikatyyppi, kuukausi_nro, vuosikuukausi, vuosi, kunta_nro, kunta_nimi, ikaryhma, sukupuoli, etuus, oppilaitos_peruste, oppilaitosaste, saaja_lkm, saaja_laskenta_lkm, maksettu_eur, maksettu_laskenta_eur`. This one does have recipient counts.
- Grain: yearly from 2005, monthly from 2018, academic year (`Lukuvuosi`) from 2005/2006.
- **Correct total (calendar year):** `etuus == "Opintoraha ja asumislisä yhteensä"`, `oppilaitosaste == "Yhteensä"`, and either `oppilaitos_peruste` value (they agree at the `Yhteensä` level; they only differ in how the split by school level is assigned). Summed over age, sex and municipality.
  - 2024: **€517,674,718.16**, identical on `Vuosi` and `Kuukausi`. `Lukuvuosi` 2024 rows give €513,106,776.92 (a different period).
  - Parts reconcile: `Opintoraha` €502,755,294.31 plus `Asumislisä` €14,919,423.85 equals the combined figure; the school-level parts add up to it too.
  - Naive sum of the whole file: €18.58 bn, about 36 times too high.
- Use `maksettu_eur`, not `maksettu_laskenta_eur`. Per Kela's field descriptions, `maksettu_eur` is gross money paid with refunds negative; the `_laskenta_` columns exist only to compute the average aid per recipient (regular payments only) and differ a lot.
- `Opintolainan valtiontakaus` (student loan guarantee) shows €0 in `maksettu_eur`: it is not a payment. Exclude it from "money paid".
- Same `199` / `Tuntematon` suppression rule as asumistuki; `Tieto puuttuu` for age and school level. Municipality 199 nets €9.0 m for the 2024 total here.
- No duplicate keys in the 2024 file across the full dimension key.
- Fixture: `data-pipeline/samples/kela_opintotuki_2026_first_rows.csv`.
- Check: `python -I data-pipeline/recon/check_kela_rollups.py opintotuki data_2024.csv`.

## 4. Supplier payments: Tutkihankintoja invoice data

**Status: confirmed live (sample only; no full year analysed).**

- Dataset: https://avoindata.suomi.fi/data/en_GB/dataset/tutkihankintoja-data (CKAN id `tutkihankintoja-data`, title "Tutkihankintoja.fi-palvelun data (valtion ja kuntien ostolaskut)"). CC BY 4.0. Updated 2026-11-10.
- Files: `th_data_2016.csv` … `th_data_2026.csv`, one per year, plus `th_kaannokset.xlsx` (translations, 17 KB, not opened). Measured sizes: 2017 is 272 MB, 2024 is 807 MB, 2025 is 826 MB (other years not measured). The plan's "about 275 MB" held only for early years. A CI download of all years is likely several GB; Parquet output will be much smaller.
- **Format:** semicolon-delimited, UTF-8, one header row, even for files labelled TSV. Same 13 columns in 2016, 2022, 2024, 2025 and 2026: `lasku_id;tili;tiliointisumma;tositepvm;toimittaja_y_tunnus;toimittaja_nimi;hankintayksikko_tunnus;hankintayksikko;ylaorganisaatio_tunnus;ylaorganisaatio;sektori;tuote_palveluryhma;hankintakategoria`.
- One row per accounting row, not per invoice. `lasku_id` is not unique across rows. `tili` is an account code plus name in one field. `tiliointisumma` can be negative (credit notes, for example −1170.0 for a Pfizer row in 2026).
- `toimittaja_y_tunnus` is the supplier business ID. `NA` appears together with `toimittaja_nimi = Salassa pidettävä` for confidential purchases. Count such rows as "not traced".
- `sektori` is `Valtio` in the sample rows; the dataset title says municipalities are included. Which other values exist and how much money they hold was **not** checked. `ylaorganisaatio` is the administrative branch (hallinnonala), `hankintayksikko` the agency.
- Open: totals per year, share with `NA` supplier IDs, share of rows with a business ID, and whether yearly totals can be tied to the budget.
- Fixture: `data-pipeline/samples/tutkihankintoja_2025_first_rows.csv`.

## 5. Statistics Finland StatFin (PxWeb API v1)

**Status: confirmed live.**

- API root: `https://pxdata.stat.fi/PXWeb/api/v1/en/StatFin`. All calls here were made with a browser-like `User-Agent` header; behaviour without one was not tested. A PxWeb API v2 path under `/PXWeb/api/v2/` returns 404, so v1 is the live version. Guessed table paths (for example `/jtt/statfin_jtt_pxt_12a6.px`) return HTTP 400; take paths from the tree listing.
- Tables, with paths relative to the root:

  | Table | Path | Content | Range |
  |---|---|---|---|
  | 12a6 | `/jmete/12a6.px` | General government expenditure by function (COFOG), annual | 1990 to 2024* |
  | 11zf | `/jtume/11zf.px` | General government revenue and expenditure, quarterly | 1999Q1 to 2026Q2* |
  | 15ah | `/ntp/15ah.px` | ANA general government revenue and expenditure, annual | 1975 to 2025* |

- 12a6 variables: `sektoriluokitus_7_20230101` (sector, 8 values from `S13`), `taloustoimi_1_20180101` (transaction, 23 values), `julkisyht_teht_3_20010101` (function, 80 values from `SSS`, `G01`…; eliminable), `timeperiod_y`, `contentscode` (`jmete-cp`, `jmete-bkt_suhde`, `percapita`). A JSON-stat2 data query worked and returned a table with a stated update time of 2025-12-18.
- 11zf: `timeperiod_q`, `taloustoimi_1_20180101` (73), `sektoriluokitus_7_20230101` (7), `contentscode` (7). 15ah: sector (7), transaction (90), `timeperiod_y`, `contentscode` (2).
- The 2026-06-08 identifier change in the plan is consistent with what was found (the variable codes carry date suffixes such as `_20230101`). Code and value lists above are today's. A pipeline test must fail loudly if they change.
- The asterisk on the latest year in the table titles marks preliminary data.
- Not done: Eurostat `gov_10a_exp` (not part of this recon), the 2023 break from wellbeing services counties (stated by the plan, not re-checked), and the **licence** (Statistics Finland's open data licence is expected to be CC BY 4.0, but it was not confirmed on a live page).

## 6. Company register: PRH YTJ open data

**Status: partial / open.**

- Live API: `https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=<id>` or `?name=<text>`. Returns JSON with `businessId`, `names` (with history), `companyForms` and more. No key. The old v1 API (`/bis/v1/<id>`) returns 404.
- The avoindata.fi record (`yritykset`, CC BY 4.0, updated daily per its notes) describes a bulk JSON file, but the CKAN record lists **no downloadable resources**; the notes only point to avoindata.prh.fi. Bulk access is unresolved.
- The record's text says it covers trade-register forms and excludes sole traders. Coverage tests were mixed:
  - Found: `2238370-0` (Oy), `0645278-8` (Oy), and by name `MIELI Suomen Mielenterveys ry` (`0202225-4`), which is an association.
  - Not found: business ID `0214391-0` (an `ry` from the 2016 invoice sample, possibly dissolved), and by name `Suomen Punainen Risti` and `Takuusäätiö`, both large grant recipients.
- Conclusion: usable for companies. For associations and foundations, which dominate the grants data, matching is unproven. Needs a test with a batch of real grant recipients before Phase 4. The association and foundation registers are separate and may need their own source.

## 7. Tax Administration (Vero)

**Status: partial / open.**

- Open data page: https://www.vero.fi/tietoa-verohallinnosta/tilastot/avoin_dat/ (CC BY 4.0). CSV files of public corporate income tax data per tax year, 2020 to 2025 (about 23 to 27 MB each), plus a changed-assessment list from tax year 2022. The avoindata.fi record for the same data (`yhteisojen-tuloverotuksen-julkiset-tiedot`) is stale (2011 to 2014 files).
- Tax revenue development: statistics database with a PxWeb API at `https://vero2.stat.fi/PXWeb/api/v1/fi/Vero` (works; the English tree is under `/en/Vero`), with folders including `Verotulojen_kehitys`, `Arvonlisavero`, `Valmistevero`, `Autovero`, `Tulorekisteri`. **Not queried below the folder list.**
- Not needed as a dependency for a first version: the state's tax revenue by type is already in the Treasury budget (main class 11 "Verot ja veronluonteiset tulot", from the `paaluokat` and transactions endpoints). Vero's own figures could cross-check it. Vero collects some taxes for others and not all state taxes (for example vehicle tax is collected by Traficom), so the two will not match exactly.
- Corporate tax public data is per company, which is relevant to "where the money comes from" at company level. Whether to use it is a scope decision for the owner.

## 8. STEA grants

**Status: partial / open. Not resolved.**

- Public site: https://avustukset.stea.fi/ (a JavaScript app). Visited as a normal user. For 2026 it shows 766 organisations, 1,527 grant targets, €447,993,335 applied for, **€273,912,000 granted**, with per-organisation applied/granted amounts and number of targets. Years 2017 to 2026 are selectable. The plan said "about €274 m to 686 organisations"; the money matches and the organisation count on the live page is 766.
- No download or export button and no mention of an open API were found on the pages. No business ID is shown in the list, only organisation names.
- The page's own configuration contains a backend API address. **Probing it was blocked in this session and was not retried.** It is not documented as a public API, so it is not recorded here. Options for the owner: ask STEA whether a bulk file or API is offered, check their terms for reuse, or decide whether collecting the table from the public pages is acceptable.
- No matching national dataset exists on avoindata.fi (searches for `valtionavustus`, `stea`, `tutkiavustuksia` returned nothing relevant). The avustus search only finds municipal grant lists (Helsinki, Oulu), which are out of scope for a first release.

## 9. Tutkiavustuksia (State Treasury grants register)

**Status: partial / open.**

- https://tutkiavustuksia.fi/ redirects to https://www.tutkihallintoa.fi/valtionavustukset/. It is a dashboard with embedded reports, not a data download.
- The data comes from the grant authorities' legal duty to report applications and decisions within 3 months (Finlex 2022/1394), so it fills in gradually and recent months are incomplete. The page shows grant totals by recipient type (public bodies about €1.52 bn, companies about €1.30 bn, non-profits about €1.14 bn, others €0.20 bn), top grantors for 2026 (Business Finland €530 m, Research Council of Finland €305 m, Ministry of Education and Culture €276 m) and top recipients (VTT €255 m, University of Helsinki €119 m, Aalto €75 m).
- A second report covers grants to non-profit communities from the **state ledger**, using accounts `82510000` (operating) and `82580000` (capital), "voittoa tavoittelemattomat yhteisöt". Ledger account 82510000 style codes also appear in the Treasury transactions API (`LkpT_*` columns); whether that gives a cross-check by account is untested.
- No bulk file, API or export was found, and the Treasury API portal's six APIs do not include grants.
- Open: ask the Treasury whether grant decisions are published as open data, and what recipient identifiers (business ID) are available.

---

## Decisions this recon needs from the owner

1. **STEA and Tutkiavustuksia (Phase 4):** neither shows a documented bulk file or API. Do we ask the two organisations, or decide on page-level collection, or park grants?
2. **Municipal invoices:** Tutkihankintoja includes municipalities. Include them as a recipient/payer category (the plan said municipalities are out except as state-transfer recipients), or filter to `sektori = Valtio`?
3. **Reconciliation tolerance:** the Treasury and Kela totals differ by about 1%. Accept a stated tolerance with a written reason?

## What it means for Phase 1

- The budget side is straightforward: Treasury API, 3-year request windows, `Nettokertymä` summed per momentti and year.
- Kela files are 100 to 300 MB per year but only a few rollup rows are needed. Download once, filter by the exact rollup rules above, and store the aggregate as Parquet. Do not ship raw files.
- The pipeline needs these checks from day one: rollup equals the sum of parts, one value per key and year, and a Kela-to-budget tolerance test using momentti 331054 and 297055.
