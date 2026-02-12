"""Shared message processing logic used by both mention and DM handlers."""

from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Any

from app.handlers.threads import ThreadStore
from app.models.operations import TEAM_MEMBERS
from app.services.claude import ClaudeService
from app.services.sheets import SheetsService
from app.services.site_resolver import SiteResolver
from app.services.data_quality import find_missing_data, find_stale_data
from app.utils.formatters import (
    build_chain_roadmap,
    format_confirmation_message,
    format_data_quality_response,
    format_error_message,
    format_feedback_buttons,
    format_help_text,
    format_query_response,
)
from app.utils.missing_fields import enforce_must_fields, format_missing_fields_message
from app.utils.validators import validate_required_fields

logger = logging.getLogger(__name__)

# Shared singletons (initialized in main.py)
thread_store = ThreadStore()

# Event deduplication to prevent double-processing from Slack retries
_processed_events: dict[str, float] = {}
_processed_lock = Lock()
_DEDUP_TTL = 30  # seconds


def _is_duplicate_event(event_ts: str) -> bool:
    """Check if this event was already processed. Returns True if duplicate."""
    now = time.time()
    with _processed_lock:
        # Clean stale entries
        stale = [k for k, v in _processed_events.items() if now - v > _DEDUP_TTL]
        for k in stale:
            del _processed_events[k]
        if event_ts in _processed_events:
            return True
        _processed_events[event_ts] = now
        return False
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
    event_ts: str | None = None,
) -> None:
    """Core message processing pipeline: parse → validate → confirm/ask."""
    # Deduplicate Slack retries and dual-event deliveries
    if event_ts and _is_duplicate_event(event_ts):
        logger.info("Skipping duplicate event: %s", event_ts)
        return

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

    # Handle explicit feedback messages (e.g., "@mustafa feedback: ..." or "@mustafa geri bildirim: ...")
    text_lower = text.lower().strip()
    if text_lower.startswith(("feedback:", "feedback ", "geri bildirim:", "geri bildirim ")):
        # Strip the prefix to get the actual feedback text
        for prefix in ("feedback:", "feedback ", "geri bildirim:", "geri bildirim "):
            if text_lower.startswith(prefix):
                feedback_text = text[len(prefix):].strip()
                break
        sender_name = _resolve_user_name(client, user_id)
        try:
            sheets = get_sheets()
            sheets.append_feedback(
                user=sender_name,
                operation="explicit",
                site_id="",
                ticket_id="",
                rating="comment",
                expected_behavior=feedback_text,
                original_message=text,
            )
            say(text="Teşekkürler, geri bildiriminiz kaydedildi!", thread_ts=thread_ts)
        except Exception:
            logger.exception("Explicit feedback write error")
            say(text="Geri bildirim kaydedilemedi, lütfen tekrar deneyin.", thread_ts=thread_ts)
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

    logger.info("Parsed: op=%s data_keys=%s missing=%s", result.operation, list(result.data.keys()), result.missing_fields)

    # Handle errors from Claude
    if result.error == "future_date":
        say(
            blocks=format_error_message("future_date"),
            thread_ts=thread_ts,
        )
        return

    if result.operation == "error" or result.error:
        if result.language == "en":
            say(text="Something went wrong, please try again.", thread_ts=thread_ts)
        else:
            say(text="Bir sorun oluştu, lütfen tekrar deneyin.", thread_ts=thread_ts)
        return

    # Handle clarify — ask a follow-up question, keep thread state alive
    if result.operation == "clarify":
        clarify_msg = result.data.get("message", "")
        if clarify_msg:
            # Carry forward identifiers from existing state so they survive the clarify round-trip
            context_data: dict[str, Any] = {}
            if existing_state:
                prev_data = existing_state.get("data", {})
                for key in ("site_id", "ticket_id"):
                    if prev_data.get(key):
                        context_data[key] = prev_data[key]

            # Store thread state so the user's reply continues the conversation
            messages = thread_context or []
            messages.append({"role": "user", "content": f"[Sender: {sender_name}]\n{text}"})
            messages.append({"role": "assistant", "content": json.dumps({"operation": "clarify", "message": clarify_msg}, ensure_ascii=False)})
            thread_store.set(thread_ts, {
                "operation": "clarify",
                "user_id": user_id,
                "data": context_data,
                "missing_fields": [],
                "messages": messages,
                "language": result.language,
            })
            say(text=clarify_msg, thread_ts=thread_ts)
        return

    # Handle help operation
    if result.operation == "help" and not existing_state:
        say(blocks=format_help_text(), thread_ts=thread_ts)
        return

    # Handle query (read-only, no confirmation needed)
    if result.operation == "query":
        # Build conversation history for query context
        q_messages = thread_context or []
        q_messages.append({"role": "user", "content": f"[Sender: {sender_name}]\n{text}"})
        q_messages.append({"role": "assistant", "content": json.dumps({"operation": "query", "data": result.data}, ensure_ascii=False)})
        _handle_query(result.data, thread_ts, say, user_id, q_messages, result.language)
        return

    # Multi-turn data merge: only when refining the SAME operation
    if existing_state and existing_state.get("operation"):
        original_op = existing_state["operation"]
        original_data = existing_state.get("data", {})

        # Query/clarify → write: inherit identifiers (site_id, ticket_id), don't merge data
        if original_op in ("query", "clarify"):
            for key in ("site_id", "ticket_id"):
                if original_data.get(key) and not result.data.get(key):
                    result.data[key] = original_data[key]
        elif result.operation == original_op:
            # Same operation — merge previous data with new fields
            merged = {**original_data}
            for k, v in result.data.items():
                if v and k != "_row_index":
                    merged[k] = v
            result.data = merged
        elif existing_state.get("missing_fields") or existing_state.get("awaiting_chain_input"):
            # We were waiting for missing fields or chain step input — keep original
            # operation and merge (Claude may re-classify the reply as a different operation)
            result.operation = original_op
            merged = {**original_data}
            for k, v in result.data.items():
                if v and k != "_row_index":
                    merged[k] = v
            result.data = merged
        else:
            # Different operation — user is correcting, start fresh
            thread_store.clear(thread_ts)
            existing_state = None
            thread_context = None

    # Enforce: root_cause "Pending" is only valid for Open status
    if result.data.get("root_cause") == "Pending" and result.data.get("status") not in ("Open", None, ""):
        del result.data["root_cause"]

    # Validate missing fields against our actual required fields logic
    # (Claude may over-report, e.g. root_cause when status is Open)
    actual_missing = validate_required_fields(result.operation, result.data)
    result.missing_fields = [f for f in result.missing_fields if f in actual_missing]
    # Also add any newly-missing fields that Claude didn't report
    for f in actual_missing:
        if f not in result.missing_fields:
            result.missing_fields.append(f)

    # Enforce FIELD_REQUIREMENTS must fields (catches fields Claude missed)
    facility_type = result.data.get("facility_type")
    result.missing_fields = enforce_must_fields(
        result.operation, result.data, result.missing_fields,
        facility_type=facility_type,
    )

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
                text=f"Birden fazla saha eşleşti. Hangisini kastediyorsunuz?\n{sites_text}",
                thread_ts=thread_ts,
            )
            return

    # Resolve update_support row index
    if result.operation == "update_support" and "_row_index" not in result.data:
        ticket_id = result.data.get("ticket_id", "")
        resolved_site_id = result.data.get("site_id", "")
        sheets = get_sheets()

        if ticket_id:
            row_index = sheets.find_support_log_row(ticket_id=ticket_id)
        elif resolved_site_id:
            # Check if there are multiple open tickets — if so, ask which one
            open_tickets = sheets.list_open_tickets(resolved_site_id)
            if len(open_tickets) > 1:
                lines = [f"• `{t['ticket_id']}` — {t['issue_summary']} ({t['status']}, {t['received_date']})" for t in open_tickets]
                msg = f"`{resolved_site_id}` için birden fazla açık ticket var. Hangisini güncellemek istiyorsunuz?\n" + "\n".join(lines)
                # Store state so user can reply with ticket ID
                thread_store.set(thread_ts, {
                    "operation": "update_support",
                    "user_id": user_id,
                    "data": result.data,
                    "missing_fields": [],
                    "messages": messages,
                    "language": result.language,
                })
                say(text=msg, thread_ts=thread_ts)
                return
            row_index = sheets.find_support_log_row(site_id=resolved_site_id)
        else:
            row_index = None

        if row_index:
            result.data["_row_index"] = row_index
        else:
            target = ticket_id or resolved_site_id or "?"
            say(
                text=f"`{target}` için güncellenecek destek kaydı bulunamadı.",
                thread_ts=thread_ts,
            )
            return

    # Check for missing fields
    if result.missing_fields:
        msg_text, has_blockers = format_missing_fields_message(
            result.missing_fields, result.operation, language=result.language,
            facility_type=facility_type,
        )

        if has_blockers:
            # Must fields missing — block until user provides them
            missing_state: dict[str, Any] = {
                "operation": result.operation,
                "user_id": user_id,
                "data": result.data,
                "missing_fields": result.missing_fields,
                "messages": messages,
                "language": result.language,
            }
            # Preserve chain context if present
            if existing_state:
                for key in ("chain_steps", "current_step", "total_steps",
                            "completed_operations", "skipped_operations",
                            "pending_operations", "raw_message", "sender_name"):
                    if key in existing_state:
                        missing_state[key] = existing_state[key]
            thread_store.set(thread_ts, missing_state)
            say(text=msg_text, thread_ts=thread_ts)
            return

        # Only important fields missing — proceed to confirmation with a note
        if msg_text:
            say(text=msg_text, thread_ts=thread_ts)

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

    # Normalize create_site data and extract chained operations
    pending_ops = None
    if result.operation == "create_site":
        extracted_extras = _normalize_create_site_data(result.data)
        # Prefer Claude's explicit extra_operations, fall back to extracted from data
        pending_ops = result.extra_operations or extracted_extras

        # Duplicate site_id check
        site_id = result.data.get("site_id", "")
        if site_id:
            try:
                sheets = get_sheets()
                existing = sheets.read_sites()
                if any(s["Site ID"] == site_id for s in existing):
                    say(
                        text=(
                            f"⚠️ `{site_id}` zaten mevcut. Yeni saha oluşturmak yerine "
                            f"güncellemek mi istiyorsunuz?\n"
                            f"Yeni saha olarak devam etmek istiyorsanız lütfen farklı bir Site ID belirtin."
                        ),
                        thread_ts=thread_ts,
                    )
                    return
            except Exception:
                pass  # Don't block on sheet read errors

    # Preserve chain context from existing thread state
    chain_ctx = None
    if existing_state and existing_state.get("chain_steps"):
        chain_ctx = {
            "chain_steps": existing_state["chain_steps"],
            "current_step": existing_state.get("current_step", 1),
            "total_steps": existing_state.get("total_steps", 1),
            "completed_operations": existing_state.get("completed_operations", []),
            "skipped_operations": existing_state.get("skipped_operations", []),
        }
        if not pending_ops and existing_state.get("pending_operations"):
            pending_ops = existing_state["pending_operations"]

    # All fields present — show confirmation
    _show_confirmation(result.operation, result.data, user_id, thread_ts, say, text, sender_name, messages, result.language, pending_ops, chain_ctx)


def _show_confirmation(
    operation: str,
    data: dict[str, Any],
    user_id: str,
    thread_ts: str,
    say,
    raw_message: str,
    sender_name: str,
    messages: list[dict] | None = None,
    language: str = "tr",
    pending_operations: list[dict] | None = None,
    chain_state: dict[str, Any] | None = None,
) -> None:
    """Show formatted confirmation with buttons and store state."""
    step_info = None
    cs: dict[str, Any] = {}

    if chain_state:
        # Continuing an existing chain
        cs = {**chain_state}
        step_info = (cs.get("current_step", 1), cs.get("total_steps", 1))
    elif pending_operations:
        chain_steps = [operation] + [op["operation"] for op in pending_operations]
        total = len(chain_steps)
        step_info = (1, total)
        cs = {
            "chain_steps": chain_steps,
            "current_step": 1,
            "total_steps": total,
            "completed_operations": [],
            "skipped_operations": [],
        }
        # Post roadmap before the first card
        roadmap = build_chain_roadmap(chain_steps)
        say(text=roadmap, thread_ts=thread_ts)

    display_data = {**data, "operation": operation}
    blocks = format_confirmation_message(display_data, step_info=step_info)

    state: dict[str, Any] = {
        "operation": operation,
        "user_id": user_id,
        "data": data,
        "missing_fields": [],
        "raw_message": raw_message,
        "sender_name": sender_name,
        "messages": messages or [],
        "language": language,
    }
    if pending_operations:
        state["pending_operations"] = pending_operations
    state.update(cs)

    thread_store.set(thread_ts, state)

    say(blocks=blocks, thread_ts=thread_ts)


def _handle_query(
    data: dict[str, Any],
    thread_ts: str,
    say,
    user_id: str = "",
    messages: list[dict] | None = None,
    language: str = "tr",
) -> None:
    """Handle read-only queries."""
    query_type = data.get("query_type", "site_summary")
    site_id = data.get("site_id")
    sheets = get_sheets()

    def _store_query_state() -> None:
        """Store thread state so follow-up queries work, with feedback."""
        if user_id:
            thread_store.set(thread_ts, {
                "operation": "query",
                "user_id": user_id,
                "data": data,
                "missing_fields": [],
                "messages": messages or [],
                "language": language,
                "feedback_pending": True,
                "sender_name": user_id,
                "raw_message": "",
            })

    try:
        if query_type in ("site_summary", "site_status"):
            if not site_id:
                say(text="Hangi saha hakkında bilgi istiyorsunuz?", thread_ts=thread_ts)
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
                _store_query_state()
                return
            lines = []
            for entry in open_entries:
                lines.append(f"• `{entry['Site ID']}` — {entry.get('Issue Summary', '')} ({entry.get('Status', '')})")
            say(text=f"*Açık Ticket'lar ({len(open_entries)}):*\n" + "\n".join(lines), thread_ts=thread_ts)

        elif query_type == "stock":
            stock = sheets.read_stock()
            if not stock:
                say(text="Stok bilgisi bulunamadı.", thread_ts=thread_ts)
                _store_query_state()
                return
            lines = []
            for item in stock:
                lines.append(f"• {item['Device Type']} x{item['Qty']} ({item.get('Condition', '')}) — {item.get('Location', '')}")
            say(text=f"*Stok Durumu:*\n" + "\n".join(lines), thread_ts=thread_ts)

        elif query_type == "implementation":
            if not site_id:
                say(text="Hangi sahanın kurulum detaylarını görmek istiyorsunuz?", thread_ts=thread_ts)
                return
            impl = sheets.read_implementation(site_id)
            if not impl:
                say(text=f"`{site_id}` için kurulum detayı bulunamadı.", thread_ts=thread_ts)
                _store_query_state()
                return
            lines = [f"*⚙️ `{site_id}` — Kurulum Detayları:*"]
            for key, value in impl.items():
                if key == "Site ID" or not value:
                    continue
                lines.append(f"• *{key}:* {value}")
            say(text="\n".join(lines), thread_ts=thread_ts)

        elif query_type == "hardware":
            if not site_id:
                say(text="Hangi sahanın donanım envanterini görmek istiyorsunuz?", thread_ts=thread_ts)
                return
            hw = sheets.read_hardware(site_id)
            if not hw:
                say(text=f"`{site_id}` için donanım kaydı bulunamadı.", thread_ts=thread_ts)
                _store_query_state()
                return
            lines = [f"*🔧 `{site_id}` — Donanım Envanteri:*"]
            for item in hw:
                parts = [f"{item.get('Device Type', '?')} x{item.get('Qty', '?')}"]
                if item.get("HW Version"):
                    parts.append(f"HW:{item['HW Version']}")
                if item.get("FW Version"):
                    parts.append(f"FW:{item['FW Version']}")
                if item.get("Notes"):
                    parts.append(f"({item['Notes']})")
                lines.append(f"• {' '.join(parts)}")
            total = sum(int(h.get("Qty", 0)) for h in hw)
            lines.append(f"_Toplam: {total} cihaz_")
            say(text="\n".join(lines), thread_ts=thread_ts)

        elif query_type == "support_history":
            if not site_id:
                say(text="Hangi sahanın destek geçmişini görmek istiyorsunuz?", thread_ts=thread_ts)
                return
            support = sheets.read_support_log(site_id)
            if not support:
                say(text=f"`{site_id}` için destek kaydı bulunamadı.", thread_ts=thread_ts)
                _store_query_state()
                return
            lines = [f"*📋 `{site_id}` — Destek Geçmişi ({len(support)} kayıt):*"]
            for entry in support[-10:]:  # Last 10 entries
                status_icon = "✅" if entry.get("Status") == "Resolved" else "🔴"
                tid = entry.get("Ticket ID", "")
                date = entry.get("Received Date", "")
                summary = entry.get("Issue Summary", "")[:60]
                lines.append(f"• {status_icon} `{tid}` ({date}) — {summary}")
            if len(support) > 10:
                lines.append(f"_...ve {len(support) - 10} kayıt daha_")
            say(text="\n".join(lines), thread_ts=thread_ts)

        elif query_type == "ticket_detail":
            ticket_id = data.get("ticket_id", "")
            if not ticket_id:
                say(text="Hangi ticket'ın detaylarını görmek istiyorsunuz? (örn. SUP-001)", thread_ts=thread_ts)
                return
            # Search all support logs for the ticket
            all_support = sheets.read_support_log(site_id) if site_id else sheets.read_support_log()
            entry = next((s for s in all_support if s.get("Ticket ID") == ticket_id), None)
            if not entry:
                say(text=f"`{ticket_id}` bulunamadı.", thread_ts=thread_ts)
                _store_query_state()
                return
            status_icon = "✅" if entry.get("Status") == "Resolved" else "🔴"
            lines = [f"*{status_icon} `{ticket_id}` — Ticket Detayı:*"]
            for key, value in entry.items():
                if not value:
                    continue
                lines.append(f"• *{key}:* {value}")
            say(text="\n".join(lines), thread_ts=thread_ts)

        elif query_type == "missing_data":
            sites = sheets.read_sites()
            hardware = sheets.read_hardware(site_id) if site_id else sheets.read_hardware()
            support = sheets.read_support_log(site_id) if site_id else sheets.read_support_log()
            implementation = sheets.read_all_implementation()
            issues = find_missing_data(sites=sites, hardware=hardware, support=support, site_id=site_id, implementation=implementation)
            blocks = format_data_quality_response("missing_data", issues, site_id)
            say(blocks=blocks, thread_ts=thread_ts)

        elif query_type == "stale_data":
            hardware = sheets.read_hardware(site_id) if site_id else sheets.read_hardware()
            implementation = sheets.read_all_implementation()
            issues = find_stale_data(hardware=hardware, implementation=implementation, site_id=site_id)
            blocks = format_data_quality_response("stale_data", issues, site_id)
            say(blocks=blocks, thread_ts=thread_ts)

        else:
            say(text=f"Bu sorgu türü henüz desteklenmiyor: {query_type}", thread_ts=thread_ts)

        _store_query_state()
        say(text="Faydalı oldu mu?", blocks=format_feedback_buttons(context="query"), thread_ts=thread_ts)

    except Exception as e:
        logger.exception("Query error")
        say(text="Sorgu sırasında hata oluştu, lütfen tekrar deneyin.", thread_ts=thread_ts)


def _is_valid_site_id_format(s: str) -> bool:
    """Quick check if string looks like a Site ID."""
    import re
    return bool(re.match(r"^[A-Z]{2,4}-[A-Z]{2}-\d{2}$", s))


# --- Create Site normalization ---

_COUNTRY_NAMES = {
    "TR": "Turkey", "EG": "Egypt", "SA": "Saudi Arabia",
    "AE": "UAE", "US": "USA", "UK": "United Kingdom",
}

# Valid keys for the Sites tab (snake_case)
_VALID_SITE_KEYS = {
    "site_id", "customer", "city", "country", "address", "facility_type",
    "dashboard_link", "supervisor_1", "phone_1", "email_1",
    "supervisor_2", "phone_2", "email_2", "go_live_date", "contract_status",
    "notes", "whatsapp_group",
}


def _normalize_create_site_data(data: dict[str, Any]) -> list[dict] | None:
    """Normalize create_site data: flatten contacts, fix field names.

    Returns extracted extra_operations if hardware/impl/support data is found in data.
    """
    extra_ops: list[dict] = []

    # Flatten contacts array → supervisor_1/phone_1/email_1 etc.
    contacts = data.pop("contacts", None)
    if contacts and isinstance(contacts, list):
        for i, contact in enumerate(contacts[:2], start=1):
            if isinstance(contact, dict):
                data.setdefault(f"supervisor_{i}", contact.get("name", ""))
                data.setdefault(f"phone_{i}", contact.get("phone", ""))
                data.setdefault(f"email_{i}", contact.get("email", ""))

    # Map dashboard_url → dashboard_link
    if "dashboard_url" in data:
        if "dashboard_link" not in data:
            data["dashboard_link"] = data.pop("dashboard_url")
        else:
            data.pop("dashboard_url")

    # Normalize country code to full name
    country = data.get("country", "")
    if country and len(country) <= 3:
        upper = country.upper()
        if upper in _COUNTRY_NAMES:
            data["country"] = _COUNTRY_NAMES[upper]

    # Extract hardware entries → update_hardware
    hardware = data.pop("hardware", None)
    if hardware:
        entries = hardware.get("entries", []) if isinstance(hardware, dict) else (hardware if isinstance(hardware, list) else [])
        if entries:
            extra_ops.append({"operation": "update_hardware", "data": {"entries": entries}})

    # Extract implementation data → update_implementation
    implementation = data.pop("implementation", None)
    if implementation and isinstance(implementation, dict):
        extra_ops.append({"operation": "update_implementation", "data": implementation})

    # Extract support log data → log_support
    last_visit_date = data.pop("last_visit_date", None)
    last_visit_notes = data.pop("last_visit_notes", None)
    if last_visit_date or last_visit_notes:
        support_data: dict[str, Any] = {}
        if last_visit_date:
            support_data["received_date"] = last_visit_date
        if last_visit_notes:
            support_data["issue_summary"] = last_visit_notes
        extra_ops.append({"operation": "log_support", "data": support_data})

    # Strip non-site keys from data
    for key in list(data.keys()):
        if key not in _VALID_SITE_KEYS:
            data.pop(key)

    # Always include hardware and implementation in the chain for completeness
    if not any(op["operation"] == "update_hardware" for op in extra_ops):
        extra_ops.append({"operation": "update_hardware", "data": {}})
    if not any(op["operation"] == "update_implementation" for op in extra_ops):
        extra_ops.append({"operation": "update_implementation", "data": {}})
    return extra_ops
