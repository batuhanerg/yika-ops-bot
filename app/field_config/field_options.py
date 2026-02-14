"""Valid dropdown options for Implementation Details fields.

Used for validation and display in missing-field prompts.
Keys use sheet column header names (matching Claude's output).
"""

from __future__ import annotations

from thefuzz import fuzz

IMPLEMENTATION_DROPDOWNS: dict[str, list[str]] = {
    "Internet Provider": ["ERG Controls", "Müşteri"],
    "Hand hygiene type": [
        "Tek adımlı (sadece sabun)",
        "İki adımlı (sabun ve dezenfektan)",
    ],
    "Tag buzzer/vibration": ["Açık", "Kapalı"],
}

# snake_case → column header for dropdown lookup
_SNAKE_TO_COLUMN: dict[str, str] = {
    "internet_provider": "Internet Provider",
    "hand_hygiene_type": "Hand hygiene type",
    "tag_buzzer_vibration": "Tag buzzer/vibration",
}

_FUZZY_THRESHOLD = 70


def get_dropdown_options(field: str) -> list[str] | None:
    """Get dropdown options for a field (snake_case or column header key).

    Returns None if the field is not a dropdown.
    """
    if field in IMPLEMENTATION_DROPDOWNS:
        return IMPLEMENTATION_DROPDOWNS[field]
    col = _SNAKE_TO_COLUMN.get(field)
    if col:
        return IMPLEMENTATION_DROPDOWNS.get(col)
    return None


def validate_impl_dropdown(field: str, value: str) -> str | None:
    """Validate a value against dropdown options for a field.

    Returns:
        - The matched option string (exact or fuzzy) if valid
        - The original value if the field is not a dropdown
        - None if the field is a dropdown but no match found
    """
    options = get_dropdown_options(field)
    if options is None:
        return value  # Not a dropdown field — pass through

    # Exact match
    for opt in options:
        if value == opt:
            return opt

    # Case-insensitive exact match
    value_lower = value.lower()
    for opt in options:
        if value_lower == opt.lower():
            return opt

    # Fuzzy match (partial_ratio handles short inputs like "iki adımlı")
    best_score = 0
    best_match = None
    for opt in options:
        score = fuzz.partial_ratio(value_lower, opt.lower())
        if score > best_score:
            best_score = score
            best_match = opt

    if best_score >= _FUZZY_THRESHOLD and best_match:
        return best_match

    return None
