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
    e = {"benefit": "asumistuki", "year": 2025, "source_url": "https://example.test/x.csv", "resource_id": "r",
         "sha256": "0" * 64, "bytes": 1, "retrieved_at": "2026-11-15", "total_cents": 300,
         "unknown_municipality_cents": 0, "parts": {"elamantilanne": {"a": 100, "b": 200}}, "checks": ["ok"]}
    e.update(over)
    return e


def _write(tmp_path, entries, schema=kela.SNAPSHOT_SCHEMA):
    import json
    p = tmp_path / "kela.json"
    p.write_text(json.dumps({"schema": schema, "entries": entries}), encoding="utf-8")
    return p


def test_snapshot_round_trips(tmp_path):
    k = kela.KelaYear(2025, "asumistuki", 300, {"elamantilanne": {"a": 100, "b": 200}}, -5, ["ok"])
    prov = {"source_url": "u", "resource_id": "r", "sha256": "ab", "bytes": 3, "retrieved_at": "2026-11-15"}
    p = tmp_path / "s" / "kela.json"
    kela.save_snapshot({("asumistuki", 2025): (k, prov)}, p)
    back = kela.load_snapshot(p)[("asumistuki", 2025)]
    assert back == (k, prov)


def test_snapshot_stops_when_parts_do_not_add_up(tmp_path):
    with pytest.raises(AssertionError):
        kela.load_snapshot(_write(tmp_path, [_entry(total_cents=301)]))


def test_snapshot_stops_on_two_entries_for_one_year(tmp_path):
    with pytest.raises(AmbiguousSeries):
        kela.load_snapshot(_write(tmp_path, [_entry(), _entry()]))


def test_snapshot_stops_on_unknown_schema(tmp_path):
    with pytest.raises(ValueError):
        kela.load_snapshot(_write(tmp_path, [_entry()], schema=99))


def test_committed_snapshot_is_valid_and_covers_every_year():
    # The file CI actually reads. A bad edit or a missing year fails here, before any deploy.
    from wimm.build import LINKS, YEARS
    snap = kela.load_snapshot()
    for l in LINKS:
        for y in YEARS:
            assert (l.benefit, y) in snap, f"{l.benefit} {y} missing from snapshots/kela.json"
