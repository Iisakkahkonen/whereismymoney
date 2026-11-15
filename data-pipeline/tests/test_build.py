import pytest

from wimm import build, coverage, treasury


def item(year, momentti, side, budget):
    return treasury.BudgetItem(year, momentti, momentti, "x", "11", "x", "x", side, budget, budget)


def test_balanced_budget_passes():
    build.check_budget_balances([item(2024, "1", "revenue", 100.0), item(2024, "2", "expenditure", 100.0)], [2024])


def test_unbalanced_budget_stops_the_build():
    # A lost main class would show up exactly like this.
    with pytest.raises(AssertionError, match="2024"):
        build.check_budget_balances([item(2024, "1", "revenue", 100.0), item(2024, "2", "expenditure", 60.0)], [2024])


def test_every_linked_item_is_a_known_budget_item_code():
    # Links are matched on the digits-only code the API filters on.
    assert {l.momentti for l in build.LINKS} == {"331054", "297055"}
    assert all(m.isdigit() and len(m) == 6 for m in (l.momentti for l in build.LINKS))


def test_a_benefit_and_its_budget_item_are_one_search_result():
    link = build.LINKS[0]  # asumistuki, funded by momentti 331054
    items = [item(2024, link.momentti, "expenditure", 1.0), item(2024, "999999", "expenditure", 1.0)]
    docs = build.search_docs(items, [link])
    assert [d["id"] for d in docs] == ["b:999999", f"k:{link.benefit}"]
    benefit = docs[1]
    assert benefit["momentti"] == link.momentti
    assert "housing allowance" in benefit["text"].lower() and "asumistuki" in benefit["text"].lower()


def test_item_without_a_source_is_entirely_untraced():
    c = coverage.compute_coverage(1_000_000.0, 0.0)
    assert c.traced_eur == 0.0
    assert c.untraced_eur == 1_000_000.0
    assert c.traced_share == 0.0


def test_traced_part_below_actual_leaves_the_difference_untraced():
    c = coverage.compute_coverage(1_696_100_000.0, 1_676_928_570.45)
    assert c.traced_eur == pytest.approx(1_676_928_570.45)
    assert c.untraced_eur == pytest.approx(19_171_429.55)
    assert c.traced_share == pytest.approx(0.9887, abs=1e-4)
    assert c.note == ""


def test_source_above_actual_is_capped_flagged_and_still_reported():
    # 2025 housing allowance: Kela paid more than the Treasury booked.
    c = coverage.compute_coverage(1_212_431_733.0, 1_227_965_673.0)
    assert c.traced_eur == pytest.approx(1_212_431_733.0)  # never above the actual
    assert c.untraced_eur == 0.0  # never negative
    assert c.traced_share == 1.0
    assert c.reported_eur == pytest.approx(1_227_965_673.0)  # the source's own figure is kept
    assert c.note == "traced_exceeds_actual"


def test_negative_source_figure_is_kept_with_its_sign_and_traces_nothing():
    c = coverage.compute_coverage(100.0, -5.0)
    assert c.reported_eur == -5.0  # not clamped to zero
    assert (c.traced_eur, c.traced_share) == (0.0, 0.0)
    assert c.untraced_eur == 100.0
    assert c.note == "source_negative"


@pytest.mark.parametrize("actual,reported", [(float("nan"), 1.0), (1.0, float("inf")), (float("inf"), 1.0)])
def test_coverage_rejects_amounts_that_are_not_finite(actual, reported):
    with pytest.raises(ValueError):
        coverage.compute_coverage(actual, reported)


@pytest.mark.parametrize("actual", [0.0, -5.0])
def test_non_positive_actual_traces_nothing(actual):
    c = coverage.compute_coverage(actual, 100.0)
    assert (c.traced_eur, c.traced_share) == (0.0, 0.0)
    assert c.untraced_eur >= 0.0
    assert c.reported_eur == 100.0


def test_snapshot_mode_never_downloads_and_names_the_missing_year(tmp_path):
    import json
    from wimm import build as b
    snap = tmp_path / "kela.json"
    snap.write_text(json.dumps({"schema": 1, "entries": []}), encoding="utf-8")
    # Cache dir is empty and unreachable on purpose: snapshot mode must fail from the file alone.
    with pytest.raises(AssertionError, match="--kela download"):
        b.kela_inputs("snapshot", tmp_path / "no-cache", [2025], snap)


def test_reconcile_returns_the_signed_difference_inside_the_limit():
    assert build.reconcile("x", 104.0, 100.0) == pytest.approx(0.04)
    assert build.reconcile("x", 96.0, 100.0) == pytest.approx(-0.04)


@pytest.mark.parametrize("kela", [105.1, 94.9])
def test_reconcile_stops_just_beyond_the_limit(kela):
    with pytest.raises(AssertionError, match="differ by"):
        build.reconcile("x", kela, 100.0)


@pytest.mark.parametrize("actual", [-100.0, 0.0, float("nan"), float("inf")])
def test_reconcile_refuses_a_treasury_actual_that_is_not_finite_and_positive(actual):
    # With a signed denominator, actual=-100 and Kela=100 gave a "gap" of -2, which passed.
    with pytest.raises(AssertionError, match="positive Treasury actual"):
        build.reconcile("x", 100.0, actual)


def test_reconcile_refuses_a_kela_figure_that_is_not_finite():
    with pytest.raises(AssertionError):
        build.reconcile("x", float("nan"), 100.0)
