"""Kela rollup rules, tested on tiny files whose correct answer is known by hand.

The traps these guard against were found in Phase 0 (docs/data-inventory.md):
rollup rows next to their parts, several time grains in one file, and
suppressed municipalities that net negative.
"""

import csv

import pytest

from wimm import AmbiguousSeries, kela

ASU_COLS = ["aikatyyppi", "kuukausi_nro", "vuosikuukausi", "vuosi", "kunta_nro", "kunta_nimi", "ikaryhma",
            "ruokakuntatyyppi", "hallintamuoto", "elamantilanne", "maksettu_eur"]
OPI_COLS = ["aikatyyppi", "kuukausi_nro", "vuosikuukausi", "vuosi", "kunta_nro", "kunta_nimi", "ikaryhma", "sukupuoli",
            "etuus", "oppilaitos_peruste", "oppilaitosaste", "saaja_lkm", "saaja_laskenta_lkm", "maksettu_eur",
            "maksettu_laskenta_eur"]


def write(path, cols, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return path


def asu(grain, kunta, age, rt, hm, state, eur, year=2024):
    return [grain, 12, f"{year}12", year, kunta, "x", age, rt, hm, state, eur]


def good_asumistuki_rows():
    """100.00 euros paid in total: 60 to singles in municipality 091, 40 to families in 199 (suppressed)."""
    rows = []
    for grain in ("Vuosi", "Kuukausi", "Neljännesvuosi"):
        rows += [
            asu(grain, "091", "25-29", "Yhteensä", "Yhteensä", "Muut ruokakunnat", "60.00"),
            asu(grain, "199", "30-34", "Yhteensä", "Yhteensä", "Muut ruokakunnat", "40.00"),
        ]
    # parts of the household type, only on the yearly grain, and a tenure split that must not be added
    rows += [
        asu("Vuosi", "091", "25-29", "Yksin asuvat", "Yhteensä", "Muut ruokakunnat", "60.00"),
        asu("Vuosi", "199", "30-34", "Lapsiperheet yhteensä", "Yhteensä", "Muut ruokakunnat", "40.00"),
        asu("Vuosi", "091", "25-29", "Yhteensä", "Vuokra-asunnot yhteensä", "Muut ruokakunnat", "55.00"),
        asu("Vuosi", "199", "30-34", "-Yhden huoltajan perheet", "Yhteensä", "Muut ruokakunnat", "25.00"),  # child of a part
    ]
    return rows


def test_asumistuki_uses_only_the_rollup_rows(tmp_path):
    p = write(tmp_path / "a.csv", ASU_COLS, good_asumistuki_rows())
    k = kela.aggregate_asumistuki(p, 2024)
    # A naive sum of the file would be several times 100.00.
    assert k.total_cents == 10_000
    assert k.unknown_municipality_cents == 4_000
    assert k.parts["elamantilanne"] == {"Muut ruokakunnat": 10_000}


def test_asumistuki_stops_when_grains_disagree(tmp_path):
    rows = good_asumistuki_rows()
    rows[2][-1] = "61.00"  # one monthly row off by a euro
    with pytest.raises(AssertionError, match="Kuukausi"):
        kela.aggregate_asumistuki(write(tmp_path / "a.csv", ASU_COLS, rows), 2024)


def test_asumistuki_stops_when_parts_do_not_add_up(tmp_path):
    rows = good_asumistuki_rows()
    rows = [r for r in rows if r[7] != "Lapsiperheet yhteensä"]  # a missing part
    with pytest.raises(AssertionError, match="household-type"):
        kela.aggregate_asumistuki(write(tmp_path / "a.csv", ASU_COLS, rows), 2024)


def test_asumistuki_stops_on_a_duplicate_yearly_row(tmp_path):
    rows = good_asumistuki_rows()
    rows.append(list(rows[0]))
    with pytest.raises(AmbiguousSeries):
        kela.aggregate_asumistuki(write(tmp_path / "a.csv", ASU_COLS, rows), 2024)


def opi(grain, kunta, benefit, level, eur, basis="Kaikki oppilaitokset", year=2024):
    return [grain, 12, f"{year}12", year, kunta, "x", "20-24", "Nainen", benefit, basis, level, 1, 1, eur, eur]


def good_opintotuki_rows():
    """Study grant 90.00 + housing supplement 10.00 = 100.00, split over two school levels."""
    comb = "Opintoraha ja asumislisä yhteensä"
    rows = []
    for grain in ("Vuosi", "Kuukausi"):
        rows += [opi(grain, "091", comb, "Yhteensä", "100.00")]
    rows += [
        opi("Vuosi", "091", "Opintoraha", "Yhteensä", "90.00"),
        opi("Vuosi", "091", "Asumislisä", "Yhteensä", "10.00"),
        opi("Vuosi", "091", comb, "Yliopistot", "70.00"),
        opi("Vuosi", "091", comb, "Lukiot", "30.00"),
        opi("Vuosi", "091", "Opintolainan valtiontakaus", "Yhteensä", "0.00"),
        # same money again on the other basis, and an academic-year row: neither may be added
        opi("Vuosi", "091", comb, "Yhteensä", "100.00", basis="Viimeisin oppilaitos"),
        opi("Lukuvuosi", "091", comb, "Yhteensä", "95.00"),
    ]
    return rows


def test_opintotuki_uses_only_the_rollup_rows(tmp_path):
    p = write(tmp_path / "o.csv", OPI_COLS, good_opintotuki_rows())
    k = kela.aggregate_opintotuki(p, 2024)
    assert k.total_cents == 10_000
    assert k.parts["etuus"] == {"Opintoraha": 9_000, "Asumislisä": 1_000}
    assert k.parts["oppilaitosaste"] == {"Yliopistot": 7_000, "Lukiot": 3_000}


def test_opintotuki_stops_when_school_levels_do_not_add_up(tmp_path):
    rows = [r for r in good_opintotuki_rows() if r[10] != "Lukiot"]
    with pytest.raises(AssertionError, match="school-level"):
        kela.aggregate_opintotuki(write(tmp_path / "o.csv", OPI_COLS, rows), 2024)


def test_opintotuki_stops_on_a_duplicate_yearly_row(tmp_path):
    rows = good_opintotuki_rows()
    rows.append(list(rows[0]))
    with pytest.raises(AmbiguousSeries):
        kela.aggregate_opintotuki(write(tmp_path / "o.csv", OPI_COLS, rows), 2024)


# --- committed snapshot (CI cannot download the raw files) -------------------

def _entry(**over):
    rid = kela.ASUMISTUKI_RESOURCES[2025]
    e = {"benefit": "asumistuki", "year": 2025, "source_url": kela.url(kela.ASUMISTUKI_DATASET, rid, 2025), "resource_id": rid,
         "sha256": "ab" * 32, "bytes": 1, "retrieved_at": "2026-11-15", "total_cents": 300,
         "unknown_municipality_cents": 0, "parts": {"elamantilanne": {"a": 100, "b": 200}}, "checks": ["ok"]}
    e.update(over)
    return e


def _write(tmp_path, entries, schema=kela.SNAPSHOT_SCHEMA):
    import json
    p = tmp_path / "kela.json"
    p.write_text(json.dumps({"schema": schema, "entries": entries}), encoding="utf-8")
    return p


def test_snapshot_round_trips(tmp_path):
    e = _entry()
    k = kela.KelaYear(2025, "asumistuki", 300, e["parts"], 0, ["ok"])
    prov = {f: e[f] for f in kela.PROVENANCE_FIELDS}
    p = tmp_path / "s" / "kela.json"
    kela.save_snapshot({("asumistuki", 2025): (k, prov)}, p)
    assert kela.load_snapshot(p)[("asumistuki", 2025)] == (k, prov)


def test_snapshot_stops_when_parts_do_not_add_up(tmp_path):
    with pytest.raises(AssertionError):
        kela.load_snapshot(_write(tmp_path, [_entry(total_cents=301)]))


def test_snapshot_stops_on_two_entries_for_one_year(tmp_path):
    with pytest.raises(AmbiguousSeries):
        kela.load_snapshot(_write(tmp_path, [_entry(), _entry()]))


def test_snapshot_stops_on_unknown_schema(tmp_path):
    with pytest.raises(ValueError):
        kela.load_snapshot(_write(tmp_path, [_entry()], schema=99))


@pytest.mark.parametrize("over", [
    {"parts": {}},  # every partition check used to be skipped for an empty parts map
    {"parts": {"elamantilanne": {}}},
    {"parts": {"elamantilanne": {"a": 300}, "extra": {"x": 300}}},  # unsupported breakdown
    {"parts": {"elamantilanne": {"a": 150.0, "b": 150.0}}},  # not integer cents
    {"total_cents": 0, "parts": {"elamantilanne": {"a": 0}}},
    {"total_cents": 300.0},
    {"unknown_municipality_cents": "0"},
    {"checks": []},
    {"benefit": "unknown_benefit"},
    {"year": 1999},
    {"sha256": "xyz"},
    {"bytes": 0},
    {"retrieved_at": "yesterday"},
    {"resource_id": "some-other-resource"},
    {"source_url": "https://example.test/x.csv"},
])
def test_snapshot_rejects_a_malformed_entry(tmp_path, over):
    with pytest.raises(ValueError):
        kela.load_snapshot(_write(tmp_path, [_entry(**over)]))


def test_snapshot_rejects_a_missing_provenance_field(tmp_path):
    e = _entry()
    del e["sha256"]
    with pytest.raises(ValueError, match="provenance missing"):
        kela.load_snapshot(_write(tmp_path, [e]))


def test_student_aid_snapshot_needs_both_breakdowns(tmp_path):
    rid = kela.OPINTOTUKI_RESOURCES[2025]
    base = {"benefit": "opintoraha_ja_asumislisa", "year": 2025, "resource_id": rid,
            "source_url": kela.url(kela.OPINTOTUKI_DATASET, rid, 2025)}
    both = {"etuus": {"a": 100, "b": 200}, "oppilaitosaste": {"x": 300}}
    kela.load_snapshot(_write(tmp_path, [_entry(**base, parts=both)]))  # valid
    for drop in both:
        parts = {d: c for d, c in both.items() if d != drop}
        with pytest.raises(ValueError, match="parts must be exactly"):
            kela.load_snapshot(_write(tmp_path, [_entry(**base, parts=parts)]))


def test_removing_any_breakdown_from_the_committed_snapshot_fails_the_loader(tmp_path):
    # Mutate the committed file itself: removing any one required breakdown must fail the loader.
    import json
    data = json.loads(kela.SNAPSHOT.read_text(encoding="utf-8"))
    for i, e in enumerate(data["entries"]):
        for dim in e["parts"]:
            broken = json.loads(json.dumps(data))
            del broken["entries"][i]["parts"][dim]
            p = tmp_path / f"broken_{i}_{dim}.json"
            p.write_text(json.dumps(broken), encoding="utf-8")
            with pytest.raises(ValueError, match="parts must be exactly"):
                kela.load_snapshot(p)


def test_committed_snapshot_is_valid_and_covers_every_year():
    # The file CI actually reads. A bad edit or a missing year fails here, before any deploy.
    from wimm.build import LINKS, YEARS
    snap = kela.load_snapshot()
    for l in LINKS:
        for y in YEARS:
            assert (l.benefit, y) in snap, f"{l.benefit} {y} missing from snapshots/kela.json"
