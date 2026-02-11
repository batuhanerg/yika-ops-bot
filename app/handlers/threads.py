"""Thread state management — in-memory dict keyed by Slack thread_ts."""

from __future__ import annotations

import time
from typing import Any


class ThreadStore:
    """Stores conversation state per Slack thread."""

    def __init__(self) -> None:
        self._threads: dict[str, dict[str, Any]] = {}

    def get(self, thread_ts: str) -> dict[str, Any] | None:
        entry = self._threads.get(thread_ts)
        if entry is None:
            return None
        # Return a copy without internal metadata
        return {k: v for k, v in entry.items() if not k.startswith("_")}

    def set(self, thread_ts: str, state: dict[str, Any]) -> None:
        self._threads[thread_ts] = {
            **state,
            "_created_at": time.time(),
        }

    def merge(self, thread_ts: str, updates: dict[str, Any]) -> None:
        """Merge new data into existing thread state."""
        entry = self._threads.get(thread_ts)
        if entry is None:
            self.set(thread_ts, updates)
            return

        for key, value in updates.items():
            if key.startswith("_"):
                continue
            if key == "data" and isinstance(value, dict) and isinstance(entry.get("data"), dict):
                entry["data"].update(value)
            else:
                entry[key] = value

    def clear(self, thread_ts: str) -> None:
        self._threads.pop(thread_ts, None)

    def expire(self, max_age_seconds: int = 3600) -> None:
        """Remove thread states older than max_age_seconds."""
        now = time.time()
        expired = [
            ts for ts, state in self._threads.items()
            if now - state.get("_created_at", now) > max_age_seconds
        ]
        for ts in expired:
            del self._threads[ts]
