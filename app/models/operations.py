"""Pydantic models for all operation types."""

from __future__ import annotations

from pydantic import BaseModel


# --- Enums as literal lists (used by validators) ---

SUPPORT_TYPES = ("Visit", "Remote", "Call")
SUPPORT_STATUSES = ("Open", "Resolved", "Follow-up (ERG)", "Follow-up (Customer)", "Scheduled")
ROOT_CAUSES = (
    "HW Fault (Production)",
    "HW Fault (Customer)",
    "FW Bug",
    "Dashboard Bug",
    "Feature Request",
    "Configuration",
    "User Error",
    "Pending",
    "Other",
)
FACILITY_TYPES = ("Food", "Healthcare")
DEVICE_TYPES = (
    "Tag",
    "Anchor",
    "Gateway",
    "Charging Dock",
    "Power Bank",
    "Power Adapter",
    "USB Cable",
    "Other",
)
CONTRACT_STATUSES = ("Active", "Pending", "Expired", "Pilot")
STOCK_LOCATIONS = ("Istanbul Office", "Adana Storage", "Other")
STOCK_CONDITIONS = ("New", "Refurbished", "Faulty", "Reserved")

TEAM_MEMBERS = ("Batu", "Mehmet", "Gökhan", "Koray")

# --- Dropdown registry (field_name → allowed values) ---

DROPDOWN_FIELDS: dict[str, tuple[str, ...]] = {
    "support_type": SUPPORT_TYPES,
    "support_status": SUPPORT_STATUSES,
    "root_cause": ROOT_CAUSES,
    "facility_type": FACILITY_TYPES,
    "device_type": DEVICE_TYPES,
    "contract_status": CONTRACT_STATUSES,
    "stock_location": STOCK_LOCATIONS,
    "stock_condition": STOCK_CONDITIONS,
}

# --- Required fields per operation ---

REQUIRED_FIELDS: dict[str, list[str]] = {
    "log_support": [
        "site_id",
        "received_date",
        "type",
        "status",
        "issue_summary",
        "technician",
    ],
    "create_site": [
        "customer",
        "city",
        "country",
        "facility_type",
        "go_live_date",
        "contract_status",
    ],
    "update_hardware": [
        "site_id",
    ],
    "update_stock": [
        "location",
        "device_type",
        "qty",
        "condition",
    ],
    "update_site": [
        "site_id",
    ],
    "update_implementation": [
        "site_id",
    ],
    "update_support": [
        "site_id",
    ],
    "query": [
        "query_type",
    ],
}

# Conditional required fields based on status
CONDITIONAL_REQUIRED: dict[str, dict[str, list[str]]] = {
    "log_support": {
        "Resolved": ["resolved_date", "resolution", "root_cause"],
        "Follow-up (ERG)": ["root_cause"],
        "Follow-up (Customer)": ["root_cause"],
        "Scheduled": ["root_cause"],
    },
}


class ParseResult(BaseModel):
    """Result of parsing a user message via Claude."""

    operation: str
    data: dict
    missing_fields: list[str] = []
    error: str | None = None
    warnings: list[str] | None = None
    language: str = "tr"
    extra_operations: list[dict] | None = None
