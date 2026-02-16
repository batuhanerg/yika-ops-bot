"""Format missing fields messages with friendly Turkish questions.

Classifies fields as must (blockers) or important (suggestions)
using FIELD_REQUIREMENTS, then formats them with natural language.

Also provides enforce_must_fields() for code-level must-field validation
independent of what Claude reports in missing_fields.
"""

from __future__ import annotations

from app.field_config.field_descriptions import get_field_description
from app.field_config.field_options import get_dropdown_options
from app.field_config.field_requirements import FIELD_REQUIREMENTS
from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

# snake_case → sheet column header for implementation fields.
# Claude returns column header keys per system_prompt.md instruction.
_IMPL_FIELD_TO_COLUMN: dict[str, str] = {
    "internet_provider": "Internet Provider",
    "ssid": "SSID",
    "password": "Password",
    "gateway_placement": "Gateway placement",
    "charging_dock_placement": "Charging dock placement",
    "dispenser_anchor_placement": "Dispenser anchor placement",
    "handwash_time": "Handwash time",
    "tag_buzzer_vibration": "Tag buzzer/vibration",
    "entry_time": "Entry time",
    "dispenser_anchor_power_type": "Dispenser anchor power type",
    "clean_hygiene_time": "Clean hygiene time",
    "hp_alert_time": "HP alert time",
    "hand_hygiene_time": "Hand hygiene time",
    "hand_hygiene_interval": "Hand hygiene interval (dashboard)",
    "hand_hygiene_type": "Hand hygiene type",
    "tag_clean_to_red_timeout": "Tag clean-to-red timeout",
    "other_details": "Other details",
}

# Map operation → tab key in FIELD_REQUIREMENTS
_OP_TO_TAB = {
    "log_support": "support_log",
    "create_site": "sites",
    "update_hardware": "hardware_inventory",
    "update_implementation": "implementation_details",
    "update_stock": "stock",
    # update_site intentionally NOT mapped — only site_id is required,
    # not the full create_site must fields (customer, city, country, etc.)
    "update_support": "support_log",
}


def _classify_field(
    field: str,
    operation: str,
    facility_type: str | None = None,
) -> str:
    """Classify a field as 'must' or 'important' for a given operation."""
    tab = _OP_TO_TAB.get(operation)
    if not tab or tab not in FIELD_REQUIREMENTS:
        return "must"  # Default to must if unknown

    req = FIELD_REQUIREMENTS[tab]
    if field in req.get("must", []):
        return "must"
    if field in req.get("important", []):
        return "important"
    if field in req.get("important_conditional", {}):
        return "important"

    # Check must_when_facility_type
    facility_must = req.get("must_when_facility_type", {})
    if facility_must:
        if facility_type and facility_type in facility_must:
            if field in facility_must[facility_type]:
                return "must"
        # Field belongs to a facility-type list but we don't know the type
        # or it's for a different facility — treat as important
        for fields_list in facility_must.values():
            if field in fields_list:
                return "important"

    return "must"  # If it's in missing_fields but not in any category, treat as must


def format_missing_fields_message(
    missing_fields: list[str],
    operation: str,
    language: str = "tr",
    facility_type: str | None = None,
) -> tuple[str, bool]:
    """Format a friendly message for missing fields.

    Returns (message_text, has_blockers).
    has_blockers is True if any must fields are missing.
    """
    must_fields: list[str] = []
    important_fields: list[str] = []

    for field in missing_fields:
        severity = _classify_field(field, operation, facility_type=facility_type)
        if severity == "must":
            must_fields.append(field)
        else:
            important_fields.append(field)

    lines: list[str] = []

    if language == "tr":
        if must_fields:
            lines.append("Kaydı oluşturabilmem için şu bilgiler gerekli:")
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
                lines.append(line)

        if important_fields:
            lines.append("Kaydı zenginleştirmek için şunlar da faydalı olur:")
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
                lines.append(line)
    else:
        if must_fields:
            field_names = ", ".join(f"`{f}`" for f in must_fields)
            lines.append(f"Required information: {field_names}")
        if important_fields:
            field_names = ", ".join(f"`{f}`" for f in important_fields)
            lines.append(f"Optional but helpful: {field_names}")

    has_blockers = len(must_fields) > 0
    return "\n".join(lines), has_blockers


def _data_has_field(data: dict, field: str, operation: str) -> bool:
    """Check if data contains a field, considering column header aliases.

    For update_implementation, Claude returns sheet column header keys
    (e.g. "Internet Provider") while FIELD_REQUIREMENTS uses snake_case
    (e.g. "internet_provider"). Check both.
    """
    if data.get(field):
        return True
    if operation in ("update_implementation",):
        col = _IMPL_FIELD_TO_COLUMN.get(field)
        if col and data.get(col):
            return True
    return False


def enforce_must_fields(
    operation: str,
    data: dict,
    claude_missing: list[str],
    facility_type: str | None = None,
) -> list[str]:
    """Cross-reference extracted data against FIELD_REQUIREMENTS must fields.

    Returns a deduplicated list of all must fields that are missing,
    including those Claude reported and those it missed.
    """
    tab = _OP_TO_TAB.get(operation)
    if not tab or tab not in FIELD_REQUIREMENTS:
        return list(claude_missing)

    req = FIELD_REQUIREMENTS[tab]
    # Start from Claude's list but remove fields that are actually present in data
    missing: list[str] = [
        f for f in claude_missing if not _data_has_field(data, f, operation)
    ]

    # For bulk hardware, entries list satisfies device_type and qty
    entries = data.get("entries")
    entries_satisfy: set[str] = set()
    if operation == "update_hardware" and isinstance(entries, list) and entries:
        entries_satisfy = {"device_type", "qty"}
        missing = [f for f in missing if f not in entries_satisfy]

    # Check must fields
    for field in req.get("must", []):
        if field in entries_satisfy:
            continue
        if not _data_has_field(data, field, operation) and field not in missing:
            missing.append(field)

    # Check must_when_facility_type
    if facility_type:
        facility_must = req.get("must_when_facility_type", {})
        if facility_type in facility_must:
            for field in facility_must[facility_type]:
                if not _data_has_field(data, field, operation) and field not in missing:
                    missing.append(field)

    return missing
