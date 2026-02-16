"""Scheduled report generation: weekly data quality + daily aging alerts.

Both functions return (blocks, text_fallback) tuples ready for
Slack chat.postMessage(). They do NOT post to Slack themselves.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.field_config.field_requirements import CONTEXT_RULES, FIELD_REQUIREMENTS
from app.services.data_quality import find_missing_data, find_stale_data
from app.utils.formatters import format_feedback_buttons


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_long_section(text: str, max_chars: int = 2900) -> list[str]:
    """Split text into chunks that fit within Slack's 3000-char block limit.

    Splits at newline boundaries so no line is cut mid-way.
    Returns a list of text chunks, each under max_chars.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    lines = text.split("\n")
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + (1 if current else 0)  # +1 for \n separator
        if current_len + line_len > max_chars and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def _append_section_blocks(blocks: list[dict], text: str) -> None:
    """Append one or more section blocks, splitting if text exceeds Slack limit."""
    for chunk in _split_long_section(text):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": chunk},
        })


_SECTION_CAP = 15


def _cap_lines(lines: list[str], total_count: int) -> list[str]:
    """Cap issue lines at _SECTION_CAP, appending '...ve N sorun daha' if needed.

    lines[0] is the header line; lines[1:] are the issue lines.
    """
    header = lines[0]
    issue_lines = lines[1:]
    if len(issue_lines) <= _SECTION_CAP:
        return lines
    capped = issue_lines[:_SECTION_CAP]
    remaining = len(issue_lines) - _SECTION_CAP
    capped.append(f"  ...ve {remaining} sorun daha")
    return [header] + capped


def _get_skipped_tabs(contract_status: str) -> set[str]:
    if contract_status == "Awaiting Installation":
        return set(CONTEXT_RULES["awaiting_installation"]["skip_tabs"])
    return set()


def _count_expected_fields(
    sites: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    support: list[dict[str, Any]],
    implementation: list[dict[str, Any]],
    stock: list[dict[str, Any]],
) -> tuple[int, int]:
    """Count (filled, total) must+important fields across all data.

    Returns (filled_count, total_count) for completeness percentage.
    """
    total = 0
    filled = 0

    fr = FIELD_REQUIREMENTS

    # Build skip-tab map per site
    site_skip: dict[str, set[str]] = {}
    site_facility: dict[str, str] = {}
    for site in sites:
        sid = site["Site ID"]
        site_skip[sid] = _get_skipped_tabs(site.get("Contract Status", ""))
        site_facility[sid] = site.get("Facility Type", "")

    # Column name mappings (reuse from data_quality)
    from app.services.data_quality import (
        _SITES_FIELD_TO_COLUMN,
        _HW_FIELD_TO_COLUMN,
        _IMPL_FIELD_TO_COLUMN,
        _SUPPORT_FIELD_TO_COLUMN,
        _STOCK_FIELD_TO_COLUMN,
    )

    # --- Sites ---
    for site in sites:
        for field_key in fr["sites"]["must"]:
            col = _SITES_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if site.get(col):
                filled += 1
        for field_key in fr["sites"].get("important", []):
            col = _SITES_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if site.get(col):
                filled += 1

    # --- Hardware ---
    for hw in hardware:
        sid = hw.get("Site ID", "")
        if "hardware_inventory" in site_skip.get(sid, set()):
            continue
        device = hw.get("Device Type", "")
        for field_key, rule in fr["hardware_inventory"].get("important_conditional", {}).items():
            col = _HW_FIELD_TO_COLUMN.get(field_key, field_key)
            if isinstance(rule, dict) and "except_device_types" in rule:
                if device in rule["except_device_types"]:
                    continue
            total += 1
            if hw.get(col):
                filled += 1

    # --- Implementation ---
    for impl in implementation:
        sid = impl.get("Site ID", "")
        if "implementation_details" in site_skip.get(sid, set()):
            continue
        ftype = site_facility.get(sid, "")
        for field_key in fr["implementation_details"]["must"]:
            col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if impl.get(col):
                filled += 1
        for field_key in fr["implementation_details"].get("important", []):
            col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if impl.get(col):
                filled += 1
        facility_must = fr["implementation_details"].get("must_when_facility_type", {})
        if ftype and ftype in facility_must:
            for field_key in facility_must[ftype]:
                col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
                total += 1
                if impl.get(col):
                    filled += 1

    # --- Support ---
    for entry in support:
        sid = entry.get("Site ID", "")
        if "support_log" in site_skip.get(sid, set()):
            continue
        status = entry.get("Status", "")
        for field_key, rule in fr["support_log"].get("important_conditional", {}).items():
            col = _SUPPORT_FIELD_TO_COLUMN.get(field_key, field_key)
            if isinstance(rule, dict):
                if "required_when_status_not" in rule:
                    if status in rule["required_when_status_not"]:
                        continue
                elif "required_when_status" in rule:
                    if status not in rule["required_when_status"]:
                        continue
            total += 1
            if entry.get(col):
                filled += 1

    # --- Stock ---
    for item in stock:
        for field_key in fr["stock"]["must"]:
            col = _STOCK_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if item.get(col):
                filled += 1
        for field_key in fr["stock"].get("important", []):
            col = _STOCK_FIELD_TO_COLUMN.get(field_key, field_key)
            total += 1
            if item.get(col):
                filled += 1

    return filled, total


# ---------------------------------------------------------------------------
# Weekly Report
# ---------------------------------------------------------------------------

def generate_weekly_report(
    sites: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    support: list[dict[str, Any]],
    implementation: list[dict[str, Any]],
    stock: list[dict[str, Any]],
    prev_snapshot: list[dict[str, str]] | None = None,
) -> tuple[list[dict], str]:
    """Generate the weekly data quality report.

    Returns (blocks, text_fallback).
    prev_snapshot: last week's issue list for resolution tracking (Item 4).
    """
    today_str = date.today().isoformat()

    # Collect all issues via existing data quality functions
    missing_issues = find_missing_data(
        sites=sites, hardware=hardware, support=support,
        implementation=implementation, stock=stock,
    )
    stale_issues = find_stale_data(
        hardware=hardware, implementation=implementation,
        stock=stock,
    )

    # Classify missing issues into buckets
    must_issues: list[dict[str, str]] = []
    important_issues: list[dict[str, str]] = []
    aging_issues: list[dict[str, str]] = []

    for issue in missing_issues:
        if issue.get("field") == "Aging":
            aging_issues.append(issue)
        elif issue.get("severity") == "must":
            must_issues.append(issue)
        elif issue.get("severity") == "important":
            important_issues.append(issue)

    # Build blocks
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"📋 Haftalık Veri Kalitesi Raporu — {today_str}"},
    })

    # Resolution tracking (Item 4 — only if prev_snapshot provided)
    if prev_snapshot is not None:
        # Build set of Awaiting Installation site IDs to exclude from
        # resolution (status change is not a "resolution")
        awaiting_sites = {
            s["Site ID"] for s in sites
            if s.get("Contract Status") == "Awaiting Installation"
        }

        current_issue_keys = set()
        for iss in must_issues:
            current_issue_keys.add((iss["site_id"], iss.get("tab", ""), iss.get("field", ""), "must"))
        for iss in important_issues:
            current_issue_keys.add((iss["site_id"], iss.get("tab", ""), iss.get("field", ""), "important"))

        # Filter out prev items whose site is now Awaiting Installation
        prev_must = [
            i for i in prev_snapshot
            if i.get("severity") == "must" and i["site_id"] not in awaiting_sites
        ]
        prev_important = [
            i for i in prev_snapshot
            if i.get("severity") == "important" and i["site_id"] not in awaiting_sites
        ]

        resolved_must = sum(
            1 for i in prev_must
            if (i["site_id"], i.get("tab", ""), i.get("field", ""), "must") not in current_issue_keys
        )
        resolved_important = sum(
            1 for i in prev_important
            if (i["site_id"], i.get("tab", ""), i.get("field", ""), "important") not in current_issue_keys
        )

        # Only show resolution section if there were previous issues to resolve
        parts = []
        if len(prev_must) > 0:
            parts.append(f"{resolved_must}/{len(prev_must)} acil sorun çözüldü")
        if len(prev_important) > 0:
            parts.append(f"{resolved_important}/{len(prev_important)} önemli sorun çözüldü")

        if parts:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📈 Geçen hafta: {', '.join(parts)}",
                },
            })

    # 🔴 Must issues
    if must_issues:
        # Group by site_id to sort by issue count (worst first)
        must_by_site: dict[str, list[dict[str, str]]] = {}
        for iss in must_issues:
            must_by_site.setdefault(iss["site_id"], []).append(iss)
        sorted_sites = sorted(must_by_site.items(), key=lambda x: len(x[1]), reverse=True)

        lines = [f"🔴 *Acil (zorunlu bilgi eksik): {len(must_issues)} sorun*"]
        for sid, issues_for_site in sorted_sites:
            for iss in issues_for_site:
                detail = iss["detail"]
                if iss.get("tab") == "Support Log":
                    lines.append(f"  • {sid}: {detail}")
                elif "sahipsiz" in detail:
                    lines.append(f"  • {detail}")
                else:
                    lines.append(f"  • {sid}: {iss['field']} eksik")
        lines = _cap_lines(lines, len(must_issues))
        _append_section_blocks(blocks, "\n".join(lines))

    # 🟡 Important issues
    if important_issues:
        # Group by (site_id, tab) to consolidate, deduplicate field names
        by_site_tab: dict[tuple[str, str], list[str]] = {}
        for iss in important_issues:
            key = (iss["site_id"], iss.get("tab", ""))
            field = iss.get("field", "")
            by_site_tab.setdefault(key, [])
            if field and field not in by_site_tab[key]:
                by_site_tab[key].append(field)

        # Sort by issue count descending
        sorted_important = sorted(by_site_tab.items(), key=lambda x: len(x[1]), reverse=True)

        lines = [f"🟡 *Önemli bilgi eksik: {len(important_issues)} sorun*"]
        for (sid, tab), fields in sorted_important:
            fields = [f for f in fields if f.strip() and f != "—"]
            if not fields:
                continue
            prefix = f"{sid}: {tab} — " if tab and tab != "Sites" else f"{sid}: "
            if len(fields) == 1:
                lines.append(f"  • {prefix}{fields[0]} boş")
            else:
                lines.append(f"  • {prefix}{', '.join(fields)} boş")
        lines = _cap_lines(lines, len(important_issues))
        _append_section_blocks(blocks, "\n".join(lines))

    # 🟠 Aging tickets
    if aging_issues:
        lines = [f"🟠 *Yaşlanan ticketlar (3+ gün): {len(aging_issues)} sorun*"]
        # Sort by days open descending (oldest first) — extract from detail
        sorted_aging = sorted(aging_issues, key=lambda iss: int(
            ''.join(c for c in iss["detail"].split("gündür")[0].split(":")[-1] if c.isdigit()) or '0'
        ), reverse=True)
        for iss in sorted_aging:
            sid = iss["site_id"]
            detail = iss["detail"]
            ticket_id = detail.split(":")[0].strip() if ":" in detail else ""
            summary = ""
            for entry in support:
                if entry.get("Ticket ID") == ticket_id:
                    summary = entry.get("Issue Summary", "")
                    break
            if summary:
                lines.append(f"  • {sid} {ticket_id}: {summary} — {detail.split(':', 1)[1].strip()}")
            else:
                lines.append(f"  • {sid}: {detail}")
        lines = _cap_lines(lines, len(aging_issues))
        _append_section_blocks(blocks, "\n".join(lines))

    # 🔵 Stale data
    if stale_issues:
        # Consolidate by (site_id, tab) — count how many rows are stale/missing
        by_site_tab_stale: dict[tuple[str, str], list[str]] = {}
        for iss in stale_issues:
            key = (iss["site_id"], iss["tab"])
            by_site_tab_stale.setdefault(key, []).append(iss["detail"])

        # Sort by issue count descending
        sorted_stale = sorted(by_site_tab_stale.items(), key=lambda x: len(x[1]), reverse=True)

        lines = [f"🔵 *Eski veriler (30+ gün): {len(stale_issues)} sorun*"]
        for (sid, tab), details in sorted_stale:
            missing_count = sum(1 for d in details if "yok" in d)
            stale_count = len(details) - missing_count
            parts = []
            if missing_count > 1:
                parts.append(f"{missing_count} cihazda Last Verified boş")
            elif missing_count == 1:
                parts.append("Last Verified boş")
            if stale_count > 1:
                parts.append(f"{stale_count} cihazda Last Verified eski")
            elif stale_count == 1:
                stale_detail = [d for d in details if "yok" not in d][0]
                parts.append(stale_detail)
            lines.append(f"  • {sid}: {tab} — {', '.join(parts)}")
        lines = _cap_lines(lines, len(stale_issues))
        _append_section_blocks(blocks, "\n".join(lines))

    # ✅ Overall status
    total_sites = len(sites)
    open_tickets = sum(
        1 for s in support if s.get("Status") and s["Status"] != "Resolved"
    )
    filled, total_fields = _count_expected_fields(
        sites, hardware, support, implementation, stock,
    )
    completeness = round(filled / total_fields * 100) if total_fields > 0 else 100

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"✅ *Genel durum:* {total_sites} saha, "
                f"{open_tickets} açık ticket, "
                f"%{completeness} veri tamamlılık"
            ),
        },
    })

    # Thread hint
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "Bu sorunları çözmek için bu thread'e yazabilirsiniz.\n"
                'Örnek: "EST-TR-01 internet provider ERG Controls, SSID deneme"'
            ),
        },
    })

    # Feedback buttons
    blocks.extend(format_feedback_buttons(context="report"))

    # Text fallback
    total_issues = len(must_issues) + len(important_issues) + len(aging_issues) + len(stale_issues)
    fallback = (
        f"Haftalık Veri Kalitesi Raporu — {today_str}: "
        f"{len(must_issues)} acil, {len(important_issues)} önemli, "
        f"{len(aging_issues)} yaşlanan, {len(stale_issues)} eski veri sorunu. "
        f"%{completeness} veri tamamlılık."
    )

    return blocks, fallback


# ---------------------------------------------------------------------------
# Daily Aging Alert
# ---------------------------------------------------------------------------

def generate_daily_aging_alert(
    support: list[dict[str, Any]],
) -> tuple[list[dict], str] | None:
    """Generate daily aging alert for tickets open >3 days.

    Returns (blocks, text_fallback) or None if no aging tickets.
    """
    aging_tickets: list[dict[str, Any]] = []

    for entry in support:
        status = entry.get("Status", "")
        if status == "Resolved":
            continue
        received = entry.get("Received Date", "")
        if not received:
            continue
        try:
            received_date = date.fromisoformat(received)
            days_open = (date.today() - received_date).days
            if days_open > 3:
                aging_tickets.append({
                    "site_id": entry.get("Site ID", "?"),
                    "ticket_id": entry.get("Ticket ID", "?"),
                    "issue_summary": entry.get("Issue Summary", ""),
                    "days_open": days_open,
                    "status": status,
                })
        except ValueError:
            continue

    if not aging_tickets:
        return None

    count = len(aging_tickets)
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"⚠️ *{count} ticket 3 günden fazladır açık:*",
        },
    })

    # Ticket list
    lines: list[str] = []
    for t in aging_tickets:
        lines.append(
            f"  • {t['site_id']} {t['ticket_id']}: "
            f"{t['issue_summary']} — {t['days_open']} gündür açık"
        )
    _append_section_blocks(blocks, "\n".join(lines))

    # Thread hint
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Bu thread'e yazarak güncelleyebilirsiniz.",
        },
    })

    # Feedback buttons
    blocks.extend(format_feedback_buttons(context="report"))

    fallback = f"{count} ticket 3 günden fazladır açık"

    return blocks, fallback
