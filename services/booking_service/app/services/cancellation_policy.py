"""Cancellation refund policy (HU4.3).

Pure-function module so the policy can be unit-tested in isolation and the
thresholds can be tweaked from a single place when business needs change.

Rule:
- More than `REFUND_FULL_DAYS` days before check-in     → 100% refund
- Between `REFUND_PARTIAL_DAYS` and `REFUND_FULL_DAYS`  → 50% refund
- Less than `REFUND_PARTIAL_DAYS` days (or check-in already past) → 0%
"""

from datetime import date

REFUND_FULL_DAYS = 7
REFUND_PARTIAL_DAYS = 2

REFUND_FULL = 1.0
REFUND_PARTIAL = 0.5
REFUND_NONE = 0.0


def days_until_check_in(check_in: date, today: date) -> int:
    """Whole-day delta from today to check-in. Negative if check-in is past."""
    return (check_in - today).days


def calculate_refund_percentage(check_in: date, today: date) -> float:
    """Return the fraction (0..1) of the original payment to refund."""
    delta = days_until_check_in(check_in, today)
    if delta > REFUND_FULL_DAYS:
        return REFUND_FULL
    if delta >= REFUND_PARTIAL_DAYS:
        return REFUND_PARTIAL
    return REFUND_NONE
