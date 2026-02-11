"""Tests for thread state management."""

import time

import pytest

from app.handlers.threads import ThreadStore


@pytest.fixture
def store() -> ThreadStore:
    return ThreadStore()


class TestStoreAndRetrieve:
    def test_store_state(self, store: ThreadStore):
        store.set("T001", {"operation": "log_support", "user_id": "U1"})
        state = store.get("T001")
        assert state is not None
        assert state["operation"] == "log_support"
        assert state["user_id"] == "U1"

    def test_get_nonexistent_returns_none(self, store: ThreadStore):
        assert store.get("NONEXISTENT") is None


class TestAccumulateData:
    def test_merge_across_turns(self, store: ThreadStore):
        store.set("T002", {
            "operation": "log_support",
            "user_id": "U1",
            "data": {"site_id": "MIG-TR-01", "type": "Visit"},
            "missing_fields": ["received_date", "status", "technician"],
        })
        store.merge("T002", {
            "data": {"received_date": "2025-01-15", "status": "Resolved", "technician": "Batu"},
            "missing_fields": [],
        })
        state = store.get("T002")
        assert state["data"]["site_id"] == "MIG-TR-01"
        assert state["data"]["received_date"] == "2025-01-15"
        assert state["data"]["technician"] == "Batu"
        assert state["missing_fields"] == []


class TestExpireOldState:
    def test_expire_removes_old(self, store: ThreadStore):
        store.set("T003", {"operation": "log_support", "user_id": "U1"})
        # Manually backdate the timestamp
        store._threads["T003"]["_created_at"] = time.time() - 7200  # 2 hours ago
        store.expire(max_age_seconds=3600)
        assert store.get("T003") is None

    def test_expire_keeps_recent(self, store: ThreadStore):
        store.set("T004", {"operation": "log_support", "user_id": "U1"})
        store.expire(max_age_seconds=3600)
        assert store.get("T004") is not None


class TestClearOnAction:
    def test_clear_removes_state(self, store: ThreadStore):
        store.set("T005", {"operation": "log_support", "user_id": "U1"})
        store.clear("T005")
        assert store.get("T005") is None

    def test_clear_nonexistent_is_noop(self, store: ThreadStore):
        store.clear("NONEXISTENT")  # should not raise
