# Sample data

Small excerpts from the live sources, kept as fixtures for pipeline tests. Fetched 2026-11-15. Not complete datasets; do not use them for numbers.

| File | Source | Licence |
|---|---|---|
| `treasury_331054_asumistuki_2024.csv` | State Treasury API `valtiontalous/v1/budjettitaloudentapahtumat?momentti=331054&yearFrom=2024&yearTo=2024` (full response) | State Treasury open data; the API's own licence is not confirmed, see `docs/data-inventory.md` |
| `treasury_297055_opintoraha_ja_asumislisa_2024.csv` | Same endpoint, `momentti=297055` (full response) | As above |
| `kela_asumistuki_2026_first_rows.csv` | Kela, Maksetut yleiset asumistuet, `data_2026.csv`, first rows | Kela, CC BY 4.0 |
| `kela_opintotuki_2026_first_rows.csv` | Kela, Opintotuen saajat ja maksetut tuet, `data_2026.csv`, first rows | Kela, CC BY 4.0 |
| `tutkihankintoja_2025_first_rows.csv` | Tutkihankintoja.fi data, `th_data_2025.csv`, first rows (semicolon-delimited) | CC BY 4.0, published by Hansel Oy per the CKAN record |
| `stea_2026_first_rows.csv` | STEA open data, `STEA-aineisto.xlsx`, sheet 2026, header and first 8 rows (converted to CSV) | STEA, CC BY 4.0 |

Sources: Kela (Kelasto), licensed CC BY 4.0. STEA (Ministry of Social Affairs and Health), licensed CC BY 4.0.
