"""Kela open data: general housing allowance (asumistuki) and student aid.

Source: Kela (Kelasto), CC BY 4.0. See docs/data-inventory.md sections 2 and 3
for how these files were checked. The files are cubes: rollup rows ("Yhteensä")
sit next to their own parts, and several time grains share one file. A plain
sum overcounts by 20 to 36 times, so only the filters below may be summed.

Money is summed in integer cents to keep the cross-checks exact.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import AmbiguousSeries
from .http import fetch

CKAN_BASE = "https://avoindata.suomi.fi/data/dataset"
ASUMISTUKI_DATASET = "f80f3deb-5742-4fc3-bab9-16e180cfb6c1"
OPINTOTUKI_DATASET = "6c4d12ce-3aaf-40ea-96c4-4e396a959e95"

# Resource ids per year, taken from the CKAN records on 2026-11-15.
ASUMISTUKI_RESOURCES = {
    2021: "452a5e9b-5158-4c46-928a-e019a6d04b49",
    2022: "8738a30b-cf24-4015-9c36-03bfa3a44568",
    2023: "ce012b24-05b2-4301-ac42-1bce5594ff1b",
    2024: "d88904a1-2195-4d67-90eb-01098dd1a0d8",
    2025: "f722f956-7381-4af4-b8a8-161fa63e5e5f",
}
OPINTOTUKI_RESOURCES = {
    2021: "4fce5b8d-e566-40e5-a7cf-3533d5f3c04d",
    2022: "f4168e88-0103-48d2-bebe-26d5543fa450",
    2023: "fb2d2ec7-b370-47e3-bbb6-26f2c1cbde6d",
    2024: "2a0391f0-6afc-4a16-a1c3-f3d5e716000f",
    2025: "169cfdbe-069e-4409-a714-5293a0def420",
}

UNKNOWN_MUNICIPALITY = "199"  # fewer than four recipients, or missing

# Kela's own description pages, used for "every number links to its source".
ASUMISTUKI_PAGE = "https://avoindata.suomi.fi/data/en/dataset/maksetut-yleiset-asumistuet1"
OPINTOTUKI_PAGE = "https://avoindata.suomi.fi/data/en/dataset/opintotuen-saajat-ja-maksetut-tuet"


def url(dataset: str, resource: str, year: int) -> str:
    return f"{CKAN_BASE}/{dataset}/resource/{resource}/download/data_{year}.csv"


@dataclass
class KelaYear:
    """Cents per category, already checked. `total_cents` is the headline figure."""

    year: int
    benefit: str
    total_cents: int = 0
    parts: dict[str, dict[str, int]] = field(default_factory=dict)  # dimension -> category -> cents
    unknown_municipality_cents: int = 0  # net, can be negative because refunds are negative
    checks: list[str] = field(default_factory=list)  # human-readable checks that passed


def cents(x: str) -> int:
    return round(float(x) * 100)


def _require_equal(label: str, a: int, b: int) -> None:
    if a != b:
        raise AssertionError(f"{label}: {a / 100:,.2f} != {b / 100:,.2f}")


def aggregate_asumistuki(path: Path, year: int) -> KelaYear:
    """Total paid housing allowance in a calendar year.

    Filter: ruokakuntatyyppi == "Yhteensä" and hallintamuoto == "Yhteensä",
    summed over age group, life situation and municipality. The same total must
    come out of the yearly, monthly and quarterly rows.
    """
    grain: dict[str, int] = defaultdict(int)
    by_state: dict[str, int] = defaultdict(int)
    rt_parts = 0
    unknown = 0
    seen: set[tuple] = set()
    rt_part_names = {"Yksin asuvat", "Lapsettomat parit", "Lapsiperheet yhteensä", "Muut", "Tieto puuttuu"}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["vuosi"] != str(year):
                raise ValueError(f"{path.name}: row for year {r['vuosi']}")
            g = r["aikatyyppi"]
            rt, hm = r["ruokakuntatyyppi"], r["hallintamuoto"]
            if g == "Vuosi":
                key = (r["kunta_nro"], r["ikaryhma"], rt, hm, r["elamantilanne"])
                if key in seen:
                    raise AmbiguousSeries(f"{path.name}: duplicate yearly row {key}")
                seen.add(key)
            if hm != "Yhteensä":
                continue
            c = cents(r["maksettu_eur"])
            if rt == "Yhteensä":
                grain[g] += c
                if g == "Vuosi":
                    by_state[r["elamantilanne"]] += c
                    if r["kunta_nro"] == UNKNOWN_MUNICIPALITY:
                        unknown += c
            elif g == "Vuosi" and rt in rt_part_names:
                rt_parts += c
    out = KelaYear(year, "asumistuki", total_cents=grain["Vuosi"])
    for g in ("Kuukausi", "Neljännesvuosi"):
        _require_equal(f"asumistuki {year}: {g} total vs yearly total", grain[g], grain["Vuosi"])
    _require_equal(f"asumistuki {year}: household-type parts vs total", rt_parts, grain["Vuosi"])
    _require_equal(f"asumistuki {year}: life-situation parts vs total", sum(by_state.values()), grain["Vuosi"])
    out.parts["elamantilanne"] = dict(by_state)
    out.unknown_municipality_cents = unknown
    out.checks = [
        "yearly, monthly and quarterly rows give the same total",
        "household-type parts add up to the total",
        "life-situation parts add up to the total",
        "no duplicate yearly rows",
    ]
    return out


def aggregate_opintotuki(path: Path, year: int) -> KelaYear:
    """Total paid study grant and housing supplement in a calendar year.

    Filter: etuus == "Opintoraha ja asumislisä yhteensä", oppilaitosaste ==
    "Yhteensä", oppilaitos_peruste == "Kaikki oppilaitokset". Rows with
    aikatyyppi "Lukuvuosi" (academic year, August to July) are excluded: they
    are a different period. The loan guarantee is not a payment and is excluded.
    """
    comb = "Opintoraha ja asumislisä yhteensä"
    grain: dict[str, int] = defaultdict(int)
    by_benefit: dict[str, int] = defaultdict(int)
    by_level: dict[str, int] = defaultdict(int)
    unknown = 0
    seen: set[tuple] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            g = r["aikatyyppi"]
            if g == "Lukuvuosi":
                continue
            if r["vuosi"] != str(year):
                raise ValueError(f"{path.name}: row for year {r['vuosi']}")
            if g == "Vuosi":
                key = (r["kunta_nro"], r["ikaryhma"], r["sukupuoli"], r["etuus"], r["oppilaitos_peruste"], r["oppilaitosaste"])
                if key in seen:
                    raise AmbiguousSeries(f"{path.name}: duplicate yearly row {key}")
                seen.add(key)
            if r["oppilaitos_peruste"] != "Kaikki oppilaitokset":
                continue
            c = cents(r["maksettu_eur"])
            lvl, et = r["oppilaitosaste"], r["etuus"]
            if lvl == "Yhteensä" and et == comb:
                grain[g] += c
                if g == "Vuosi" and r["kunta_nro"] == UNKNOWN_MUNICIPALITY:
                    unknown += c
            if g == "Vuosi":
                if lvl == "Yhteensä" and et in ("Opintoraha", "Asumislisä"):
                    by_benefit[et] += c
                if et == comb and lvl != "Yhteensä":
                    by_level[lvl] += c
    out = KelaYear(year, "opintoraha_ja_asumislisa", total_cents=grain["Vuosi"])
    _require_equal(f"opintotuki {year}: monthly total vs yearly total", grain["Kuukausi"], grain["Vuosi"])
    _require_equal(f"opintotuki {year}: study grant + housing supplement vs total", sum(by_benefit.values()), grain["Vuosi"])
    _require_equal(f"opintotuki {year}: school-level parts vs total", sum(by_level.values()), grain["Vuosi"])
    out.parts["etuus"] = dict(by_benefit)
    out.parts["oppilaitosaste"] = dict(by_level)
    out.unknown_municipality_cents = unknown
    out.checks = [
        "yearly and monthly rows give the same total",
        "study grant plus housing supplement add up to the total",
        "school-level parts add up to the total",
        "no duplicate yearly rows",
    ]
    return out


def load_asumistuki(year: int, cache: Path) -> KelaYear:
    p = fetch(url(ASUMISTUKI_DATASET, ASUMISTUKI_RESOURCES[year], year), cache / "kela" / f"asumistuki_{year}.csv")
    return aggregate_asumistuki(p, year)


def load_opintotuki(year: int, cache: Path) -> KelaYear:
    p = fetch(url(OPINTOTUKI_DATASET, OPINTOTUKI_RESOURCES[year], year), cache / "kela" / f"opintotuki_{year}.csv")
    return aggregate_opintotuki(p, year)
