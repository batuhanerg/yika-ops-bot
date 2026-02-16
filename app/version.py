"""Version and release notes for deploy announcements."""

from __future__ import annotations

import re
from pathlib import Path

__version__ = "1.8.7"

# Legacy fallback bullets (used only when CHANGELOG.md is missing from the image)
RELEASE_NOTES: list[str] = []

_MAX_RELEASE_ENTRIES = 5


def parse_release_notes(changelog_content: str, version: str) -> list[str] | None:
    """Parse a RELEASE_NOTES HTML comment block for a specific version.

    Looks for:
        <!-- RELEASE_NOTES vX.Y.Z
        line1
        line2
        -->

    Returns a list of non-empty lines, or None if no block found.
    Caps at 5 entries.
    """
    pattern = re.compile(
        rf"<!--\s*RELEASE_NOTES\s+v{re.escape(version)}\s*\n(.*?)-->",
        re.DOTALL,
    )
    match = pattern.search(changelog_content)
    if not match:
        return None

    lines = [line.strip() for line in match.group(1).strip().splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return None
    return lines[:_MAX_RELEASE_ENTRIES]


def format_deploy_message(
    version: str,
    notes: list[str] | None,
    *,
    fallback_bullets: list[str] | None = None,
) -> str:
    """Format the Slack deployment announcement message.

    If notes (from RELEASE_NOTES block) are available, use the conversational format.
    Otherwise fall back to the old bullet-point format.
    """
    if notes:
        body = "\n".join(notes)
        return (
            f"Merhaba! Birkaç iyileştirme yaptım (v{version}):\n\n"
            f"{body}\n\n"
            f"Bir sorun yaşarsanız bana yazın! 💬"
        )

    # Fallback: old bullet-point style
    if fallback_bullets:
        bullets = "\n".join(f"• {b}" for b in fallback_bullets)
        return f"Yeni versiyona geçtim: *v{version}* 🚀\n\n{bullets}"

    return f"Yeni versiyona geçtim: *v{version}* 🚀"


def get_release_notes_for_current_version() -> list[str] | None:
    """Load and parse RELEASE_NOTES for __version__ from CHANGELOG.md."""
    changelog_path = Path(__file__).parent.parent / "CHANGELOG.md"
    if not changelog_path.exists():
        return None
    content = changelog_path.read_text(encoding="utf-8")
    return parse_release_notes(content, __version__)
