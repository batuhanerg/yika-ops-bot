"""Format missing fields messages with friendly Turkish questions.

Classifies fields as must (blockers) or important (suggestions)
using FIELD_REQUIREMENTS, then formats them with natural language.
"""

from __future__ import annotations

from app.field_config.field_requirements import FIELD_REQUIREMENTS
from app.field_config.friendly_fields import FRIENDLY_FIELD_MAP

# Map operation → tab key in FIELD_REQUIREMENTS
_OP_TO_TAB = {
    "log_support": "support_log",
    "create_site": "sites",
    "update_hardware": "hardware_inventory",
    "update_implementation": "implementation_details",
    "update_stock": "stock",
    "update_site": "sites",
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
                lines.append(f"  • {question}")

        if important_fields:
            lines.append("Kaydı zenginleştirmek için şunlar da faydalı olur:")
            for f in important_fields:
                question = FRIENDLY_FIELD_MAP.get(f, f)
                lines.append(f"  • {question}")
    else:
        if must_fields:
            field_names = ", ".join(f"`{f}`" for f in must_fields)
            lines.append(f"Required information: {field_names}")
        if important_fields:
            field_names = ", ".join(f"`{f}`" for f in important_fields)
            lines.append(f"Optional but helpful: {field_names}")

    has_blockers = len(must_fields) > 0
    return "\n".join(lines), has_blockers
