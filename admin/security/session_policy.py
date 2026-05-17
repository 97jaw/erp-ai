from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

SESSION_IDLE_MINUTES = int(os.environ.get("SESSION_IDLE_MINUTES", "60"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_session_idle_expired(last_activity: datetime | None) -> bool:
    if last_activity is None:
        return False
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    return last_activity < _utcnow() - timedelta(minutes=SESSION_IDLE_MINUTES)
