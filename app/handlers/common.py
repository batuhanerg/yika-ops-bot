"""Shared message processing logic used by both mention and DM handlers."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.handlers.threads import ThreadStore
from app.models.operations import TEAM_MEMBERS
from app.services.claude import ClaudeService
from app.services.sheets import SheetsService
from app.services.site_resolver import SiteResolver
from app.utils.formatters import (
    format_confirmation_message,
    format_error_message,
    format_help_text,
    format_query_response,
)
from app.utils.validators import validate_required_fields

logger = logging.getLogger(__name__)

# Shared singletons (initialized in main.py)
thread_store = ThreadStore()
_claude: ClaudeService | None = None
_sheets: SheetsService | None = None


def get_claude() -> ClaudeService:
    global _claude
    if _claude is None:
        _claude = ClaudeService()
    return _claude


def get_sheets() -> SheetsService:
    global _sheets
    if _sheets is None:
        _sheets = SheetsService()
    return _sheets


def _resolve_user_name(client, user_id: str) -> str:
    """Get display name for a Slack user ID."""
    try:
        result = client.users_info(user=user_id)
        profile = result["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or "Unknown"
    except Exception:
        return "Unknown"


def _get_site_resolver() -> SiteResolver:
    """Build a SiteResolver from the current Sites tab."""
    sheets = get_sheets()
    sites = sheets.read_sites()
    return SiteResolver(sites)


def process_message(
    text: str,
    user_id: str,
    channel: str,
    thread_ts: str,
    say,
    client,
) -> None:
    """Core message processing pipeline: parse → validate → confirm/ask."""
    # Handle help command
    if text.lower().strip() in ("yardım", "yardim", "help"):
        say(blocks=format_help_text(), thread_ts=thread_ts)
        return

    # Handle greetings
    if text.lower().strip() in ("merhaba", "selam", "hello", "hi"):
        say(
            text="Merhaba! Ben Mustafa, ERG Controls operasyon asistanınızım. Size nasıl yardımcı olabilirim? (`yardım` yazarak komutları görebilirsiniz)",
            thread_ts=thread_ts,
        )
        return

    sender_name = _resolve_user_name(client, user_id)

    # Check for existing thread state (multi-turn)
    existing_state = thread_store.get(thread_ts)
    thread_context = None
    if existing_state and existing_state.get("messages"):
        thread_context = existing_state["messages"]

    # Parse with Claude
    try:
        claude = get_claude()
        result = claude.parse_message(
            message=text,
            sender_name=sender_name,
            thread_context=thread_context,
        )
    except Exception as e:
        logger.exception("Claude API error")
        say(text="Mesajınızı işleyemiyorum, lütfen tekrar deneyin.", thread_ts=thread_ts)
        return

    # Handle errors from Claude
    if result.error == "future_date":
        say(
            blocks=format_error_message("future_date"),
            thread_ts=thread_ts,
        )
        return

    if result.error:
        say(text=f"Hata: {result.error}", thread_ts=thread_ts)
        return

    # Handle help operation
    if result.operation == "help" and not existing_state:
        say(blocks=format_help_text(), thread_ts=thread_ts)
        return

    # Handle query (read-only, no confirmation needed)
    if result.operation == "query" and not existing_state:
        _handle_query(result.data, thread_ts, say)
        return

    # Multi-turn enforcement: keep the same operation and merge data
    if existing_state and existing_state.get("operation"):
        original_op = existing_state["operation"]
        original_data = existing_state.get("data", {})

        # Force operation back to the original
        result.operation = original_op

        # Merge: start with original data, overlay new non-empty fields
        merged = {**original_data}
        for k, v in result.data.items():
            if v and k != "_row_index":  # don't overwrite with empty, preserve internal keys
                merged[k] = v
        result.data = merged

    # Validate missing fields against our actual required fields logic
    # (Claude may over-report, e.g. root_cause when status is Open)
    actual_missing = validate_required_fields(result.operation, result.data)
    result.missing_fields = [f for f in result.missing_fields if f in actual_missing]

    # Build conversation history for multi-turn context
    messages = thread_context or []
    messages.append({"role": "user", "content": f"[Sender: {sender_name}]\n{text}"})
    assistant_json = json.dumps({"operation": result.operation, "data": result.data}, ensure_ascii=False)
    messages.append({"role": "assistant", "content": assistant_json})

    # Resolve site if needed
    site_id = result.data.get("site_id", "")
    if site_id and not _is_valid_site_id_format(site_id) and result.operation != "create_site":
        resolver = _get_site_resolver()
        matches = resolver.resolve(site_id)
        if len(matches) == 0:
            sheets = get_sheets()
            all_sites = sheets.read_sites()
            available = [s["Site ID"] for s in all_sites]
            say(
                blocks=format_error_message("unknown_site", site_name=site_id, available_sites=available),
                thread_ts=thread_ts,
            )
            return
        elif len(matches) == 1:
            result.data["site_id"] = matches[0]["Site ID"]
        else:
            sites_text = "\n".join(f"• `{m['Site ID']}` — {m.get('Customer', '')}" for m in matches)
            say(
                text=f"Birden fazla site eşleşti. Hangisini kastediyorsunuz?\n{sites_text}",
                thread_ts=thread_ts,
            )
            return

    # Resolve update_support row index
    if result.operation == "update_support" and "_row_index" not in result.data:
        resolved_site_id = result.data.get("site_id", "")
        if resolved_site_id:
            sheets = get_sheets()
            row_index = sheets.find_support_log_row(resolved_site_id)
            if row_index:
                result.data["_row_index"] = row_index
            else:
                say(
                    text=f"`{resolved_site_id}` için güncellenecek destek kaydı bulunamadı.",
                    thread_ts=thread_ts,
                )
                return

    # Check for missing fields
    if result.missing_fields:
        thread_store.set(thread_ts, {
            "operation": result.operation,
            "user_id": user_id,
            "data": result.data,
            "missing_fields": result.missing_fields,
            "messages": messages,
            "language": result.language,
        })

        # Build missing fields message
        field_names = ", ".join(f"`{f}`" for f in result.missing_fields)
        if result.language == "tr":
            say(
                text=f"Eksik bilgiler var: {field_names}\nLütfen bu bilgileri gönderin.",
                thread_ts=thread_ts,
            )
        else:
            say(
                text=f"Missing information: {field_names}\nPlease provide these details.",
                thread_ts=thread_ts,
            )
        return

    # Check warnings
    if result.warnings and "old_date" in result.warnings:
        # Store state with warning, ask for confirmation
        thread_store.set(thread_ts, {
            "operation": result.operation,
            "user_id": user_id,
            "data": result.data,
            "missing_fields": [],
            "pending_warning": "old_date",
            "messages": messages,
            "language": result.language,
        })
        say(
            text="⚠️ Bu kayıt 90 günden eski. Devam etmek istiyor musunuz?",
            thread_ts=thread_ts,
        )
        return

    # All fields present — show confirmation
    _show_confirmation(result.operation, result.data, user_id, thread_ts, say, text, sender_name, messages)


def _show_confirmation(
    operation: str,
    data: dict[str, Any],
    user_id: str,
    thread_ts: str,
    say,
    raw_message: str,
    sender_name: str,
    messages: list[dict] | None = None,
) -> None:
    """Show formatted confirmation with buttons and store state."""
    display_data = {**data, "operation": operation}
    blocks = format_confirmation_message(display_data)

    thread_store.set(thread_ts, {
        "operation": operation,
        "user_id": user_id,
        "data": data,
        "missing_fields": [],
        "raw_message": raw_message,
        "sender_name": sender_name,
        "messages": messages or [],
    })

    say(blocks=blocks, thread_ts=thread_ts)


def _handle_query(data: dict[str, Any], thread_ts: str, say) -> None:
    """Handle read-only queries."""
    query_type = data.get("query_type", "site_summary")
    site_id = data.get("site_id")
    sheets = get_sheets()

    try:
        if query_type in ("site_summary", "site_status"):
            if not site_id:
                say(text="Hangi site hakkında bilgi istiyorsunuz?", thread_ts=thread_ts)
                return
            sites = sheets.read_sites()
            site_info = next((s for s in sites if s["Site ID"] == site_id), None)
            if not site_info:
                say(text=f"`{site_id}` bulunamadı.", thread_ts=thread_ts)
                return
            support = sheets.read_support_log(site_id)
            hardware = sheets.read_hardware(site_id)
            open_issues = sum(1 for s in support if s.get("Status") not in ("Resolved",))
            total_devices = sum(int(h.get("Qty", 0)) for h in hardware)
            visits = [s["Received Date"] for s in support if s.get("Type") == "Visit"]
            last_visit = max(visits) if visits else "—"
            summary = {
                "site_id": site_id,
                "customer": site_info.get("Customer", ""),
                "status": site_info.get("Contract Status", ""),
                "open_issues": open_issues,
                "total_devices": total_devices,
                "last_visit": last_visit,
            }
            say(blocks=format_query_response("site_summary", summary), thread_ts=thread_ts)

        elif query_type == "open_issues":
            if site_id:
                support = sheets.read_support_log(site_id)
            else:
                support = sheets.read_support_log()
            open_entries = [s for s in support if s.get("Status") not in ("Resolved",)]
            if not open_entries:
                say(text="Açık ticket bulunamadı.", thread_ts=thread_ts)
                return
            lines = []
            for entry in open_entries:
                lines.append(f"• `{entry['Site ID']}` — {entry.get('Issue Summary', '')} ({entry.get('Status', '')})")
            say(text=f"*Açık Ticket'lar ({len(open_entries)}):*\n" + "\n".join(lines), thread_ts=thread_ts)

        elif query_type == "stock":
            stock = sheets.read_stock()
            if not stock:
                say(text="Stok bilgisi bulunamadı.", thread_ts=thread_ts)
                return
            lines = []
            for item in stock:
                lines.append(f"• {item['Device Type']} x{item['Qty']} ({item.get('Condition', '')}) — {item.get('Location', '')}")
            say(text=f"*Stok Durumu:*\n" + "\n".join(lines), thread_ts=thread_ts)

        else:
            say(text=f"Bu sorgu türü henüz desteklenmiyor: {query_type}", thread_ts=thread_ts)

    except Exception as e:
        logger.exception("Query error")
        say(text="Sorgu sırasında hata oluştu, lütfen tekrar deneyin.", thread_ts=thread_ts)


def _is_valid_site_id_format(s: str) -> bool:
    """Quick check if string looks like a Site ID."""
    import re
    return bool(re.match(r"^[A-Z]{2,4}-[A-Z]{2}-\d{2}$", s))
