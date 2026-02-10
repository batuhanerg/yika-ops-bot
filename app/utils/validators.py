"""Field validation for dates, enums, required fields, Site ID format."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel

from app.models.operations import (
    CONDITIONAL_REQUIRED,
    DROPDOWN_FIELDS,
    REQUIRED_FIELDS,
)

# Site ID pattern: 2-4 uppercase letters, dash, 2 uppercase letters, dash, 2 digits
SITE_ID_PATTERN = re.compile(r"^[A-Z]{2,4}-[A-Z]{2}-\d{2}$")


class ValidationResult(BaseModel):
    valid: bool = True
    warning: bool = False
    message: str = ""


def validate_site_id_format(site_id: str) -> bool:
    """Check if site_id matches XXX-CC-NN format."""
    if not site_id:
        return False
    return bool(SITE_ID_PATTERN.match(site_id))


def validate_date_not_future(d: date) -> ValidationResult:
    """Reject dates in the future."""
    if d > date.today():
        return ValidationResult(
            valid=False,
            message="Gelecek tarihli kayıt oluşturulamaz. / Future dates are not allowed.",
        )
    return ValidationResult(valid=True)


def validate_date_not_too_old(d: date) -> ValidationResult:
    """Warn if date is more than 90 days ago."""
    days_ago = (date.today() - d).days
    if days_ago > 90:
        return ValidationResult(
            valid=True,
            warning=True,
            message=f"Bu kayıt {days_ago} gün önceye ait (>90 gün). Emin misiniz?",
        )
    return ValidationResult(valid=True)


def validate_resolved_after_received(received: date, resolved: date) -> ValidationResult:
    """Resolved date must be >= received date."""
    if resolved < received:
        return ValidationResult(
            valid=False,
            message="Çözüm tarihi, alım tarihinden önce olamaz. / Resolved date cannot be before received date.",
        )
    return ValidationResult(valid=True)


def validate_required_fields(operation: str, data: dict[str, Any]) -> list[str]:
    """Return list of missing required fields for the given operation."""
    required = REQUIRED_FIELDS.get(operation, [])
    missing = [f for f in required if not data.get(f)]

    # Check conditional required fields
    conditionals = CONDITIONAL_REQUIRED.get(operation, {})
    for trigger_value, extra_fields in conditionals.items():
        # Check if any field has the trigger value
        if data.get("status") == trigger_value:
            for f in extra_fields:
                if not data.get(f) and f not in missing:
                    missing.append(f)

    return missing


def validate_dropdown_value(field_name: str, value: str) -> bool:
    """Check if value is a valid option for the given dropdown field."""
    allowed = DROPDOWN_FIELDS.get(field_name)
    if allowed is None:
        return False
    return value in allowed


def validate_positive_integer(value: Any) -> bool:
    """Check that value is a positive integer."""
    if value is None:
        return False
    if not isinstance(value, int):
        return False
    return value > 0
