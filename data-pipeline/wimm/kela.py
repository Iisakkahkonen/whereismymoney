"""Kela open data: general housing allowance (asumistuki) and student aid.

Source: Kela (Kelasto), CC BY 4.0. See docs/data-inventory.md sections 2 and 3
for how these files were checked. The files are cubes: rollup rows ("Yhteensä")
sit next to their own parts, and several time grains share one file. A plain
sum overcounts by 20 to 36 times, so only the filters below may be summed.

Money is summed in integer cents to keep the cross-checks exact.
"""

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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
    seen: set[int] = set()
    rt_part_names = {"Yksin asuvat", "Lapsettomat parit", "Lapsiperheet yhteensä", "Muut", "Tieto puuttuu"}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["vuosi"] != str(year):
                raise ValueError(f"{path.name}: row for year {r['vuosi']}")
            g = r["aikatyyppi"]
            rt, hm = r["ruokakuntatyyppi"], r["hallintamuoto"]
            if g == "Vuosi":
                key = (r["kunta_nro"], r["ikaryhma"], rt, hm, r["elamantilanne"])
                # Keep a hash, not the tuple: millions of keys as strings do not fit in a small machine's memory.
                # A hash collision can only raise a false alarm (the build stops), never hide a duplicate.
                if hash(key) in seen:
                    raise AmbiguousSeries(f"{path.name}: duplicate yearly row {key}")
                seen.add(hash(key))
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
    seen: set[int] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            g = r["aikatyyppi"]
            if g == "Lukuvuosi":
                continue
            if r["vuosi"] != str(year):
                raise ValueError(f"{path.name}: row for year {r['vuosi']}")
            if g == "Vuosi":
                key = (r["kunta_nro"], r["ikaryhma"], r["sukupuoli"], r["etuus"], r["oppilaitos_peruste"], r["oppilaitosaste"])
                if hash(key) in seen:
                    raise AmbiguousSeries(f"{path.name}: duplicate yearly row {key}")
                seen.add(hash(key))
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


# benefit key -> (dataset id, resource ids per year, cache file prefix, aggregate function)
SOURCES = {
    "asumistuki": (ASUMISTUKI_DATASET, ASUMISTUKI_RESOURCES, "asumistuki", aggregate_asumistuki),
    "opintoraha_ja_asumislisa": (OPINTOTUKI_DATASET, OPINTOTUKI_RESOURCES, "opintotuki", aggregate_opintotuki),
}

# The raw files are 1.5 GB in total, and avoindata.suomi.fi answers 403 to the
# GitHub Actions runners (seen 2026-11-15; the same URL works from a home
# connection). So CI does not download them. The pipeline downloads and
# aggregates on a normal connection (`--kela download`), and the checked
# aggregates are committed here together with where they came from. The build
# reads this file and still reconciles every figure against the Treasury.
SNAPSHOT = Path(__file__).resolve().parent.parent / "snapshots" / "kela.json"
SNAPSHOT_SCHEMA = 1


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def raw_path(benefit: str, year: int, cache: Path) -> Path:
    """Where a raw file is kept. The resource id is in the name, so a changed resource can never
    be mistaken for the old file."""
    _dataset, resources, prefix, _agg = SOURCES[benefit]
    return cache / "kela" / f"{prefix}_{year}_{resources[year]}.csv"


def download_and_aggregate(benefit: str, year: int, cache: Path, refresh: bool = True) -> tuple[KelaYear, dict]:
    """Fetch one raw file, aggregate it, and describe where it came from.

    refresh=True downloads it again. refresh=False re-aggregates the copy on disk (offline), and
    then retrieved_at is that file's date on disk."""
    dataset, resources, _prefix, aggregate = SOURCES[benefit]
    u = url(dataset, resources[year], year)
    p = fetch(u, raw_path(benefit, year, cache), refresh=refresh)
    prov = {
        "source_url": u,
        "resource_id": resources[year],
        "sha256": sha256_of(p),
        "bytes": p.stat().st_size,
        "retrieved_at": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).date().isoformat(),
    }
    return aggregate(p, year), prov


def save_snapshot(entries: dict[tuple[str, int], tuple[KelaYear, dict]], path: Path = SNAPSHOT) -> None:
    rows = []
    for (benefit, year), (k, prov) in sorted(entries.items()):
        rows.append({
            "benefit": benefit, "year": year, **prov,
            "total_cents": k.total_cents,
            "unknown_municipality_cents": k.unknown_municipality_cents,
            "parts": k.parts, "checks": k.checks,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": SNAPSHOT_SCHEMA, "entries": rows}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")


# The breakdowns each benefit must carry. A snapshot that lost one (or all) of them would still
# reconcile on the headline total, so the loader insists on the exact set.
REQUIRED_PARTS = {
    "asumistuki": {"elamantilanne"},
    "opintoraha_ja_asumislisa": {"etuus", "oppilaitosaste"},
}
PROVENANCE_FIELDS = ("source_url", "resource_id", "sha256", "bytes", "retrieved_at")


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _validate_entry(name: str, e: dict) -> None:
    """Shape checks on one snapshot entry. Structural problems raise ValueError."""
    key = (e.get("benefit"), e.get("year"))
    if key[0] not in SOURCES or key[1] not in SOURCES[key[0]][1]:
        raise ValueError(f"{name}: entry for unknown benefit/year {key}")
    for field_name in ("total_cents", "unknown_municipality_cents"):
        if not _is_int(e.get(field_name)):
            raise ValueError(f"{name} {key}: {field_name} must be an integer number of cents")
    if e["total_cents"] <= 0:
        raise ValueError(f"{name} {key}: total_cents must be positive")
    parts = e.get("parts")
    if not isinstance(parts, dict) or set(parts) != REQUIRED_PARTS[key[0]]:
        found = sorted(parts) if isinstance(parts, dict) else parts
        raise ValueError(f"{name} {key}: parts must be exactly {sorted(REQUIRED_PARTS[key[0]])}, found {found}")
    for dim, cats in parts.items():
        if not isinstance(cats, dict) or not cats or not all(_is_int(v) for v in cats.values()):
            raise ValueError(f"{name} {key}: breakdown {dim!r} must be a non-empty map of category to integer cents")
    if not isinstance(e.get("checks"), list) or not e["checks"]:
        raise ValueError(f"{name} {key}: the list of passed checks is missing")
    missing = [f for f in PROVENANCE_FIELDS if f not in e]
    if missing:
        raise ValueError(f"{name} {key}: provenance missing {missing}")
    dataset, resources, _prefix, _agg = SOURCES[key[0]]
    if e["resource_id"] != resources[key[1]] or e["source_url"] != url(dataset, resources[key[1]], key[1]):
        raise ValueError(f"{name} {key}: provenance does not match the resource this pipeline reads")
    if not (isinstance(e["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", e["sha256"])):
        raise ValueError(f"{name} {key}: sha256 is not a 64-character hex digest")
    if not (_is_int(e["bytes"]) and e["bytes"] > 0):
        raise ValueError(f"{name} {key}: bytes must be a positive integer")
    try:
        date.fromisoformat(e["retrieved_at"])
    except (TypeError, ValueError):
        raise ValueError(f"{name} {key}: retrieved_at must be a real ISO date (YYYY-MM-DD)") from None


def load_snapshot(path: Path = SNAPSHOT) -> dict[tuple[str, int], tuple[KelaYear, dict]]:
    """Read the committed aggregates. The shape is validated (required breakdowns present,
    integer cents, provenance matching the pinned resource), and every breakdown must add up
    to the total, so a hand-edited or damaged file fails here instead of reaching the site."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError(f"{path.name}: schema {data.get('schema')}, expected {SNAPSHOT_SCHEMA}")
    out: dict[tuple[str, int], tuple[KelaYear, dict]] = {}
    for e in data["entries"]:
        _validate_entry(path.name, e)
        key = (e["benefit"], e["year"])
        if key in out:
            raise AmbiguousSeries(f"{path.name}: two snapshot entries for {key}")
        k = KelaYear(e["year"], e["benefit"], e["total_cents"], e["parts"], e["unknown_municipality_cents"], e["checks"])
        for dim, cats in k.parts.items():
            _require_equal(f"snapshot {key} {dim} parts vs total", sum(cats.values()), k.total_cents)
        out[key] = (k, {x: e[x] for x in PROVENANCE_FIELDS})
    return out
