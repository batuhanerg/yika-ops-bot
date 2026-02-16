"""Tests for stock prompt after hardware inventory writes.

After a hardware write that changes device quantities, Mustafa prompts
the user to update stock — "Bu cihazlar stoktan mı geldi?"
"""

import pytest
from unittest.mock import MagicMock, patch

from app.handlers.common import thread_store


# ---------------------------------------------------------------------------
# Helper: register action handlers and return them as a dict
# ---------------------------------------------------------------------------

def _register_handlers():
    """Register action handlers on a mock app and return handler dict."""
    from app.handlers.actions import register

    app_mock = MagicMock()
    handlers = {}

    def capture_action(action_id):
        def decorator(fn):
            handlers[action_id] = fn
            return fn
        return decorator

    app_mock.action = capture_action
    register(app_mock)
    return handlers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_threads():
    """Ensure thread store is clean before and after each test."""
    yield
    for i in range(1, 30):
        thread_store.clear(f"ts_stock_{i:03d}")


def _make_confirm_body(thread_ts: str) -> dict:
    """Build a Slack action body for confirm button click."""
    return {
        "message": {"thread_ts": thread_ts, "ts": f"msg_{thread_ts}"},
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
    }


def _mock_sheets():
    """Create a mock SheetsService with reasonable defaults."""
    mock = MagicMock()
    mock.read_hardware.return_value = [
        {"Site ID": "ASM-TR-01", "Device Type": "Tag", "Qty": 10},
    ]
    mock.read_stock.return_value = [
        {"Location": "Istanbul Office", "Device Type": "Tag", "Qty": 25},
        {"Location": "Istanbul Office", "Device Type": "Gateway", "Qty": 3},
        {"Location": "Adana Storage", "Device Type": "Gateway", "Qty": 5},
    ]
    mock.find_stock_row_index.return_value = 2
    return mock


def _all_say_texts(say_mock) -> list[str]:
    """Extract all text arguments from say calls."""
    texts = []
    for call in say_mock.call_args_list:
        text = call.kwargs.get("text", "")
        if not text and call.args:
            text = str(call.args[0])
        texts.append(text)
    return texts


# ===========================================================================
# Stock prompt triggering
# ===========================================================================


class TestStockPromptTriggering:
    """Test that stock prompt is triggered correctly after hardware writes."""

    def test_hardware_write_with_qty_triggers_stock_prompt(self):
        """After confirming hardware write with Qty, stock prompt is sent."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_001", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "qty": 10}],
            },
            "raw_message": "ASM'ye 10 tag ekledim",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_001")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        assert any("stok" in t.lower() for t in all_texts), \
            f"Stock prompt not found. Say calls: {all_texts}"

    def test_hardware_write_without_qty_no_stock_prompt(self):
        """FW version update without qty does NOT trigger stock prompt."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_002", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "fw_version": "2.0.0"}],
            },
            "raw_message": "ASM tag firmware güncellendi",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_002")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        assert not any("stoktan" in t.lower() or "stoğa" in t.lower() for t in all_texts), \
            "Stock prompt should NOT be sent for non-qty changes"

    def test_non_hardware_write_no_stock_prompt(self):
        """Support log write does NOT trigger stock prompt."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_003", {
            "operation": "log_support",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "received_date": "2026-02-15",
                "type": "Remote",
                "status": "Open",
                "root_cause": "Pending",
                "issue_summary": "Tag offline",
                "reported_by": "Batu",
                "responsible": "Batu",
            },
            "raw_message": "ASM'de tag offline",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_003")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            m = _mock_sheets()
            m.append_support_log.return_value = "SUP-001"
            m.read_support_log.return_value = [{"Status": "Open"}]
            mock_sheets.return_value = m
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        assert not any("stoktan" in t.lower() for t in all_texts)

    def test_stock_prompt_includes_device_details(self):
        """Stock prompt message includes device type, qty, and site."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_004", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "qty": 10}],
            },
            "raw_message": "ASM'ye 10 tag ekledim",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_004")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        stock_texts = [t for t in all_texts if "stok" in t.lower()]
        assert len(stock_texts) >= 1
        prompt = stock_texts[0]
        assert "Tag" in prompt
        assert "10" in prompt
        assert "ASM-TR-01" in prompt

    def test_device_removal_shows_reverse_prompt(self):
        """When raw message indicates removal, prompt offers to ADD to stock."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_005", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "qty": 5}],
            },
            "raw_message": "ASM'den 5 tag çıkardım",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_005")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        stock_texts = [t for t in all_texts if "stoğa" in t.lower() or "geri" in t.lower()]
        assert len(stock_texts) >= 1, \
            f"Reverse stock prompt not found. Say calls: {all_texts}"

    def test_multiple_entries_lists_all_in_prompt(self):
        """Bulk hardware write lists all entries in the stock prompt."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_006", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [
                    {"device_type": "Tag", "qty": 10},
                    {"device_type": "Gateway", "qty": 2},
                ],
            },
            "raw_message": "ASM'ye 10 tag ve 2 gateway ekledim",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_006")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        all_texts = _all_say_texts(say)
        stock_texts = [t for t in all_texts if "stok" in t.lower()]
        assert len(stock_texts) >= 1
        prompt = stock_texts[0]
        assert "Tag" in prompt
        assert "Gateway" in prompt


# ===========================================================================
# Stock prompt state
# ===========================================================================


class TestStockPromptState:
    """Test that stock prompt state is properly stored in thread store."""

    def test_stock_state_stored_after_prompt(self):
        """After stock prompt, thread state has stock_prompt_pending and stock_entries."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_007", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "qty": 10}],
            },
            "raw_message": "ASM'ye 10 tag ekledim",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_007")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        state = thread_store.get("ts_stock_007")
        assert state is not None
        assert state.get("stock_prompt_pending") is True
        entries = state.get("stock_entries", [])
        assert len(entries) >= 1
        assert entries[0]["device_type"] == "Tag"
        assert entries[0]["qty"] == 10

    def test_feedback_still_pending_alongside_stock(self):
        """Both feedback_pending and stock_prompt_pending coexist in thread state."""
        handlers = _register_handlers()
        thread_store.set("ts_stock_008", {
            "operation": "update_hardware",
            "user_id": "U_TEST",
            "data": {
                "site_id": "ASM-TR-01",
                "entries": [{"device_type": "Tag", "qty": 10}],
            },
            "raw_message": "ASM'ye 10 tag ekledim",
            "sender_name": "Batu",
            "language": "tr",
        })

        body = _make_confirm_body("ts_stock_008")
        say = MagicMock()
        client = MagicMock()

        with patch("app.handlers.actions.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            handlers["confirm_action"](lambda: None, body, say, client)

        state = thread_store.get("ts_stock_008")
        assert state is not None
        assert state.get("feedback_pending") is True
        assert state.get("stock_prompt_pending") is True


# ===========================================================================
# Stock reply handler
# ===========================================================================


class TestStockReplyHandler:
    """Test handling user replies to stock prompts."""

    def test_reply_with_location_updates_stock(self):
        """User replies with warehouse name → Stock sheet qty decreased."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 10, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_010", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = _mock_sheets()
            mock_sheets.return_value = m
            result = handle_stock_reply("Istanbul Office'ten geldi", "ts_stock_010", state, say, "U_TEST")

        assert result is True
        m.update_stock.assert_called_once()
        call_kwargs = m.update_stock.call_args
        # Qty should be decreased: 25 - 10 = 15
        assert call_kwargs[0][1] == {"Qty": 15}

    def test_decline_reply_no_update(self):
        """'hayır' reply → no stock update, state cleared."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 10, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_011", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            result = handle_stock_reply("hayır", "ts_stock_011", state, say, "U_TEST")

        assert result is True
        mock_sheets.return_value.update_stock.assert_not_called()
        # State should be cleared
        remaining = thread_store.get("ts_stock_011")
        assert remaining is None or not remaining.get("stock_prompt_pending")

    def test_gerek_yok_reply_no_update(self):
        """'gerek yok' reply → no stock update."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 10, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_012", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            result = handle_stock_reply("gerek yok", "ts_stock_012", state, say, "U_TEST")

        assert result is True

    def test_negative_stock_warning(self):
        """Warning when stock would go below zero."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 30, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_013", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = _mock_sheets()
            # Istanbul Office has only 25 Tags
            mock_sheets.return_value = m
            result = handle_stock_reply("Istanbul Office'ten geldi", "ts_stock_013", state, say, "U_TEST")

        assert result is True
        all_texts = _all_say_texts(say)
        assert any("25" in t and "30" in t for t in all_texts), \
            f"Warning about insufficient stock not found: {all_texts}"

    def test_unknown_location_lists_available(self):
        """Unknown location → asks user to clarify with available locations."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 10, "site_id": "ASM-TR-01", "direction": "subtract"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_014", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            mock_sheets.return_value = _mock_sheets()
            result = handle_stock_reply("Ankara depodan geldi", "ts_stock_014", state, say, "U_TEST")

        assert result is True
        all_texts = _all_say_texts(say)
        assert any("Istanbul Office" in t for t in all_texts), \
            f"Available locations not shown: {all_texts}"

    def test_device_removal_adds_to_stock(self):
        """Device removal (direction=add) increases stock qty."""
        from app.handlers.common import handle_stock_reply

        state = {
            "stock_prompt_pending": True,
            "stock_entries": [
                {"device_type": "Tag", "qty": 5, "site_id": "ASM-TR-01", "direction": "add"},
            ],
            "user_id": "U_TEST",
            "language": "tr",
        }
        thread_store.set("ts_stock_015", state)
        say = MagicMock()

        with patch("app.handlers.common.get_sheets") as mock_sheets:
            m = _mock_sheets()
            mock_sheets.return_value = m
            result = handle_stock_reply("Istanbul Office'e gitti", "ts_stock_015", state, say, "U_TEST")

        assert result is True
        m.update_stock.assert_called_once()
        call_kwargs = m.update_stock.call_args
        # Qty should be increased: 25 + 5 = 30
        assert call_kwargs[0][1] == {"Qty": 30}


# ===========================================================================
# Sheets helper: find_stock_row_index
# ===========================================================================


class TestFindStockRowIndex:
    """Test the find_stock_row_index helper on SheetsService."""

    @pytest.fixture
    def sheets_service(self):
        mock_spreadsheet = MagicMock()
        stock_ws = MagicMock()
        stock_ws.get_all_values.return_value = [
            ["Location", "Device Type", "HW Version", "FW Version", "Qty", "Condition", "Reserved For", "Notes", "Last Verified"],
            ["Istanbul Office", "Tag", "3.6.0", "1.1.6.4", "25", "New", "", "", ""],
            ["Istanbul Office", "Gateway", "2.0", "", "3", "New", "", "", ""],
            ["Adana Storage", "Gateway", "3.0", "", "5", "New", "", "", ""],
        ]
        mock_spreadsheet.worksheet.return_value = stock_ws

        with patch("app.services.sheets.SheetsService._connect"):
            from app.services.sheets import SheetsService
            service = SheetsService.__new__(SheetsService)
            service.spreadsheet = mock_spreadsheet
            service._ws_cache = {}
            yield service

    def test_finds_matching_row(self, sheets_service):
        """Finds the correct row index for a location/device type combo."""
        idx = sheets_service.find_stock_row_index("Istanbul Office", "Tag")
        assert idx == 2  # 1-based (row 2 = first data row)

    def test_finds_second_entry(self, sheets_service):
        """Finds different device type at same location."""
        idx = sheets_service.find_stock_row_index("Istanbul Office", "Gateway")
        assert idx == 3

    def test_returns_none_for_missing(self, sheets_service):
        """Returns None when location/device combo not found."""
        idx = sheets_service.find_stock_row_index("Ankara Office", "Tag")
        assert idx is None

    def test_returns_none_for_wrong_device(self, sheets_service):
        """Returns None when device type doesn't exist at location."""
        idx = sheets_service.find_stock_row_index("Adana Storage", "Tag")
        assert idx is None
