"""Time-aware context with UAE timezone defaults.

Computes fiscal periods, relative date ranges (last 3 months, YTD, etc.),
and period-end markers used when users omit explicit dates.
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DUBAI_TZ = ZoneInfo("Asia/Dubai")
QUARTER_END_MONTHS = {3, 6, 9, 12}


@dataclass
class TemporalContext:
    """Time-aware context for default date ranges and period markers."""

    now: datetime
    today: date
    current_fiscal_year: int
    current_quarter: int
    current_month: int
    is_month_end: bool
    is_quarter_end: bool
    is_year_end: bool
    business_day: bool
    last_3_months: tuple[str, str]
    last_month: tuple[str, str]
    last_quarter: tuple[str, str]
    last_year: tuple[str, str]
    ytd: tuple[str, str]
    timezone: str = "Asia/Dubai"

    @classmethod
    def build(cls, reference: datetime | None = None) -> "TemporalContext":
        """Build temporal context for a reference moment in Asia/Dubai."""
        if reference is None:
            now = datetime.now(DUBAI_TZ)
        elif reference.tzinfo is None:
            now = reference.replace(tzinfo=DUBAI_TZ)
        else:
            now = reference.astimezone(DUBAI_TZ)

        today = now.date()
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        is_month_end = today.day >= days_in_month - 2
        is_quarter_end = today.month in QUARTER_END_MONTHS and is_month_end
        is_year_end = today.month == 12 and is_month_end
        business_day = today.weekday() not in (4, 5)

        return cls(
            now=now,
            today=today,
            current_fiscal_year=today.year,
            current_quarter=((today.month - 1) // 3) + 1,
            current_month=today.month,
            is_month_end=is_month_end,
            is_quarter_end=is_quarter_end,
            is_year_end=is_year_end,
            business_day=business_day,
            last_3_months=cls._last_3_months_range(today),
            last_month=cls._last_month_range(today),
            last_quarter=cls._last_quarter_range(today),
            last_year=cls._last_year_range(today),
            ytd=cls._ytd_range(today),
        )

    def summary(self) -> str:
        """Format temporal context and date defaults for Claude prompt injection."""
        return f"""
Current time: {self.now.strftime('%Y-%m-%d %H:%M')} {self.timezone}
Current fiscal year: {self.current_fiscal_year}
Current quarter: Q{self.current_quarter}
Period markers: month-end={self.is_month_end}, quarter-end={self.is_quarter_end}

When user says relative period, use:
  "last month" → {self.last_month}
  "last quarter" → {self.last_quarter}
  "last year" → {self.last_year}
  "this year" / "YTD" → {self.ytd}
  Without specification → last 3 months: {self.last_3_months}
"""

    @staticmethod
    def _last_3_months_range(today: date) -> tuple[str, str]:
        start = today - timedelta(days=90)
        return (start.isoformat(), today.isoformat())

    @staticmethod
    def _last_month_range(today: date) -> tuple[str, str]:
        first_of_month = today.replace(day=1)
        last_day_previous_month = first_of_month - timedelta(days=1)
        start = last_day_previous_month.replace(day=1)
        return (start.isoformat(), last_day_previous_month.isoformat())

    @staticmethod
    def _last_quarter_range(today: date) -> tuple[str, str]:
        current_quarter = ((today.month - 1) // 3) + 1
        if current_quarter == 1:
            year = today.year - 1
            start = date(year, 10, 1)
            end = date(year, 12, 31)
        else:
            start_month = ((current_quarter - 2) * 3) + 1
            end_month = start_month + 2
            start = date(today.year, start_month, 1)
            end_day = calendar.monthrange(today.year, end_month)[1]
            end = date(today.year, end_month, end_day)
        return (start.isoformat(), end.isoformat())

    @staticmethod
    def _last_year_range(today: date) -> tuple[str, str]:
        year = today.year - 1
        return (date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat())

    @staticmethod
    def _ytd_range(today: date) -> tuple[str, str]:
        return (date(today.year, 1, 1).isoformat(), today.isoformat())
