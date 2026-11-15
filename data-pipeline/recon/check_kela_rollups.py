"""Phase 0 recon: which Kela rows may be summed, and does the result match the state budget?

Kela's open data files are cubes with rollup rows ("Yhteensä") next to their own
parts, and with several time grains in one file. Summing the file naively
double counts by a large factor. This script applies the filters recorded in
docs/data-inventory.md and prints the totals, so the claim can be re-checked.

Standard library only. Usage:
    python -I check_kela_rollups.py asumistuki  data_2024.csv
    python -I check_kela_rollups.py opintotuki  data_2024.csv

Source data: Kela (Kelasto), CC BY 4.0. Download from avoindata.suomi.fi, see
docs/data-inventory.md for the resource URLs.
"""

import csv
import sys
from collections import Counter


def money(row: dict, col: str = "maksettu_eur") -> float:
    return float(row[col] or 0)


def total(rows, predicate, col: str = "maksettu_eur") -> float:
    return round(sum(money(r, col) for r in rows if predicate(r)), 2)


def check_asumistuki(rows: list[dict]) -> None:
    grains = Counter(r["aikatyyppi"] for r in rows)
    print("time grains in file:", dict(grains))
    print(f"naive sum of every row:        {total(rows, lambda r: True):>20,.2f}   <- wrong")
    # ruokakuntatyyppi and hallintamuoto are both rolled up to "Yhteensä";
    # ikaryhma, elamantilanne and kunta are partitions and are summed over.
    for grain in grains:
        t = total(
            rows,
            lambda r, g=grain: r["aikatyyppi"] == g
            and r["ruokakuntatyyppi"] == "Yhteensä"
            and r["hallintamuoto"] == "Yhteensä",
        )
        print(f"{grain:<15} rollup filter:     {t:>20,.2f}")
    parts = (
        "Yksin asuvat",
        "Lapsettomat parit",
        "Lapsiperheet yhteensä",
        "Muut",
        "Tieto puuttuu",
    )
    by_parts = total(
        rows,
        lambda r: r["aikatyyppi"] == "Vuosi"
        and r["hallintamuoto"] == "Yhteensä"
        and r["ruokakuntatyyppi"] in parts,
    )
    print(f"Vuosi, ruokakuntatyyppi parts: {by_parts:>20,.2f}   (must equal the rollup)")
    unknown = total(
        rows,
        lambda r: r["aikatyyppi"] == "Vuosi"
        and r["ruokakuntatyyppi"] == "Yhteensä"
        and r["hallintamuoto"] == "Yhteensä"
        and r["kunta_nro"] == "199",
    )
    print(f"of which municipality 199 (suppressed/unknown, net): {unknown:,.2f}")
    print("negative rows:", sum(1 for r in rows if money(r) < 0))


def check_opintotuki(rows: list[dict]) -> None:
    grains = Counter(r["aikatyyppi"] for r in rows)
    print("time grains in file:", dict(grains))
    print(f"naive sum of every row:        {total(rows, lambda r: True):>20,.2f}   <- wrong")
    for grain in grains:
        for basis in ("Kaikki oppilaitokset", "Viimeisin oppilaitos"):
            t = total(
                rows,
                lambda r, g=grain, b=basis: r["aikatyyppi"] == g
                and r["oppilaitos_peruste"] == b
                and r["oppilaitosaste"] == "Yhteensä"
                and r["etuus"] == "Opintoraha ja asumislisä yhteensä",
            )
            print(f"{grain:<10} {basis:<22} rollup filter: {t:>18,.2f}")
    # Lukuvuosi is the academic year (Aug-Jul), not the calendar year.
    print("note: Lukuvuosi is the academic year; never mix with calendar-year rows.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Finnish labels on a Windows console
    if len(sys.argv) != 3 or sys.argv[1] not in ("asumistuki", "opintotuki"):
        sys.exit(__doc__)
    with open(sys.argv[2], encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows):,} rows")
    {"asumistuki": check_asumistuki, "opintotuki": check_opintotuki}[sys.argv[1]](rows)


if __name__ == "__main__":
    main()
