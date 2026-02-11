"""Button click handlers for confirm/cancel actions."""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from app.handlers.common import get_sheets, thread_store
from app.services.sheets import SheetsService
from app.utils.formatters import (
    build_chain_final_summary,
    format_confirmation_message,
    OPERATION_TITLES,
)

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

            # Inject last_verified for hardware/implementation
            today = date.today().isoformat()
            if operation == "update_hardware":
                for entry in data.get("entries", []):
                    if not entry.get("last_verified"):
                        entry["last_verified"] = data.get("last_verified", today)
                if not data.get("entries") and not data.get("last_verified"):
                    data["last_verified"] = today
            elif operation == "update_implementation":
                if not data.get("last_verified"):
                    data["last_verified"] = today

            ticket_id = _execute_write(sheets, operation, data)

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
            readback = _build_readback(sheets, operation, data, ticket_id)

            # Chain tracking
            completed = list(state.get("completed_operations", []))
            completed.append({"operation": operation, "readback": readback, "ticket_id": ticket_id})

            pending = list(state.get("pending_operations", []))
            chain_steps = state.get("chain_steps", [])
            skipped = list(state.get("skipped_operations", []))
            current_step = state.get("current_step", 0)
            total_steps = state.get("total_steps", 0)

            if pending:
                next_op = pending.pop(0)
                next_data = next_op.get("data", {})
                next_step = current_step + 1

                # Inject site_id from current operation
                site_id = data.get("site_id", "")
                if site_id and not next_data.get("site_id"):
                    next_data["site_id"] = site_id

                # Post readback only (no transition question)
                if readback:
                    say(text=f"✅ {readback}", thread_ts=thread_ts, channel=channel)

                # Show next confirmation card with step indicator
                step_info = (next_step, total_steps)
                display_data = {**next_data, "operation": next_op["operation"]}
                blocks = format_confirmation_message(display_data, step_info=step_info)

                thread_store.set(thread_ts, {
                    "operation": next_op["operation"],
                    "user_id": user_id,
                    "data": next_data,
                    "missing_fields": [],
                    "raw_message": raw_message,
                    "sender_name": sender_name,
                    "pending_operations": pending,
                    "completed_operations": completed,
                    "skipped_operations": skipped,
                    "chain_steps": chain_steps,
                    "current_step": next_step,
                    "total_steps": total_steps,
                    "language": state.get("language", "tr"),
                })
                say(blocks=blocks, thread_ts=thread_ts, channel=channel)
            else:
                # No more pending — finalize
                in_chain = bool(chain_steps) and len(chain_steps) > 1
                if in_chain:
                    site_id = data.get("site_id", "")
                    completed_ops = {item["operation"] for item in completed}
                    summary = build_chain_final_summary(site_id, chain_steps, completed_ops, set(skipped))
                    text = f"✅ {readback}\n\n{summary}" if readback else summary
                    say(text=text, thread_ts=thread_ts, channel=channel)
                else:
                    say(text=f"✅ İşlem tamamlandı.\n{readback}", thread_ts=thread_ts, channel=channel)

                    # Stock cross-reference check (only for non-chained single operations)
                    if _should_ask_stock(operation, data, raw_message):
                        say(
                            text="Bu değişim stok ile ilgili mi? Stok güncellemesi yapmamı ister misin?",
                            thread_ts=thread_ts,
                            channel=channel,
                        )

                thread_store.clear(thread_ts)

        except Exception as e:
            logger.exception("Write error")
            say(text="Sheets'e yazamadım, lütfen tekrar deneyin.", thread_ts=thread_ts, channel=channel)

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

        lang = state.get("language", "tr") if state else "tr"
        pending = list(state.get("pending_operations", [])) if state else []
        completed = list(state.get("completed_operations", [])) if state else []
        skipped = list(state.get("skipped_operations", [])) if state else []
        chain_steps = state.get("chain_steps", []) if state else []
        current_step = state.get("current_step", 0) if state else 0
        total_steps = state.get("total_steps", 0) if state else 0

        # Track current operation as skipped
        if state:
            skipped.append(state["operation"])

        if pending:
            next_op = pending.pop(0)
            next_data = next_op.get("data", {})
            next_step = current_step + 1

            # Inject site_id
            site_id = state.get("data", {}).get("site_id", "") if state else ""
            if site_id and not next_data.get("site_id"):
                next_data["site_id"] = site_id

            say(text="⏭️ Atlandı.", thread_ts=thread_ts, channel=channel)

            step_info = (next_step, total_steps)
            display_data = {**next_data, "operation": next_op["operation"]}
            blocks = format_confirmation_message(display_data, step_info=step_info)

            thread_store.set(thread_ts, {
                "operation": next_op["operation"],
                "user_id": user_id,
                "data": next_data,
                "missing_fields": [],
                "raw_message": state.get("raw_message", "") if state else "",
                "sender_name": state.get("sender_name", "Unknown") if state else "Unknown",
                "pending_operations": pending,
                "completed_operations": completed,
                "skipped_operations": skipped,
                "chain_steps": chain_steps,
                "current_step": next_step,
                "total_steps": total_steps,
                "language": lang,
            })
            say(blocks=blocks, thread_ts=thread_ts, channel=channel)
        else:
            thread_store.clear(thread_ts)
            in_chain = bool(chain_steps) and len(chain_steps) > 1
            if in_chain and completed:
                site_id = state.get("data", {}).get("site_id", "") if state else ""
                completed_ops = {item["operation"] for item in completed}
                summary = build_chain_final_summary(site_id, chain_steps, completed_ops, set(skipped))
                say(text=summary, thread_ts=thread_ts, channel=channel)
            elif in_chain:
                say(text="❌ Tüm adımlar atlandı.", thread_ts=thread_ts, channel=channel)
            elif lang == "tr":
                say(text="❌ İptal edildi. Yanlış anladıysam tekrar yazabilirsiniz.", thread_ts=thread_ts, channel=channel)
            else:
                say(text="❌ Cancelled. If I misunderstood, feel free to rephrase.", thread_ts=thread_ts, channel=channel)


def _execute_write(sheets: SheetsService, operation: str, data: dict[str, Any]) -> str | None:
    """Execute the write operation to the correct sheet tab. Returns ticket_id for new support logs."""
    if operation == "log_support":
        return sheets.append_support_log(data)

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
        last_verified = data.get("last_verified")
        updates = {k: v for k, v in data.items() if k not in ("site_id", "last_verified") and v}
        if last_verified:
            updates["Last Verified"] = last_verified
        if updates:
            sheets.update_implementation(site_id, updates)

    elif operation == "update_stock":
        sheets.append_stock(data)

    return None


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


def _build_readback(sheets: SheetsService, operation: str, data: dict[str, Any], ticket_id: str | None = None) -> str:
    """Build a contextual readback summary after a write."""
    site_id = data.get("site_id", "")
    if not site_id:
        return ""

    try:
        if operation == "log_support":
            logs = sheets.read_support_log(site_id)
            total = len(logs)
            open_count = sum(1 for l in logs if l.get("Status") not in ("Resolved",))
            tid = f" (`{ticket_id}`)" if ticket_id else ""
            return f"📊 `{site_id}`{tid}: {total} toplam kayıt, {open_count} açık ticket."

        elif operation == "update_support":
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


