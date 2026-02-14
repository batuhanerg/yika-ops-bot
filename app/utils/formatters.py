"""Slack Block Kit message formatting for confirmations, queries, errors, and help."""

from __future__ import annotations

from typing import Any

# --- Field display labels ---

FIELD_LABELS: dict[str, str] = {
    "ticket_id": "Ticket ID",
    "site_id": "Site ID",
    "received_date": "Received Date",
    "resolved_date": "Resolved Date",
    "type": "Type",
    "status": "Status",
    "root_cause": "Root Cause",
    "reported_by": "Reported By",
    "issue_summary": "Issue Summary",
    "resolution": "Resolution",
    "devices_affected": "Devices Affected",
    "responsible": "Responsible",
    "notes": "Notes",
    "customer": "Customer",
    "city": "City",
    "country": "Country",
    "facility_type": "Facility Type",
    "go_live_date": "Go-live Date",
    "contract_status": "Contract Status",
    "device_type": "Device Type",
    "qty": "Quantity",
    "hw_version": "HW Version",
    "fw_version": "FW Version",
    "location": "Location",
    "condition": "Condition",
    "query_type": "Query Type",
    "supervisor_1": "Supervisor 1",
    "phone_1": "Phone 1",
    "email_1": "Email 1",
    "supervisor_2": "Supervisor 2",
    "phone_2": "Phone 2",
    "email_2": "Email 2",
    "dashboard_link": "Dashboard Link",
    "address": "Address",
    "internet_provider": "Internet Provider",
    "ssid": "SSID",
    "password": "Password",
    "whatsapp_group": "WhatsApp Group",
    "dispenser_anchor_placement": "Dispenser Anchor Placement",
    "clean_hygiene_time": "Clean Hygiene Time",
    "hp_alert_time": "HP Alert Time",
    "hand_hygiene_time": "Hand Hygiene Time",
    "hand_hygiene_interval": "Hand Hygiene Interval",
    "hand_hygiene_type": "Hand Hygiene Type",
    # Column header keys (Claude returns these for implementation data)
    "SSID": "SSID",
    "Internet Provider": "Internet Provider",
    "Password": "Password",
    "Gateway placement": "Gateway Placement",
    "Charging dock placement": "Charging Dock Placement",
    "Dispenser anchor placement": "Dispenser Anchor Placement",
    "Handwash time": "Handwash Time",
    "Tag buzzer/vibration": "Tag Buzzer/Vibration",
    "Entry time": "Entry Time",
    "Dispenser anchor power type": "Dispenser Anchor Power Type",
    "Clean hygiene time": "Clean Hygiene Time",
    "HP alert time": "HP Alert Time",
    "Hand hygiene time": "Hand Hygiene Time",
    "Hand hygiene interval (dashboard)": "Hand Hygiene Interval",
    "Hand hygiene type": "Hand Hygiene Type",
    "Tag clean-to-red timeout": "Tag Clean-to-Red Timeout",
    "Other details": "Other Details",
}

OPERATION_TITLES: dict[str, str] = {
    "log_support": "Destek Kaydı / Support Log",
    "create_site": "Yeni Saha / New Site",
    "update_support": "Destek Güncelleme / Support Update",
    "update_site": "Saha Güncelleme / Site Update",
    "update_hardware": "Donanım Güncelleme / Hardware Update",
    "update_implementation": "Ayar Güncelleme / Implementation Update",
    "update_stock": "Stok Güncelleme / Stock Update",
}

CHAIN_LABELS: dict[str, str] = {
    "create_site": "saha",
    "update_hardware": "donanım",
    "update_implementation": "ayarlar",
    "log_support": "destek kaydı",
    "update_stock": "stok",
}

# Fields to skip in confirmation display
_SKIP_FIELDS = {"operation", "entries", "_future_date_warning", "_row_index"}


def format_confirmation_message(data: dict[str, Any], step_info: tuple[int, int] | None = None) -> list[dict]:
    """Format a confirmation message with all fields and confirm/cancel buttons."""
    operation = data.get("operation", "unknown")
    title = OPERATION_TITLES.get(operation, operation)

    blocks: list[dict] = []

    # Header (with step indicator if in chain)
    if step_info:
        current, total = step_info
        header_text = f"📋 Adım {current}/{total} — {title}"
    else:
        header_text = f"📋 {title}"
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header_text},
    })

    # Fields section
    fields = []
    for key, value in data.items():
        if key in _SKIP_FIELDS or not value:
            continue
        label = FIELD_LABELS.get(key, key.replace("_", " ").title())
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{value}"})

    # Handle bulk hardware entries
    if "entries" in data and data["entries"]:
        for i, entry in enumerate(data["entries"], 1):
            parts = [f"{entry.get('device_type', '?')} x{entry.get('qty', '?')}"]
            if entry.get("hw_version"):
                parts.append(f"HW:{entry['hw_version']}")
            if entry.get("fw_version"):
                parts.append(f"FW:{entry['fw_version']}")
            if entry.get("notes"):
                parts.append(f"({entry['notes']})")
            fields.append({"type": "mrkdwn", "text": f"*Item {i}:*\n{' '.join(parts)}"})

    # Slack limits 10 fields per section — split if needed
    for i in range(0, len(fields), 10):
        blocks.append({"type": "section", "fields": fields[i : i + 10]})

    # Divider
    blocks.append({"type": "divider"})

    # Confirm / Cancel buttons
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Onayla"},
                "style": "primary",
                "action_id": "confirm_action",
                "value": "confirm",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ İptal"},
                "style": "danger",
                "action_id": "cancel_action",
                "value": "cancel",
            },
        ],
    })

    return blocks


def format_query_response(query_type: str, data: dict[str, Any]) -> list[dict]:
    """Format a read-only query response."""
    blocks: list[dict] = []

    if query_type == "site_summary":
        site_id = data.get("site_id", "?")
        customer = data.get("customer", "?")
        status = data.get("status", "?")
        open_issues = data.get("open_issues", 0)
        total_devices = data.get("total_devices", 0)
        last_visit = data.get("last_visit", "—")

        blocks.append({
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 {site_id} — {customer}"},
        })
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                {"type": "mrkdwn", "text": f"*Open Issues:*\n{open_issues}"},
                {"type": "mrkdwn", "text": f"*Total Devices:*\n{total_devices}"},
                {"type": "mrkdwn", "text": f"*Last Visit:*\n{last_visit}"},
            ],
        })
    else:
        # Generic key-value display
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Query Result ({query_type}):*"},
        })
        fields = []
        for key, value in data.items():
            label = FIELD_LABELS.get(key, key.replace("_", " ").title())
            fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{value}"})
        if fields:
            blocks.append({"type": "section", "fields": fields[:10]})

    return blocks


def format_error_message(error_type: str, **kwargs: Any) -> list[dict]:
    """Format an error message."""
    blocks: list[dict] = []

    if error_type == "unknown_site":
        site_name = kwargs.get("site_name", "?")
        available = kwargs.get("available_sites", [])
        sites_text = ", ".join(f"`{s}`" for s in available)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ *\"{site_name}\"* adında bir saha bulunamadı.\n"
                    f"Mevcut sahalar: {sites_text}"
                ),
            },
        })
    elif error_type == "unknown_responsible":
        name = kwargs.get("name", "?")
        team = kwargs.get("team", [])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *\"{name}\"* tanımlı değil. Ekip: {', '.join(team)}.",
            },
        })
    elif error_type == "future_date":
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚠️ Gelecek tarihli kayıt oluşturulamaz.",
            },
        })
    else:
        message = kwargs.get("message", "Bir hata oluştu.")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"⚠️ {message}"},
        })

    return blocks


def format_help_text() -> list[dict]:
    """Format the Turkish help guide as Slack Block Kit blocks."""
    blocks: list[dict] = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "🤖 Mustafa — Kullanım Kılavuzu"},
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "Merhaba! Ben Mustafa, ERG Controls operasyon asistanınızım. "
                "Benimle Türkçe veya İngilizce konuşabilirsiniz."
            ),
        },
    })

    blocks.append({"type": "divider"})

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*🔹 Nasıl Kullanılır?*\n"
                "• Kanalda: `@mustafa` yazıp mesajınızı gönderin\n"
                "• DM'den: Direkt mesaj atabilirsiniz"
            ),
        },
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*🔹 Neler Yapabilirim?*\n\n"
                "📋 *Yeni Kurulum Kaydet*\n"
                "`@mustafa yeni müşteri: [isim], [şehir], [tesis türü], [tarih]`\n\n"
                "📞 *Destek Kaydı Oluştur*\n"
                "`@mustafa bugün ASM'ye gittim, 2 tag değiştirdim T12 T18, üretim hatası`\n\n"
                "🔄 *Destek Kaydı Güncelle*\n"
                "`@mustafa ASM'deki açık ticket'ı kapat, sorun çözüldü`\n\n"
                "🔧 *Donanım Güncelle*\n"
                "`@mustafa ASM'ye 5 tag daha ekledik`\n\n"
                "⚙️ *Ayar Güncelle*\n"
                "`@mustafa ASM yıkama süresi 30 saniye olarak güncellendi`\n\n"
                "📦 *Stok Güncelle*\n"
                "`@mustafa stoka 10 yeni tag ekle, İstanbul ofis`\n\n"
                "🔍 *Bilgi Sorgula*\n"
                "`@mustafa ASM'nin durumu ne?`\n"
                "`@mustafa tüm sahalarda açık ticket var mı?`\n"
                "`@mustafa stokta kaç tag var?`\n\n"
                "📊 *Veri Kalitesi*\n"
                "`@mustafa eksik bilgiler var mı?`\n"
                "`@mustafa hangi veriler eski?`\n"
                "`@mustafa ASM'nin eksik bilgileri ne?`"
            ),
        },
    })

    blocks.append({"type": "divider"})

    # Field requirements section — dynamically built from FIELD_REQUIREMENTS
    from app.field_config.field_requirements import FIELD_REQUIREMENTS
    from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

    _help_ops = [
        ("📞 Destek Kaydı", "support_log"),
        ("📋 Yeni Saha", "sites"),
        ("🔧 Donanım", "hardware_inventory"),
        ("⚙️ Kurulum Ayarları", "implementation_details"),
        ("📦 Stok", "stock"),
    ]

    req_lines = ["*🔹 Her İşlem İçin Gerekli Bilgiler*\n"]
    for label, tab in _help_ops:
        req = FIELD_REQUIREMENTS.get(tab, {})
        must_fields = req.get("must", [])
        friendly = [FRIENDLY_FIELD_MAP.get(f, f) for f in must_fields if f != "site_id"]
        if friendly:
            field_str = ", ".join(friendly)
            req_lines.append(f"*{label}:* {field_str}")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(req_lines),
        },
    })

    blocks.append({"type": "divider"})

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*⚠️ Önemli Notlar*\n"
                "• Her yazma işlemi onay gerektirir — yanlışlıkla veri değişmez\n"
                "• Sheet salt okunurdur, değişiklikler sadece benim üzerimden yapılır\n"
                "• Eksik bilgi varsa size sorarım, tek mesajda her şeyi yazmanız gerekmez\n"
                "• Gelecek tarihli destek kaydı oluşturulamaz"
            ),
        },
    })

    from app.config import get_google_sheet_url
    sheet_url = get_google_sheet_url()
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"📎 *Google Sheet:* <{sheet_url}|Tablo Linki>",
        },
    })

    return blocks


def format_feedback_buttons(context: str = "write") -> list[dict]:
    """Format a follow-up message with 👍/👎 buttons.

    context: "write" for after writes, "query" for after query responses.
    """
    question = "Faydalı oldu mu?" if context == "query" else "Doğru kaydedildi mi?"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": question,
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👍 Evet"},
                    "action_id": "feedback_positive",
                    "value": "positive",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👎 Hayır"},
                    "action_id": "feedback_negative",
                    "value": "negative",
                },
            ],
        },
    ]


def format_data_quality_response(
    check_type: str, issues: list[dict[str, str]], site_id: str | None = None,
) -> list[dict]:
    """Format data quality check results as Slack Block Kit blocks."""
    blocks: list[dict] = []

    if check_type == "missing_data":
        scope = f"`{site_id}`" if site_id else "Tüm sahalar"
        title = f"📊 Eksik Veri Raporu — {scope}"
    else:
        scope = f"`{site_id}`" if site_id else "Tüm sahalar"
        title = f"📊 Eski Veri Raporu — {scope}"

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": title},
    })

    if not issues:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ Sorun bulunamadı."},
        })
        return blocks

    # Group issues by site_id
    by_site: dict[str, list[dict[str, str]]] = {}
    for issue in issues:
        sid = issue.get("site_id", "?")
        by_site.setdefault(sid, []).append(issue)

    for sid, site_issues in by_site.items():
        lines = [f"*`{sid}`* ({len(site_issues)} sorun):"]
        for iss in site_issues:
            tab = iss.get("tab", "")
            detail = iss.get("detail", "")
            severity = iss.get("severity", "")
            if severity == "must":
                prefix = "🔴"
            elif severity == "important":
                prefix = "🟡"
            else:
                prefix = "•"
            lines.append(f"  {prefix} _{tab}:_ {detail}")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Toplam: {len(issues)} sorun bulundu."}],
    })

    return blocks


def format_chain_input_prompt(
    step: int,
    total: int,
    operation: str,
    facility_type: str | None = None,
) -> list[dict]:
    """Format a prompt for an empty chain step, asking user for data or to skip.

    Includes must/important field hints from FIELD_REQUIREMENTS.
    """
    from app.utils.missing_fields import _OP_TO_TAB
    from app.field_config.field_descriptions import get_field_description
    from app.field_config.field_options import get_dropdown_options
    from app.field_config.field_requirements import FIELD_REQUIREMENTS
    from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

    label = CHAIN_LABELS.get(operation, operation).capitalize()

    # Build field hints from FIELD_REQUIREMENTS
    tab = _OP_TO_TAB.get(operation)
    field_lines: list[str] = []
    if tab and tab in FIELD_REQUIREMENTS:
        req = FIELD_REQUIREMENTS[tab]

        must_fields = [f for f in req.get("must", []) if f != "site_id"]
        # Add facility-type must fields
        if facility_type:
            facility_must = req.get("must_when_facility_type", {})
            if facility_type in facility_must:
                must_fields.extend(facility_must[facility_type])

        important_fields = list(req.get("important", []))
        # HW conditional important fields (simplified — show them)
        for field_key in req.get("important_conditional", {}):
            if field_key not in important_fields:
                important_fields.append(field_key)

        if must_fields:
            field_lines.append("Kaydı oluşturabilmem için şu bilgiler gerekli:")
            for f in must_fields:
                question = FRIENDLY_FIELD_MAP.get(f, f)
                desc = get_field_description(f, operation)
                if desc:
                    line = f"  • {question} — {desc}"
                else:
                    line = f"  • {question}"
                opts = get_dropdown_options(f)
                if opts:
                    line += f" Seçenekler: {', '.join(opts)}"
                field_lines.append(line)

        if important_fields:
            field_lines.append("Kaydı zenginleştirmek için şunlar da faydalı olur:")
            for f in important_fields:
                question = FRIENDLY_FIELD_MAP.get(f, f)
                desc = get_field_description(f, operation)
                if desc:
                    line = f"  • {question} — {desc}"
                else:
                    line = f"  • {question}"
                opts = get_dropdown_options(f)
                if opts:
                    line += f" Seçenekler: {', '.join(opts)}"
                field_lines.append(line)

    field_text = "\n".join(field_lines)
    body = f"📝 *Adım {step}/{total} — {label}*"
    if field_text:
        body += f"\n{field_text}"
    body += "\nBu thread'e yazın veya ⏭️ ile atlayın."

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": body,
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "⏭️ Atla"},
                    "action_id": "cancel_action",
                    "value": "cancel",
                },
            ],
        },
    ]


def build_chain_roadmap(chain_steps: list[str]) -> str:
    """Build a roadmap message for a chained create_site wizard."""
    _EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    lines = ["Müşteri kaydı oluşturuyorum. Sırayla:"]
    for i, op in enumerate(chain_steps):
        emoji = _EMOJIS[i] if i < len(_EMOJIS) else f"{i + 1}."
        label = CHAIN_LABELS.get(op, op).capitalize()
        lines.append(f"{emoji} {label}")
    lines.append("Her adımda onaylayabilir veya atlayabilirsiniz.")
    return "\n".join(lines)


def build_chain_final_summary(
    site_id: str, chain_steps: list[str], completed_ops: set[str], skipped_ops: set[str],
) -> str:
    """Build the final one-line summary for a completed chain."""
    parts = []
    for op in chain_steps:
        label = CHAIN_LABELS.get(op, op)
        if op in completed_ops:
            parts.append(f"{label} ✅")
        elif op in skipped_ops:
            parts.append(f"{label} ⏭️")
        else:
            parts.append(f"{label} ❌")
    prefix = f"`{site_id}` tamamlandı" if site_id else "Tamamlandı"
    return f"{prefix}: {', '.join(parts)}"
