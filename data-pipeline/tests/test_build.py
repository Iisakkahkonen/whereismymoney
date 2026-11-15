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
