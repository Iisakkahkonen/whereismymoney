"""State budget and actuals from the State Treasury API "Valtion talous v1".

Confirmed live 2026-11-15, see docs/data-inventory.md section 1. Facts this
module relies on:
- The API needs at least one classification besides the year, and a time span
  of at most 3 years, so we fetch one main class (paaluokka) and one year at a
  time.
- Rows are per month, account and unit. Summing `Nettokertymä` over every row
  of a momentti and year gives the actual; summing `Voimassaoleva_talousarvio`
  gives the valid budget (original plus supplementary).
- Revenue is stored with a negative sign (credit). Revenue main classes are
  11 to 15, expenditure 21 to 36. We flip revenue so every amount reads as a
  positive flow, and keep a `side` column.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import AmbiguousSeries
from .http import fetch

BASE = "https://api.tutkihallintoa.fi/valtiontalous/v1"
REVENUE_CLASSES = {"11", "12", "13", "15"}

# One raw row is identified by these columns. More than one row per key would
# be an ambiguous series and the build stops.
ROW_KEY = ("Vuosi", "Kk", "Tv_Tunnus", "TakpT_TunnusP", "LkpT_Tunnus")


@dataclass(frozen=True)
class BudgetItem:
    year: int
    momentti: str  # digits only, as the API filter expects, for example "331054"
    code: str  # as printed in the budget, for example "33.10.54."
    name: str
    paaluokka: str  # main class number, for example "33"
    paaluokka_name: str
    hallinnonala: str
    side: str  # "revenue" or "expenditure"
    budget_eur: float
    actual_eur: float


def normalise_name(name: str) -> str:
    """Treasury names switch to ALL CAPS in some years; make them comparable."""
    name = " ".join(name.split())
    return name.capitalize() if name.isupper() else name


def to_euro(x: str) -> float:
    return float(x) if x else 0.0


def list_classes(year: int, cache: Path, refresh: bool = True) -> list[str]:
    """Main class numbers valid in a year, from the API's own structure table."""
    path = fetch(f"{BASE}/paaluokat", cache / "treasury" / "paaluokat.csv", refresh=refresh)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sorted({r["Tunnus"] for r in csv.DictReader(f) if r["Vuosi"] == str(year)})


def fetch_events(paaluokka: str, year: int, cache: Path, refresh: bool = True) -> Path:
    url = f"{BASE}/budjettitaloudentapahtumat?paaluokka={paaluokka}&yearFrom={year}&yearTo={year}"
    return fetch(url, cache / "treasury" / f"events_{year}_{paaluokka}.csv", refresh=refresh)


MONEY_COLUMNS = (
    "Alkuperäinen_talousarvio", "Lisätalousarvio", "Voimassaoleva_talousarvio", "Käytettävissä", "Alkusaldo",
    "Nettokertymä_ko_vuodelta", "NettoKertymaAikVuosSiirrt", "Nettokertymä", "Loppusaldo",
)


def aggregate(path: Path, year: int, notes: list[str] | None = None) -> list[BudgetItem]:
    """Aggregate one main class and year to one row per momentti.

    A repeated raw key stops the build, with one exception: when every amount in
    both rows is zero the repeat changes nothing, so it is dropped and noted.
    Labels may differ between such rows (2025 repeats the same all-zero VAT row
    with the class name in capitals and in lower case). Any repeat that carries
    money stops the build, because we cannot tell whether it double counts.
    """
    seen: dict[tuple, bool] = {}  # raw key -> whether that row was all zero
    dropped: dict[tuple, int] = {}
    acc: dict[str, dict] = defaultdict(lambda: {"budget": 0.0, "actual": 0.0, "names": {}})
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["Vuosi"] != str(year):
                raise ValueError(f"{path.name}: row for year {r['Vuosi']} in a {year} query")
            key = tuple(r[c] for c in ROW_KEY)
            all_zero = all(to_euro(r[c]) == 0.0 for c in MONEY_COLUMNS)
            if key in seen:
                if not (seen[key] and all_zero):
                    raise AmbiguousSeries(f"{path.name}: duplicate raw row {dict(zip(ROW_KEY, key))}")
                dropped[key] = dropped.get(key, 0) + 1
                continue
            seen[key] = all_zero
            a = acc[r["Momentti_TunnusP"]]
            a["budget"] += to_euro(r["Voimassaoleva_talousarvio"])
            a["actual"] += to_euro(r["Nettokertymä"])
            a["names"][int(r["Kk"])] = (r["Momentti_sNimi"], r["Hallinnonala"], r["PaaluokkaOsasto_sNimi"])
            a["paaluokka"] = r["PaaluokkaOsasto_TunnusP"].strip(".")
    if dropped and notes is not None:
        notes.append(f"{path.name}: dropped {sum(dropped.values())} repeated all-zero rows ({len(dropped)} keys), no money affected")
    items = []
    for code, a in acc.items():
        # The same momentti can be renamed within a year; use the latest month.
        name, hallinnonala, pl_name = a["names"][max(a["names"])]
        side = "revenue" if a["paaluokka"] in REVENUE_CLASSES else "expenditure"
        sign = -1.0 if side == "revenue" else 1.0
        items.append(
            BudgetItem(
                year=year,
                momentti=code.replace(".", ""),
                code=code,
                name=normalise_name(name),
                paaluokka=a["paaluokka"],
                paaluokka_name=normalise_name(pl_name),
                hallinnonala=normalise_name(hallinnonala),
                side=side,
                budget_eur=round(sign * a["budget"], 2),
                actual_eur=round(sign * a["actual"], 2),
            )
        )
    return items


def load_year(year: int, cache: Path, notes: list[str] | None = None, refresh: bool = True) -> list[BudgetItem]:
    items: list[BudgetItem] = []
    for pl in list_classes(year, cache, refresh):
        items += aggregate(fetch_events(pl, year, cache, refresh), year, notes)
    seen: set[tuple[int, str]] = set()
    for it in items:
        k = (it.year, it.momentti)
        if k in seen:  # the same momentti under two main classes
            raise AmbiguousSeries(f"momentti {it.momentti} appears twice in {it.year}")
        seen.add(k)
    return items
