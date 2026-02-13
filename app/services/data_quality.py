"""Data quality checks: missing fields and stale records.

Uses FIELD_REQUIREMENTS for structured validation with severity levels
and context-aware skipping (e.g., Awaiting Installation sites).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.field_config.field_requirements import CONTEXT_RULES, FIELD_REQUIREMENTS

# Map from snake_case field keys to sheet column names for Sites tab
_SITES_FIELD_TO_COLUMN = {
    "customer": "Customer", "city": "City", "country": "Country",
    "facility_type": "Facility Type", "contract_status": "Contract Status",
    "supervisor_1": "Supervisor 1", "phone_1": "Phone 1",
    "go_live_date": "Go-live Date", "address": "Address",
    "dashboard_link": "Dashboard Link", "whatsapp_group": "Whatsapp Group",
    "email_1": "Email 1", "supervisor_2": "Supervisor 2",
    "phone_2": "Phone 2", "email_2": "Email 2", "notes": "Notes",
}

_HW_FIELD_TO_COLUMN = {
    "hw_version": "HW Version", "fw_version": "FW Version",
}

_IMPL_FIELD_TO_COLUMN = {
    "internet_provider": "Internet Provider", "ssid": "SSID",
    "password": "Password", "gateway_placement": "Gateway placement",
    "charging_dock_placement": "Charging dock placement",
    "dispenser_anchor_placement": "Dispenser anchor placement",
    "handwash_time": "Handwash time", "tag_buzzer_vibration": "Tag buzzer/vibration",
    "entry_time": "Entry time", "dispenser_anchor_power_type": "Dispenser anchor power type",
    "clean_hygiene_time": "Clean hygiene time", "hp_alert_time": "HP alert time",
    "hand_hygiene_time": "Hand hygiene time",
    "hand_hygiene_interval": "Hand hygiene interval (dashboard)",
    "hand_hygiene_type": "Hand hygiene type",
    "tag_clean_to_red_timeout": "Tag clean-to-red timeout",
    "other_details": "Other details",
}

_SUPPORT_FIELD_TO_COLUMN = {
    "root_cause": "Root Cause", "resolution": "Resolution",
    "resolved_date": "Resolved Date", "devices_affected": "Devices Affected",
}

_STOCK_FIELD_TO_COLUMN = {
    "location": "Location", "device_type": "Device Type",
    "hw_version": "HW Version", "fw_version": "FW Version",
    "qty": "Qty", "condition": "Condition",
    "reserved_for": "Reserved For", "notes": "Notes",
    "last_verified": "Last Verified",
}


def _get_skipped_tabs(contract_status: str) -> set[str]:
    """Return tab names to skip based on contract status."""
    if contract_status == "Awaiting Installation":
        return set(CONTEXT_RULES["awaiting_installation"]["skip_tabs"])
    return set()


def find_missing_data(
    sites: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    support: list[dict[str, Any]],
    site_id: str | None = None,
    implementation: list[dict[str, Any]] | None = None,
    stock: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Scan across tabs for empty or incomplete fields.

    Returns a list of issue dicts: {site_id, tab, field, detail, severity}.
    severity is "must" or "important".
    """
    issues: list[dict[str, str]] = []

    # Filter by site if specified
    filtered_sites = [s for s in sites if s["Site ID"] == site_id] if site_id else sites
    filtered_hw = [h for h in hardware if h["Site ID"] == site_id] if site_id else hardware
    filtered_support = [s for s in support if s["Site ID"] == site_id] if site_id else support

    # Build per-site skip lists based on contract status
    site_skip_tabs: dict[str, set[str]] = {}
    for site in filtered_sites:
        sid = site["Site ID"]
        status = site.get("Contract Status", "")
        site_skip_tabs[sid] = _get_skipped_tabs(status)

    # --- Sites tab ---
    sites_req = FIELD_REQUIREMENTS["sites"]
    for site in filtered_sites:
        sid = site["Site ID"]
        # Check must fields
        for field_key in sites_req["must"]:
            col = _SITES_FIELD_TO_COLUMN.get(field_key, field_key)
            if not site.get(col):
                issues.append({
                    "site_id": sid, "tab": "Sites", "field": col,
                    "detail": f"{col} boş", "severity": "must",
                })
        # Check important fields
        for field_key in sites_req.get("important", []):
            col = _SITES_FIELD_TO_COLUMN.get(field_key, field_key)
            if not site.get(col):
                issues.append({
                    "site_id": sid, "tab": "Sites", "field": col,
                    "detail": f"{col} boş", "severity": "important",
                })

    # --- Hardware Inventory tab ---
    hw_req = FIELD_REQUIREMENTS["hardware_inventory"]
    for hw in filtered_hw:
        sid = hw["Site ID"]
        if "hardware_inventory" in site_skip_tabs.get(sid, set()):
            continue
        device = hw.get("Device Type", "?")
        # Check conditional important fields (hw_version, fw_version)
        for field_key, rule in hw_req.get("important_conditional", {}).items():
            col = _HW_FIELD_TO_COLUMN.get(field_key, field_key)
            if not hw.get(col):
                # Check if this device type is excluded
                if isinstance(rule, dict) and "except_device_types" in rule:
                    if device in rule["except_device_types"]:
                        continue
                issues.append({
                    "site_id": sid, "tab": "Hardware Inventory", "field": col,
                    "detail": f"{device}: {col} boş", "severity": "important",
                })

    # --- Support Log tab ---
    sup_req = FIELD_REQUIREMENTS["support_log"]
    for entry in filtered_support:
        sid = entry["Site ID"]
        if "support_log" in site_skip_tabs.get(sid, set()):
            continue
        ticket = entry.get("Ticket ID", "?")
        status = entry.get("Status", "")
        # Check conditional important fields
        for field_key, rule in sup_req.get("important_conditional", {}).items():
            col = _SUPPORT_FIELD_TO_COLUMN.get(field_key, field_key)
            value = entry.get(col, "")
            if isinstance(rule, dict):
                if "required_when_status_not" in rule:
                    # Only flag when status is NOT in the list
                    if status in rule["required_when_status_not"]:
                        continue
                    if not value or value == "Pending":
                        detail = f"{ticket}: Root Cause hâlâ Pending" if value == "Pending" else f"{ticket}: {col} boş"
                        issues.append({
                            "site_id": sid, "tab": "Support Log", "field": col,
                            "detail": detail, "severity": "must",
                        })
                elif "required_when_status" in rule:
                    if status not in rule["required_when_status"]:
                        continue
                    if not value:
                        issues.append({
                            "site_id": sid, "tab": "Support Log", "field": col,
                            "detail": f"{ticket}: {status} ama {col} boş",
                            "severity": "must",
                        })
            elif rule == "always_important":
                if not value:
                    issues.append({
                        "site_id": sid, "tab": "Support Log", "field": col,
                        "detail": f"{ticket}: {col} boş", "severity": "important",
                    })

    # --- Implementation Details tab ---
    impl_req = FIELD_REQUIREMENTS["implementation_details"]
    if implementation is not None:
        # Build facility_type lookup from sites
        site_facility: dict[str, str] = {}
        for site in sites:
            site_facility[site["Site ID"]] = site.get("Facility Type", "")

        filtered_impl = (
            [i for i in implementation if i.get("Site ID") == site_id]
            if site_id else implementation
        )
        for impl in filtered_impl:
            sid = impl.get("Site ID", "?")
            if "implementation_details" in site_skip_tabs.get(sid, set()):
                continue
            ftype = site_facility.get(sid, "")
            # Check must fields
            for field_key in impl_req["must"]:
                col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
                if not impl.get(col):
                    issues.append({
                        "site_id": sid, "tab": "Implementation Details",
                        "field": col, "detail": f"{col} boş", "severity": "must",
                    })
            # Check important fields
            for field_key in impl_req.get("important", []):
                col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
                if not impl.get(col):
                    issues.append({
                        "site_id": sid, "tab": "Implementation Details",
                        "field": col, "detail": f"{col} boş", "severity": "important",
                    })
            # Check must_when_facility_type
            facility_must = impl_req.get("must_when_facility_type", {})
            if ftype and ftype in facility_must:
                for field_key in facility_must[ftype]:
                    col = _IMPL_FIELD_TO_COLUMN.get(field_key, field_key)
                    if not impl.get(col):
                        issues.append({
                            "site_id": sid, "tab": "Implementation Details",
                            "field": col, "detail": f"{col} boş", "severity": "must",
                        })

    # --- Cross-tab checks: sites with no hardware records ---
    hw_sites = {h["Site ID"] for h in hardware}
    for site in filtered_sites:
        sid = site["Site ID"]
        if "hardware_inventory" in site_skip_tabs.get(sid, set()):
            continue
        if sid not in hw_sites:
            issues.append({
                "site_id": sid, "tab": "Hardware Inventory", "field": "—",
                "detail": "Donanım kaydı yok", "severity": "important",
            })

    # --- Cross-tab checks: sites with no implementation records ---
    if implementation is not None:
        impl_sites = {i.get("Site ID") for i in implementation if i.get("Site ID")}
        for site in filtered_sites:
            sid = site["Site ID"]
            if "implementation_details" in site_skip_tabs.get(sid, set()):
                continue
            if sid not in impl_sites:
                issues.append({
                    "site_id": sid, "tab": "Implementation Details", "field": "—",
                    "detail": "Kurulum detayı yok", "severity": "important",
                })

    # --- Stock tab ---
    stock_req = FIELD_REQUIREMENTS["stock"]
    if stock is not None:
        for item in stock:
            loc = item.get("Location", "?")
            device = item.get("Device Type", "?")
            label = f"{loc}/{device}"
            # Check must fields
            for field_key in stock_req["must"]:
                col = _STOCK_FIELD_TO_COLUMN.get(field_key, field_key)
                if not item.get(col):
                    issues.append({
                        "site_id": label, "tab": "Stock", "field": col,
                        "detail": f"{col} boş", "severity": "must",
                    })
            # Check important fields
            for field_key in stock_req.get("important", []):
                col = _STOCK_FIELD_TO_COLUMN.get(field_key, field_key)
                if not item.get(col):
                    issues.append({
                        "site_id": label, "tab": "Stock", "field": col,
                        "detail": f"{col} boş", "severity": "important",
                    })

    # --- Open ticket aging (>3 days, status ≠ Resolved) ---
    for entry in filtered_support:
        sid = entry["Site ID"]
        if "support_log" in site_skip_tabs.get(sid, set()):
            continue
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
                ticket = entry.get("Ticket ID", "?")
                issues.append({
                    "site_id": sid, "tab": "Support Log", "field": "Aging",
                    "detail": f"{ticket}: {days_open} gündür açık (status: {status})",
                    "severity": "important",
                })
        except ValueError:
            pass

    return issues


def find_stale_data(
    hardware: list[dict[str, Any]],
    implementation: list[dict[str, Any]],
    site_id: str | None = None,
    threshold_days: int = 30,
    stock: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Find records where Last Verified is older than threshold or missing.

    Returns a list of issue dicts: {site_id, tab, detail}.
    """
    issues: list[dict[str, str]] = []
    cutoff = date.today() - timedelta(days=threshold_days)

    filtered_hw = [h for h in hardware if h["Site ID"] == site_id] if site_id else hardware
    filtered_impl = [i for i in implementation if i.get("Site ID") == site_id] if site_id else implementation

    for hw in filtered_hw:
        sid = hw["Site ID"]
        device = hw.get("Device Type", "?")
        last_verified = hw.get("Last Verified", "")
        if not last_verified:
            issues.append({
                "site_id": sid, "tab": "Hardware Inventory",
                "detail": f"{device}: Last Verified yok",
            })
        else:
            try:
                lv_date = date.fromisoformat(last_verified)
                if lv_date < cutoff:
                    days_old = (date.today() - lv_date).days
                    issues.append({
                        "site_id": sid, "tab": "Hardware Inventory",
                        "detail": f"{device}: {days_old} gün önce doğrulanmış ({last_verified})",
                    })
            except ValueError:
                issues.append({
                    "site_id": sid, "tab": "Hardware Inventory",
                    "detail": f"{device}: Last Verified geçersiz format ({last_verified})",
                })

    for impl in filtered_impl:
        sid = impl.get("Site ID", "?")
        last_verified = impl.get("Last Verified", "")
        if not last_verified:
            issues.append({
                "site_id": sid, "tab": "Implementation Details",
                "detail": "Last Verified yok",
            })
        else:
            try:
                lv_date = date.fromisoformat(last_verified)
                if lv_date < cutoff:
                    days_old = (date.today() - lv_date).days
                    issues.append({
                        "site_id": sid, "tab": "Implementation Details",
                        "detail": f"{days_old} gün önce doğrulanmış ({last_verified})",
                    })
            except ValueError:
                issues.append({
                    "site_id": sid, "tab": "Implementation Details",
                    "detail": f"Last Verified geçersiz format ({last_verified})",
                })

    # --- Stock ---
    if stock is not None:
        for item in stock:
            loc = item.get("Location", "?")
            device = item.get("Device Type", "?")
            label = f"{loc}/{device}"
            last_verified = item.get("Last Verified", "")
            if not last_verified:
                issues.append({
                    "site_id": label, "tab": "Stock",
                    "detail": f"{device}: Last Verified yok",
                })
            else:
                try:
                    lv_date = date.fromisoformat(last_verified)
                    if lv_date < cutoff:
                        days_old = (date.today() - lv_date).days
                        issues.append({
                            "site_id": label, "tab": "Stock",
                            "detail": f"{device}: {days_old} gün önce doğrulanmış ({last_verified})",
                        })
                except ValueError:
                    issues.append({
                        "site_id": label, "tab": "Stock",
                        "detail": f"{device}: Last Verified geçersiz format ({last_verified})",
                    })

    return issues
