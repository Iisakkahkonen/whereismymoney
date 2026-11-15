"""Build every data file the front end needs.

    python -m wimm.build --cache cache --out ../web/public/data

Fetches the sources, runs all checks (the build stops on any failure), and
writes Parquet files plus a manifest and a search index. Nothing is estimated
or filled in: items with no tracing source get a traced amount of zero.
"""

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import kela, treasury
from .coverage import compute_coverage

# Complete calendar years only. 2026 is still running (Kela data to October).
YEARS = [2021, 2022, 2023, 2024, 2025]

# Owner decision 2026-11-15: the gap between the Treasury's actuals and Kela's
# statistics is accepted and shown on the page. Measured 2021 to 2025: student
# aid within 0.6%, housing allowance between -3.4% and +1.3% (the Treasury books
# round transfers, so year-end timing differs). A wrong filter is off by multiples
# (7 to 36 times in Phase 0), so the build fails only beyond this, which would
# point to a wrong filter or a source change, not to ordinary timing.
RECONCILIATION_TOLERANCE = 0.05


@dataclass(frozen=True)
class Link:
    benefit: str  # key used in the kela table
    momentti: str  # Treasury budget item that funds it
    name_fi: str
    name_en: str
    kela_page: str
    keywords: str


LINKS = [
    Link(
        "asumistuki", "331054", "Yleinen asumistuki", "General housing allowance",
        kela.ASUMISTUKI_PAGE, "asumistuki housing allowance housing benefit rent Kela",
    ),
    Link(
        "opintoraha_ja_asumislisa", "297055", "Opintoraha ja asumislisä", "Study grant and housing supplement",
        kela.OPINTOTUKI_PAGE, "opintotuki opintoraha asumislisä student financial aid study grant Kela",
    ),
]


def reconcile(label: str, kela_eur: float, treasury_eur: float) -> float:
    """Signed difference (Kela - Treasury) / Treasury, or stop the build.

    Both linked items are benefits that are paid out, so the Treasury actual must be a finite
    positive number. A zero, negative or missing actual is a source change this guard exists to
    catch; dividing by it would hide the disagreement (a signed denominator can even make a
    200 percent gap look negative and pass)."""
    if not (math.isfinite(treasury_eur) and treasury_eur > 0 and math.isfinite(kela_eur)):
        raise AssertionError(f"{label}: cannot reconcile Kela {kela_eur} with Treasury actual {treasury_eur}; expected a positive Treasury actual")
    diff = (kela_eur - treasury_eur) / treasury_eur
    if abs(diff) > RECONCILIATION_TOLERANCE:
        raise AssertionError(
            f"{label}: Kela {kela_eur:,.0f} vs Treasury {treasury_eur:,.0f} differ by {abs(diff):.1%}, "
            f"more than the accepted {RECONCILIATION_TOLERANCE:.0%}"
        )
    return diff


def check_budget_balances(items: list, years: list[int]) -> None:
    """The adopted state budget always balances (borrowing is a revenue class), so
    summed over every item, revenue must equal expenditure to the euro. This is
    the "totals reconcile with the budget" test: a missing main class, a lost
    page of data or a wrong sign shows up here immediately."""
    for y in years:
        rev = sum(i.budget_eur for i in items if i.year == y and i.side == "revenue")
        exp = sum(i.budget_eur for i in items if i.year == y and i.side == "expenditure")
        if abs(rev - exp) > 1.0:
            raise AssertionError(f"{y}: budget revenue {rev:,.2f} != expenditure {exp:,.2f}")


def search_docs(items: list, links: list) -> list[dict]:
    """One search entry per budget item (latest name) and per benefit.

    A benefit and the budget item that funds it are one result, not two: the
    benefit entry carries the budget item's own name and code as search text,
    and the budget item gets no entry of its own."""
    latest = {}
    for it in sorted(items, key=lambda i: i.year):
        latest[it.momentti] = it
    linked = {l.momentti for l in links}
    docs = [{"id": f"b:{m}", "type": "budget", "title": it.name, "code": it.code, "group": it.hallinnonala,
             "momentti": m, "text": f"{it.name} {it.code} {it.hallinnonala}"} for m, it in latest.items() if m not in linked]
    docs += [{"id": f"k:{l.benefit}", "type": "benefit", "title": l.name_fi, "title_en": l.name_en,
              "code": latest[l.momentti].code, "group": "Kela", "momentti": l.momentti, "benefit": l.benefit,
              "text": f"{l.name_fi} {l.name_en} {l.keywords} {latest[l.momentti].name} {latest[l.momentti].code}"} for l in links]
    return docs


def kela_inputs(mode: str, cache: Path, years: list[int], snapshot: Path) -> dict:
    """Kela figures per (benefit, year), with where each came from.

    "snapshot" reads the committed aggregates (what CI does: the raw files are
    1.5 GB and the host refuses the CI runners). "download" downloads the raw
    files again, re-aggregates, and rewrites the snapshot for the years asked for.
    "recompute" does the same from the copies already on disk, without any request
    (offline); the snapshot then records those files' own dates."""
    wanted = [(l.benefit, y) for l in LINKS for y in years]
    if mode in ("download", "recompute"):
        stored = kela.load_snapshot(snapshot) if snapshot.exists() else {}
        stored.update({key: kela.download_and_aggregate(*key, cache, refresh=(mode == "download")) for key in wanted})
        kela.save_snapshot(stored, snapshot)
        return {key: stored[key] for key in wanted}
    stored = kela.load_snapshot(snapshot)
    missing = [key for key in wanted if key not in stored]
    if missing:
        raise AssertionError(f"Kela snapshot has no data for {missing}; run the build with --kela download on a normal connection")
    return {key: stored[key] for key in wanted}


def build(cache: Path, out: Path, years: list[int], kela_mode: str = "snapshot", snapshot: Path = kela.SNAPSHOT,
          use_cache: bool = False) -> dict:
    """use_cache=True reuses Treasury files already on disk (offline work). The default asks the
    Treasury API for every file, and the manifest says which of the two happened."""
    out.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    items = [it for y in years for it in treasury.load_year(y, cache, notes, refresh=not use_cache)]
    notes.append(
        "Treasury data was reused from files on disk (offline mode); it may not be current."
        if use_cache else "Treasury data was fetched from the Treasury API during this build."
    )
    kela_data = kela_inputs(kela_mode, cache, years, snapshot)
    kela_years = {key: k for key, (k, _) in kela_data.items()}
    kela_files = [{"benefit": b, "year": y, **prov} for (b, y), (_, prov) in sorted(kela_data.items())]
    dates = sorted({f["retrieved_at"] for f in kela_files})
    notes.append(
        f"Kela figures come from {len(kela_files)} source files downloaded {dates[0]}"
        + (f" to {dates[-1]}" if dates[-1] != dates[0] else "")
        + ", aggregated and checked, and stored in data-pipeline/snapshots/kela.json with each file's SHA-256."
    )

    check_budget_balances(items, years)
    actual = {(it.year, it.momentti): it.actual_eur for it in items}
    traced = {}
    reconciliation = []  # published on the sources page: every gap, not only the ones that pass
    for l in LINKS:
        for y in years:
            k = kela_years[(l.benefit, y)]
            a = actual.get((y, l.momentti))
            if a is None:
                raise AssertionError(f"budget item {l.momentti} missing in {y}")
            diff = reconcile(f"{l.benefit} {y}", k.total_cents / 100, a)
            reconciliation.append({"year": y, "benefit": l.benefit, "treasury_eur": a, "kela_eur": k.total_cents / 100,
                                   "difference": diff})
            traced[(y, l.momentti)] = k.total_cents / 100

    cov = {(it.year, it.momentti): compute_coverage(it.actual_eur, traced.get((it.year, it.momentti), 0.0)) for it in items}

    pq.write_table(pa.table({
        "year": pa.array([i.year for i in items], pa.int16()),
        "momentti": [i.momentti for i in items], "code": [i.code for i in items], "name": [i.name for i in items],
        "paaluokka": [i.paaluokka for i in items], "paaluokka_name": [i.paaluokka_name for i in items],
        "hallinnonala": [i.hallinnonala for i in items], "side": [i.side for i in items],
        "budget_eur": [i.budget_eur for i in items], "actual_eur": [i.actual_eur for i in items],
    }), out / "budget_items.parquet", compression="zstd")

    rows = []
    for (benefit, y), k in sorted(kela_years.items()):
        rows.append((y, benefit, "total", "total", k.total_cents / 100))
        rows.append((y, benefit, "unknown_municipality", "net", k.unknown_municipality_cents / 100))
        for dim, cats in k.parts.items():
            rows += [(y, benefit, dim, c, v / 100) for c, v in sorted(cats.items())]
    pq.write_table(pa.table({
        "year": pa.array([r[0] for r in rows], pa.int16()), "benefit": [r[1] for r in rows],
        "dimension": [r[2] for r in rows], "category": [r[3] for r in rows], "paid_eur": [r[4] for r in rows],
    }), out / "kela.parquet", compression="zstd")

    pq.write_table(pa.table({
        "year": pa.array([i.year for i in items], pa.int16()), "momentti": [i.momentti for i in items],
        "actual_eur": [i.actual_eur for i in items],
        "traced_eur": [cov[(i.year, i.momentti)].traced_eur for i in items],
        "untraced_eur": [cov[(i.year, i.momentti)].untraced_eur for i in items],
        "traced_share": [cov[(i.year, i.momentti)].traced_share for i in items],
        "reported_eur": [cov[(i.year, i.momentti)].reported_eur for i in items],
        "note": [cov[(i.year, i.momentti)].note for i in items],
        "source": [next((l.benefit for l in LINKS if l.momentti == i.momentti), "") for i in items],
    }), out / "coverage.parquet", compression="zstd")

    (out / "search_index.json").write_text(json.dumps(search_docs(items, LINKS), ensure_ascii=False), encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "years": years,
        "reconciliation_tolerance": RECONCILIATION_TOLERANCE,
        "reconciliation": reconciliation,
        "benefits": [{"key": l.benefit, "momentti": l.momentti, "name_fi": l.name_fi, "name_en": l.name_en,
                      "source_url": l.kela_page} for l in LINKS],
        "checks": {f"{b} {y}": k.checks for (b, y), k in sorted(kela_years.items())},
        "notes": notes,
        "kela_files": kela_files,
        "sources": [
            {"id": "treasury", "name": "State Treasury, Valtion talous API (budget and actuals)",
             "url": "https://avoindata.tutkihallintoa.fi/apis", "licence": "State Treasury open data (licence to be confirmed)"},
            {"id": "kela", "name": "Kela, open statistics (Kelasto)", "url": kela.ASUMISTUKI_PAGE,
             "licence": "CC BY 4.0", "attribution": "Source: Kela (Kelasto), licensed CC BY 4.0."},
        ],
        "counts": {"budget_items": len(items), "kela_rows": len(rows)},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path("cache"))
    ap.add_argument("--out", type=Path, default=Path("../web/public/data"))
    ap.add_argument("--years", type=int, nargs="+", default=YEARS)
    ap.add_argument("--kela", choices=["snapshot", "download", "recompute"], default="snapshot",
                    help="snapshot: use the committed aggregates (CI). download: download the raw Kela files again "
                         "and refresh the snapshot. recompute: refresh the snapshot from raw files already on disk (offline).")
    ap.add_argument("--use-cache", action="store_true",
                    help="offline mode: reuse Treasury files already in the cache instead of fetching them. "
                         "The default fetches every file, so a normal run is never silently stale.")
    a = ap.parse_args()
    m = build(a.cache, a.out, a.years, a.kela, use_cache=a.use_cache)
    print(f"built {m['counts']} for {m['years']} at {m['generated_at']}")


if __name__ == "__main__":
    main()
