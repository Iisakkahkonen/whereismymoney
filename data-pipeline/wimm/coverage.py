"""The coverage meter: how much of a budget item is traced to named data.

Each budget item has an actual amount (State Treasury) and, for a few items, a
traced amount from a source that says where the money went (for example Kela's
payments by benefit). The rest is "not traced in public data". The meter must
never fill a gap with a guess (CLAUDE.md), and never hide a mismatch.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Coverage:
    traced_eur: float  # money matched to a source that says where it went
    untraced_eur: float  # shown to the reader as "not traced in public data"
    traced_share: float  # traced_eur / actual_eur, the number on the meter
    note: str  # "" when nothing odd; otherwise a short code the page can explain


def compute_coverage(actual_eur: float, traced_eur: float) -> Coverage:
    """Combine a budget item's actual with the amount a source traces.

    Edge cases the rule must settle (they all occur in real data):
    - No source at all: traced_eur is 0, so the whole item is untraced.
    - Traced is a little below actual (asumistuki 2024: Kela 1,676.9 m vs
      Treasury 1,696.1 m): the difference is shown as untraced.
    - Traced is a little ABOVE actual (opintotuki 2024: Kela 517.7 m vs
      Treasury 515.5 m): untraced would be negative and the share above 100%.
    - Actual is zero or negative (some items net to nothing): a share is
      undefined.
    """
    # TODO(human): replace this placeholder with the rule for the edge cases above.
    traced = max(0.0, traced_eur)
    untraced = actual_eur - traced
    share = traced / actual_eur if actual_eur > 0 else 0.0
    return Coverage(traced, untraced, share, "")
