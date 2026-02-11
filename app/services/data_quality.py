"""Data quality checks: missing fields and stale records."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# Fields to check on Sites tab
_SITE_IMPORTANT_FIELDS = ["Email 1", "Supervisor 2"]

# Fields to check on Hardware Inventory tab
_HARDWARE_IMPORTANT_FIELDS = ["FW Version"]


def find_missing_data(
    sites: list[dict[str, Any]],
    hardware: list[dict[str, Any]],
    support: list[dict[str, Any]],
    site_id: str | None = None,
) -> list[dict[str, str]]:
    """Scan across tabs for empty or incomplete fields.

    Returns a list of issue dicts: {site_id, tab, field, detail}.
    """
    issues: list[dict[str, str]] = []

    # Filter by site if specified
    filtered_sites = [s for s in sites if s["Site ID"] == site_id] if site_id else sites
    filtered_hw = [h for h in hardware if h["Site ID"] == site_id] if site_id else hardware
    filtered_support = [s for s in support if s["Site ID"] == site_id] if site_id else support

    # Sites tab
    for site in filtered_sites:
        sid = site["Site ID"]
        for field in _SITE_IMPORTANT_FIELDS:
            if not site.get(field):
                issues.append({
                    "site_id": sid,
                    "tab": "Sites",
                    "field": field,
                    "detail": f"{field} boş",
                })

    # Hardware Inventory tab
    for hw in filtered_hw:
        sid = hw["Site ID"]
        device = hw.get("Device Type", "?")
        for field in _HARDWARE_IMPORTANT_FIELDS:
            if not hw.get(field):
                issues.append({
                    "site_id": sid,
                    "tab": "Hardware Inventory",
                    "field": field,
                    "detail": f"{device}: {field} boş",
                })

    # Support Log tab
    for entry in filtered_support:
        sid = entry["Site ID"]
        ticket = entry.get("Ticket ID", "?")
        status = entry.get("Status", "")
        root_cause = entry.get("Root Cause", "")
        resolution = entry.get("Resolution", "")

        if root_cause == "Pending":
            issues.append({
                "site_id": sid,
                "tab": "Support Log",
                "field": "Root Cause",
                "detail": f"{ticket}: Root Cause hâlâ Pending",
            })

        if status == "Resolved" and not resolution:
            issues.append({
                "site_id": sid,
                "tab": "Support Log",
                "field": "Resolution",
                "detail": f"{ticket}: Resolved ama Resolution boş",
            })

    return issues


def find_stale_data(
    hardware: list[dict[str, Any]],
    implementation: list[dict[str, Any]],
    site_id: str | None = None,
    threshold_days: int = 30,
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
                "site_id": sid,
                "tab": "Hardware Inventory",
                "detail": f"{device}: Last Verified yok",
            })
        else:
            try:
                lv_date = date.fromisoformat(last_verified)
                if lv_date < cutoff:
                    days_old = (date.today() - lv_date).days
                    issues.append({
                        "site_id": sid,
                        "tab": "Hardware Inventory",
                        "detail": f"{device}: {days_old} gün önce doğrulanmış ({last_verified})",
                    })
            except ValueError:
                issues.append({
                    "site_id": sid,
                    "tab": "Hardware Inventory",
                    "detail": f"{device}: Last Verified geçersiz format ({last_verified})",
                })

    for impl in filtered_impl:
        sid = impl.get("Site ID", "?")
        last_verified = impl.get("Last Verified", "")
        if not last_verified:
            issues.append({
                "site_id": sid,
                "tab": "Implementation Details",
                "detail": "Last Verified yok",
            })
        else:
            try:
                lv_date = date.fromisoformat(last_verified)
                if lv_date < cutoff:
                    days_old = (date.today() - lv_date).days
                    issues.append({
                        "site_id": sid,
                        "tab": "Implementation Details",
                        "detail": f"{days_old} gün önce doğrulanmış ({last_verified})",
                    })
            except ValueError:
                issues.append({
                    "site_id": sid,
                    "tab": "Implementation Details",
                    "detail": f"Last Verified geçersiz format ({last_verified})",
                })

    return issues
