from __future__ import annotations

from datetime import date

from gateway.quality_response import QUALITY_METRICS


def build_daily_quality_report(report_date: date | None = None) -> str:
    report_day = report_date or date.today()
    total = QUALITY_METRICS["responses"]
    passed = QUALITY_METRICS["quality_pass"]
    failed = QUALITY_METRICS["quality_fail"]
    pass_rate = (passed / total * 100) if total else 0.0
    return (
        f"QUALITY REPORT — {report_day:%d %b %Y}\n"
        f"Total responses: {total}\n"
        f"Quality pass: {passed} ({pass_rate:.1f}%)\n"
        f"Quality fail: {failed}\n"
    )
