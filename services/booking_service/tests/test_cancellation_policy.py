"""Pure-function tests for the cancellation refund policy (HU4.3)."""

from datetime import date, timedelta

from app.services.cancellation_policy import (
    REFUND_FULL,
    REFUND_NONE,
    REFUND_PARTIAL,
    calculate_refund_percentage,
    days_until_check_in,
)

TODAY = date(2026, 5, 1)


class TestDaysUntilCheckIn:
    def test_future_check_in(self):
        assert days_until_check_in(TODAY + timedelta(days=10), TODAY) == 10

    def test_same_day(self):
        assert days_until_check_in(TODAY, TODAY) == 0

    def test_past_check_in_is_negative(self):
        assert days_until_check_in(TODAY - timedelta(days=2), TODAY) == -2


class TestCalculateRefundPercentage:
    """CA1/CA2/CA3 — refund tiers."""

    def test_more_than_seven_days_full_refund(self):
        check_in = TODAY + timedelta(days=8)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_FULL

    def test_thirty_days_full_refund(self):
        # Sanity check that "much further out" stays at 100%
        check_in = TODAY + timedelta(days=30)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_FULL

    def test_seven_days_is_partial_refund(self):
        # The boundary is `> 7 days`, so exactly 7 falls in the partial bucket
        check_in = TODAY + timedelta(days=7)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_PARTIAL

    def test_two_days_is_partial_refund(self):
        check_in = TODAY + timedelta(days=2)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_PARTIAL

    def test_one_day_no_refund(self):
        check_in = TODAY + timedelta(days=1)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_NONE

    def test_same_day_no_refund(self):
        assert calculate_refund_percentage(TODAY, TODAY) == REFUND_NONE

    def test_past_check_in_no_refund(self):
        # User somehow cancels after check-in — no refund
        check_in = TODAY - timedelta(days=1)
        assert calculate_refund_percentage(check_in, TODAY) == REFUND_NONE
