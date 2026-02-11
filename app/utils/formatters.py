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
    "technician": "Technician",
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
}

OPERATION_TITLES: dict[str, str] = {
    "log_support": "Destek Kaydı / Support Log",
    "create_site": "Yeni Site / New Site",
    "update_support": "Destek Güncelleme / Support Update",
    "update_site": "Site Güncelleme / Site Update",
    "update_hardware": "Donanım Güncelleme / Hardware Update",
    "update_implementation": "Ayar Güncelleme / Implementation Update",
    "update_stock": "Stok Güncelleme / Stock Update",
}

CHAIN_LABELS: dict[str, str] = {
    "create_site": "site",
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
            label = key.replace("_", " ").title()
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
                    f"⚠️ *\"{site_name}\"* isimde bir site bulamadım.\n"
                    f"Mevcut siteler: {sites_text}"
                ),
            },
        })
    elif error_type == "unknown_technician":
        name = kwargs.get("name", "?")
        team = kwargs.get("team", [])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ Teknisyen *\"{name}\"* tanımlı değil. Ekip: {', '.join(team)}.",
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
                "`@mustafa tüm sitelerde açık ticket var mı?`\n"
                "`@mustafa stokta kaç tag var?`"
            ),
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

    return blocks


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
