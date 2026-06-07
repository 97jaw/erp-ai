"""Session-scoped cache for proactive pre-computed query results (Phase 7)."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

CACHE_TTL_SECONDS = 7200
MAX_ENTRIES_PER_SESSION = 8


def normalize_lookup_message(message: str) -> str:
    """Normalize user or suggestion text for cache lookup."""
    return " ".join(message.strip().lower().split())


def cache_fingerprint(session_id: str, message: str) -> str:
    """Build a stable cache key for one session and query message."""
    normalized = normalize_lookup_message(message)
    digest = hashlib.sha256(f"{session_id}:{normalized}".encode()).hexdigest()[:24]
    return digest


@dataclass
class CachedPrecompute:
    """One pre-computed response waiting for a likely follow-up query."""

    key: str
    suggestion_text: str
    query_message: str
    text: str = ""
    visualization: dict[str, Any] | None = None
    suggestions: list[str] = field(default_factory=list)
    status: str = "pending"
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float = 0.0
    error: str | None = None

    def is_ready(self) -> bool:
        return self.status == "ready" and bool(self.text.strip())


class PrecomputeCache:
    """In-memory pre-compute store keyed by session + normalized query."""

    def __init__(self, *, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._by_session: dict[str, dict[str, CachedPrecompute]] = {}

    def mark_pending(
        self,
        session_id: str,
        *,
        suggestion_text: str,
        query_message: str,
    ) -> str:
        """Register a pending pre-compute job and return its cache key."""
        self._purge_session(session_id)
        key = cache_fingerprint(session_id, query_message)
        bucket = self._by_session.setdefault(session_id, {})
        bucket[key] = CachedPrecompute(
            key=key,
            suggestion_text=suggestion_text.strip(),
            query_message=query_message.strip(),
            status="pending",
            expires_at=time.monotonic() + self._ttl_seconds,
        )
        self._trim_session(session_id)
        return key

    def put_ready(
        self,
        session_id: str,
        key: str,
        *,
        text: str,
        visualization: dict[str, Any] | None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Store a completed pre-compute result."""
        entry = self._get_entry(session_id, key)
        if entry is None:
            return
        entry.text = text
        entry.visualization = visualization
        entry.suggestions = list(suggestions or [])
        entry.status = "ready"
        entry.expires_at = time.monotonic() + self._ttl_seconds

    def mark_failed(self, session_id: str, key: str, error: str) -> None:
        """Record a failed background pre-compute."""
        entry = self._get_entry(session_id, key)
        if entry is None:
            return
        entry.status = "failed"
        entry.error = error[:500]

    def lookup(self, session_id: str, message: str) -> CachedPrecompute | None:
        """Return a ready cache entry when the message matches a pre-computed query."""
        self._purge_session(session_id)
        bucket = self._by_session.get(session_id)
        if not bucket:
            return None

        normalized = normalize_lookup_message(message)
        for entry in bucket.values():
            if entry.status != "ready":
                continue
            if normalize_lookup_message(entry.query_message) == normalized:
                return entry
            if normalize_lookup_message(entry.suggestion_text) == normalized:
                return entry
        return None

    def list_keys(self, session_id: str) -> list[str]:
        """Return active cache keys for one session."""
        self._purge_session(session_id)
        bucket = self._by_session.get(session_id) or {}
        return list(bucket.keys())

    def _get_entry(self, session_id: str, key: str) -> CachedPrecompute | None:
        self._purge_session(session_id)
        return (self._by_session.get(session_id) or {}).get(key)

    def _purge_session(self, session_id: str) -> None:
        bucket = self._by_session.get(session_id)
        if not bucket:
            return
        now = time.monotonic()
        expired = [key for key, entry in bucket.items() if entry.expires_at and now >= entry.expires_at]
        for key in expired:
            bucket.pop(key, None)
        if not bucket:
            self._by_session.pop(session_id, None)

    def _trim_session(self, session_id: str) -> None:
        bucket = self._by_session.get(session_id)
        if not bucket or len(bucket) <= MAX_ENTRIES_PER_SESSION:
            return
        ordered = sorted(bucket.values(), key=lambda entry: entry.created_at)
        for entry in ordered[: len(bucket) - MAX_ENTRIES_PER_SESSION]:
            bucket.pop(entry.key, None)


# Shared process cache for proactive background tasks.
GLOBAL_PRECOMPUTE_CACHE = PrecomputeCache()
