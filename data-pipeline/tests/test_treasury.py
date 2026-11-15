import csv
from pathlib import Path

import pytest

from wimm import AmbiguousSeries, treasury

SAMPLES = Path(__file__).parent.parent / "samples"


def raw_sum(path: Path, column: str) -> float:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(float(r[column] or 0) for r in csv.DictReader(f))


def test_asumistuki_item_matches_raw_rows():
    path = SAMPLES / "treasury_331054_asumistuki_2024.csv"
    (item,) = treasury.aggregate(path, 2024)
    assert item.momentti == "331054"
    assert item.code == "33.10.54."
    assert item.side == "expenditure"
    # Independent re-sum of the raw rows, and the figures confirmed in Phase 0.
    assert item.actual_eur == pytest.approx(raw_sum(path, "Nettokertymä"))
    assert item.actual_eur == pytest.approx(1_696_100_000.0)
    assert item.budget_eur == pytest.approx(1_738_900_000.0)


def test_revenue_is_flipped_to_a_positive_flow():
    path = SAMPLES / "treasury_110401_vat_2024.csv"
    (item,) = treasury.aggregate(path, 2024)
    assert item.side == "revenue"
    assert item.paaluokka == "11"
    # The API stores revenue as a credit (negative). We show it as positive.
    assert raw_sum(path, "Nettokertymä") < 0
    assert item.actual_eur == pytest.approx(-raw_sum(path, "Nettokertymä"))
    assert item.actual_eur > 0


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines()


def row_with_money(lines: list[str]) -> str:
    """A data line whose Nettokertymä is not zero (the second-to-last column)."""
    return next(l for l in lines[1:] if float(next(csv.reader([l]))[-2] or 0) != 0.0)


def test_repeated_row_with_money_stops_the_build(tmp_path):
    lines = lines_of(SAMPLES / "treasury_331054_asumistuki_2024.csv")
    dup = tmp_path / "dup.csv"
    dup.write_text("\n".join(lines + [row_with_money(lines)]) + "\n", encoding="utf-8")
    with pytest.raises(AmbiguousSeries):
        treasury.aggregate(dup, 2024)


def test_all_zero_repeat_is_dropped_even_if_a_label_differs(tmp_path):
    with open(SAMPLES / "treasury_331054_asumistuki_2024.csv", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    zero = dict(rows[0], TakpT_TunnusP="33.10.54.99.", LkpT_Tunnus="")
    for col in treasury.MONEY_COLUMNS:
        zero[col] = "0.00"
    shouting = dict(zero, PaaluokkaOsasto_sNimi=zero["PaaluokkaOsasto_sNimi"].upper())  # the 2025 pattern
    path = tmp_path / "zero_dup_label.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows + [zero, shouting])
    (item,) = treasury.aggregate(path, 2024)
    assert item.actual_eur == pytest.approx(1_696_100_000.0)


def test_a_zero_row_repeated_with_a_money_row_is_ambiguous(tmp_path):
    with open(SAMPLES / "treasury_331054_asumistuki_2024.csv", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    zero = dict(rows[0], TakpT_TunnusP="33.10.54.99.", LkpT_Tunnus="")
    for col in treasury.MONEY_COLUMNS:
        zero[col] = "0.00"
    with_money = dict(zero, Nettokertymä="5.00")
    path = tmp_path / "conflict.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows + [zero, with_money])
    with pytest.raises(AmbiguousSeries):
        treasury.aggregate(path, 2024)


def test_identical_all_zero_repeat_is_dropped_and_reported(tmp_path):
    with open(SAMPLES / "treasury_331054_asumistuki_2024.csv", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    zero = dict(rows[0], TakpT_TunnusP="33.10.54.99.", LkpT_Tunnus="")  # a new account, like the real case
    for col in treasury.MONEY_COLUMNS:
        zero[col] = "0.00"
    path = tmp_path / "zero_dup.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows + [zero, zero])
    notes: list[str] = []
    (item,) = treasury.aggregate(path, 2024, notes)
    assert item.actual_eur == pytest.approx(1_696_100_000.0)  # unchanged by the repeat
    assert len(notes) == 1 and "repeated all-zero" in notes[0]


def test_wrong_year_is_rejected():
    with pytest.raises(ValueError):
        treasury.aggregate(SAMPLES / "treasury_331054_asumistuki_2024.csv", 2023)


def test_all_caps_names_are_normalised():
    assert treasury.normalise_name("SOSIAALI- JA TERVEYSMINISTERIÖN HALLINNONALA") == "Sosiaali- ja terveysministeriön hallinnonala"
    assert treasury.normalise_name("Sosiaali- ja terveysministeriön hallinnonala") == "Sosiaali- ja terveysministeriön hallinnonala"
