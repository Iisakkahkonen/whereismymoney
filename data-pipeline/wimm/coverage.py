"""The coverage meter: how much of a budget item is broken down further by a second dataset.

Every budget item is already shown at budget-item level (State Treasury). For a few
items a second source says where the money went in more detail, for example Kela's
payments by benefit and household type. That part is "traced"; the rest is "not
traced in public data". Nothing is estimated or filled in (CLAUDE.md).
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Coverage:
    traced_eur: float  # part of the actual matched to the second source, never above the actual
    untraced_eur: float  # actual minus traced, never negative
    traced_share: float  # traced_eur / actual_eur, between 0 and 1
    reported_eur: float  # what the second source itself reports, with its sign, kept unchanged so no gap is hidden
    note: str  # "" normally; "traced_exceeds_actual" when the source reports more than the Treasury booked;
    #            "source_negative" when the source's own figure is negative (nothing is traced from it)


def compute_coverage(actual_eur: float, reported_eur: float) -> Coverage:
    """Combine a budget item's actual with the amount a second source reports.

    - No source, or an actual that is zero or negative: nothing is traced.
    - A negative source figure (refunds can exceed payments): nothing is traced, the signed figure
      is kept in reported_eur and the note says so.
    - Source below actual: the difference stays untraced.
    - Source above actual (the two measure differently, for example 2025 housing
      allowance, Kela 1.228 bn vs Treasury 1.212 bn): traced is capped at the actual,
      the item is fully traced, and the overage is flagged and still shown as reported.
    - A figure that is not a finite number is a pipeline error, not a value to clamp.
    """
    if not (math.isfinite(actual_eur) and math.isfinite(reported_eur)):
        raise ValueError(f"coverage needs finite amounts, got actual={actual_eur}, reported={reported_eur}")
    eligible = max(0.0, reported_eur)  # only a positive source figure can be traced
    if actual_eur <= 0 or eligible == 0.0:
        return Coverage(0.0, max(0.0, actual_eur), 0.0, reported_eur, "source_negative" if reported_eur < 0 else "")
    traced = min(eligible, actual_eur)
    note = "traced_exceeds_actual" if eligible > actual_eur else ""
    return Coverage(traced, actual_eur - traced, traced / actual_eur, reported_eur, note)
