"""Tests for gateway.core.temporal_context."""

from datetime import datetime
from zoneinfo import ZoneInfo

from gateway.core.temporal_context import DUBAI_TZ, TemporalContext


def test_timezone_is_asia_dubai():
    context = TemporalContext.build()
    assert context.timezone == "Asia/Dubai"


def test_last_3_months_is_tuple_of_two_date_strings():
    context = TemporalContext.build(
        datetime(2026, 6, 6, 12, 0, tzinfo=DUBAI_TZ),
    )
    assert isinstance(context.last_3_months, tuple)
    assert len(context.last_3_months) == 2
    assert all(isinstance(value, str) for value in context.last_3_months)


def test_last_3_months_end_date_is_today():
    reference = datetime(2026, 6, 6, 12, 0, tzinfo=DUBAI_TZ)
    context = TemporalContext.build(reference)
    assert context.last_3_months[1] == "2026-06-06"


def test_last_3_months_start_date_is_about_90_days_ago():
    reference = datetime(2026, 6, 6, 12, 0, tzinfo=DUBAI_TZ)
    context = TemporalContext.build(reference)
    assert context.last_3_months[0] == "2026-03-08"


def test_ytd_starts_january_first_of_current_year():
    reference = datetime(2026, 6, 6, 12, 0, tzinfo=DUBAI_TZ)
    context = TemporalContext.build(reference)
    assert context.ytd == ("2026-01-01", "2026-06-06")


def test_current_quarter_returns_1_2_3_or_4():
    quarter_cases = [
        (datetime(2026, 1, 15, tzinfo=DUBAI_TZ), 1),
        (datetime(2026, 4, 15, tzinfo=DUBAI_TZ), 2),
        (datetime(2026, 8, 15, tzinfo=DUBAI_TZ), 3),
        (datetime(2026, 11, 15, tzinfo=DUBAI_TZ), 4),
    ]
    for reference, expected_quarter in quarter_cases:
        context = TemporalContext.build(reference)
        assert context.current_quarter == expected_quarter
        assert context.current_quarter in {1, 2, 3, 4}


def test_summary_mentions_last_3_months_as_default():
    context = TemporalContext.build(datetime(2026, 6, 6, tzinfo=DUBAI_TZ))
    summary = context.summary()
    assert "last 3 months" in summary.lower()


def test_is_month_end_true_on_last_three_days_of_month():
    context = TemporalContext.build(datetime(2026, 6, 29, tzinfo=DUBAI_TZ))
    assert context.is_month_end is True

    context_mid_month = TemporalContext.build(datetime(2026, 6, 15, tzinfo=DUBAI_TZ))
    assert context_mid_month.is_month_end is False
