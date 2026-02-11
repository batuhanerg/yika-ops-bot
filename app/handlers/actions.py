"""Button click handlers for confirm/cancel actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.handlers.common import get_sheets, thread_store
from app.services.sheets import SheetsService

if TYPE_CHECKING:
    from slack_bolt import App

logger = logging.getLogger(__name__)

# Device replacement keywords (Turkish + English)
_REPLACEMENT_KEYWORDS = (
    "değiştir", "değiştik", "değiştirildi", "replaced", "replacement",
    "yenisiyle", "swap", "takas",
)


def register(app: App) -> None:
    """Register button action handlers."""

    @app.action("confirm_action")
    def handle_confirm(ack, body, say, client) -> None:
        ack()

        msg = body.get("message", {})
        # Use thread_ts (thread root) to find state, fall back to message ts
        thread_ts = msg.get("thread_ts") or msg.get("ts", "")
        user_id = body.get("user", {}).get("id", "")
        channel = body.get("channel", {}).get("id", "")

        state = thread_store.get(thread_ts)
        if not state:
            say(text="Bu işlemin süresi dolmuş. Lütfen tekrar deneyin.", thread_ts=thread_ts, channel=channel)
            return

        # Only the initiating user can confirm
        if state.get("user_id") != user_id:
            say(text="Bu işlemi sadece başlatan kişi onaylayabilir.", thread_ts=thread_ts, channel=channel)
            return

        operation = state["operation"]
        data = state["data"]
        raw_message = state.get("raw_message", "")
        sender_name = state.get("sender_name", "Unknown")

        try:
            sheets = get_sheets()
            _execute_write(sheets, operation, data)

            # Audit log
            sheets.append_audit_log(
                user=sender_name,
                operation="CREATE" if operation.startswith("create") or operation.startswith("log") else "UPDATE",
                target_tab=_operation_to_tab(operation),
                site_id=data.get("site_id", ""),
                summary=_build_audit_summary(operation, data),
                raw_message=raw_message,
            )

            # Read-back confirmation
            readback = _build_readback(sheets, operation, data)
            say(text=f"✅ İşlem tamamlandı.\n{readback}", thread_ts=thread_ts, channel=channel)

            # Stock cross-reference check
            if _should_ask_stock(operation, data, raw_message):
                say(
                    text="Bu değişim stok ile ilgili mi? Stok güncellemesi yapmamı ister misin?",
                    thread_ts=thread_ts,
                    channel=channel,
                )

        except Exception as e:
            logger.exception("Write error")
            say(text="Sheets'e yazamadım, lütfen tekrar deneyin.", thread_ts=thread_ts, channel=channel)

        thread_store.clear(thread_ts)

    @app.action("cancel_action")
    def handle_cancel(ack, body, say) -> None:
        ack()

        msg = body.get("message", {})
        thread_ts = msg.get("thread_ts") or msg.get("ts", "")
        user_id = body.get("user", {}).get("id", "")
        channel = body.get("channel", {}).get("id", "")

        state = thread_store.get(thread_ts)
        if state and state.get("user_id") != user_id:
            say(text="Bu işlemi sadece başlatan kişi iptal edebilir.", thread_ts=thread_ts, channel=channel)
            return

        thread_store.clear(thread_ts)
        say(text="❌ İşlem iptal edildi.", thread_ts=thread_ts, channel=channel)


def _execute_write(sheets: SheetsService, operation: str, data: dict[str, Any]) -> None:
    """Execute the write operation to the correct sheet tab."""
    if operation == "log_support":
        sheets.append_support_log(data)

    elif operation == "create_site":
        sheets.create_site(data)

    elif operation == "update_support":
        row_index = data.pop("_row_index", None)
        if row_index:
            # Convert snake_case keys to sheet column names
            from app.services.sheets import _SUPPORT_KEY_MAP
            updates = {}
            for k, v in data.items():
                col_name = _SUPPORT_KEY_MAP.get(k)
                if col_name and v:
                    updates[col_name] = v
            sheets.update_support_log(row_index, updates)

    elif operation == "update_site":
        site_id = data.get("site_id", "")
        from app.services.sheets import _SITES_KEY_MAP
        updates = {}
        for k, v in data.items():
            if k == "site_id":
                continue
            col_name = _SITES_KEY_MAP.get(k)
            if col_name and v:
                updates[col_name] = v
        if updates:
            sheets.update_site(site_id, updates)

    elif operation == "update_hardware":
        entries = data.get("entries", [])
        if entries:
            for entry in entries:
                entry["site_id"] = data.get("site_id", "")
                sheets.append_hardware(entry)
        else:
            data_copy = {**data}
            sheets.append_hardware(data_copy)

    elif operation == "update_implementation":
        site_id = data.get("site_id", "")
        updates = {k: v for k, v in data.items() if k != "site_id" and v}
        if updates:
            sheets.update_implementation(site_id, updates)

    elif operation == "update_stock":
        sheets.append_stock(data)


def _operation_to_tab(operation: str) -> str:
    return {
        "log_support": "Support Log",
        "create_site": "Sites",
        "update_support": "Support Log",
        "update_site": "Sites",
        "update_hardware": "Hardware Inventory",
        "update_implementation": "Implementation Details",
        "update_stock": "Stock",
    }.get(operation, "Unknown")


def _build_audit_summary(operation: str, data: dict[str, Any]) -> str:
    parts = [operation]
    if data.get("site_id"):
        parts.append(data["site_id"])
    if data.get("issue_summary"):
        parts.append(data["issue_summary"][:60])
    return " — ".join(parts)


def _build_readback(sheets: SheetsService, operation: str, data: dict[str, Any]) -> str:
    """Build a contextual readback summary after a write."""
    site_id = data.get("site_id", "")
    if not site_id:
        return ""

    try:
        if operation in ("log_support", "update_support"):
            logs = sheets.read_support_log(site_id)
            total = len(logs)
            open_count = sum(1 for l in logs if l.get("Status") not in ("Resolved",))
            return f"📊 `{site_id}`: {total} toplam kayıt, {open_count} açık ticket."

        elif operation == "create_site":
            return f"🆕 `{site_id}` sitesi oluşturuldu."

        elif operation == "update_hardware":
            hw = sheets.read_hardware(site_id)
            total_devices = sum(int(h.get("Qty", 0)) for h in hw)
            return f"🔧 `{site_id}`: toplam {total_devices} cihaz."

        return ""
    except Exception:
        return ""


def _should_ask_stock(operation: str, data: dict[str, Any], raw_message: str) -> bool:
    """Check if we should ask about stock cross-reference."""
    if operation not in ("log_support", "update_hardware"):
        return False
    raw_lower = raw_message.lower()
    return any(kw in raw_lower for kw in _REPLACEMENT_KEYWORDS)
