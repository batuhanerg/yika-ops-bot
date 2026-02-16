"""Tests for deployment message formatting — RELEASE_NOTES parsing from CHANGELOG.md."""

import textwrap
from pathlib import Path

import pytest

from app.version import (
    parse_release_notes,
    format_deploy_message,
    get_release_notes_for_current_version,
)


# --- Sample CHANGELOG content for tests ---

SAMPLE_CHANGELOG = textwrap.dedent("""\
    # Changelog

    ## v1.8.1 — Human-readable deploy messages (2026-02-15)

    <!-- RELEASE_NOTES v1.8.1
    🔧 Daha önce versiyon mesajları teknik ve robotik görünüyordu — artık takıma anlaşılır şekilde anlatıyorum.
    ✨ Artık her versiyon için Türkçe özet yazılıyor.
    -->

    ### Added
    - Human-readable deployment messages parsed from CHANGELOG.md

    ## v1.8.0 — Scheduled Messaging (2026-02-15)

    <!-- RELEASE_NOTES v1.8.0
    ✨ Artık her pazartesi otomatik haftalık veri kalitesi raporu gönderiyorum.
    ✨ 3 günden fazla açık kalan ticketlar için günlük uyarı atıyorum.
    🔧 Geçen haftadan bu yana çözülen sorunları raporda gösteriyorum.
    -->

    ### Added
    - Weekly data quality report
    - Daily aging alert

    ## v1.7.5 — Bug Fixes Round 3 (2026-02-14)

    ### Fixed
    - Bug 8, Bug 9, Bug 10, Bug 11
""")


class TestParseReleaseNotes:
    """Test parsing RELEASE_NOTES blocks from CHANGELOG content."""

    def test_parse_release_notes(self):
        """Parses RELEASE_NOTES block for a given version."""
        notes = parse_release_notes(SAMPLE_CHANGELOG, "1.8.1")
        assert notes is not None
        assert len(notes) == 2
        assert "robotik" in notes[0]
        assert "✨" in notes[1]

    def test_parse_release_notes_different_version(self):
        """Parses correct block when multiple versions have notes."""
        notes = parse_release_notes(SAMPLE_CHANGELOG, "1.8.0")
        assert notes is not None
        assert len(notes) == 3
        assert "pazartesi" in notes[0]

    def test_parse_release_notes_missing(self):
        """Returns None when no RELEASE_NOTES block exists for version."""
        notes = parse_release_notes(SAMPLE_CHANGELOG, "1.7.5")
        assert notes is None

    def test_parse_release_notes_nonexistent_version(self):
        """Returns None for a version that doesn't exist at all."""
        notes = parse_release_notes(SAMPLE_CHANGELOG, "99.99.99")
        assert notes is None

    def test_parse_release_notes_strips_whitespace(self):
        """Each note line is stripped of leading/trailing whitespace."""
        notes = parse_release_notes(SAMPLE_CHANGELOG, "1.8.1")
        assert notes is not None
        for note in notes:
            assert note == note.strip()


class TestFormatDeployMessage:
    """Test Slack deployment message formatting."""

    def test_format_deploy_message_with_notes(self):
        """Formats conversational message with release notes."""
        notes = [
            "🔧 Daha önce X sorunu vardı — artık düzeldi.",
            "✨ Artık Y özelliği var.",
        ]
        msg = format_deploy_message("1.8.1", notes)
        assert "v1.8.1" in msg
        assert "Merhaba" in msg
        assert "🔧 Daha önce X sorunu vardı — artık düzeldi." in msg
        assert "✨ Artık Y özelliği var." in msg
        assert "💬" in msg  # closing line

    def test_format_deploy_message_fallback(self):
        """Falls back to old bullet format when no release notes exist."""
        old_notes = [
            "Haftalık rapor eklendi",
            "Günlük uyarı eklendi",
        ]
        msg = format_deploy_message("1.8.0", None, fallback_bullets=old_notes)
        assert "v1.8.0" in msg
        assert "• Haftalık rapor eklendi" in msg
        assert "• Günlük uyarı eklendi" in msg

    def test_format_deploy_message_fallback_no_bullets(self):
        """When no notes and no fallback, still produces a valid message."""
        msg = format_deploy_message("1.8.0", None)
        assert "v1.8.0" in msg

    def test_release_notes_max_entries(self):
        """No more than 5 entries per version in RELEASE_NOTES."""
        changelog_with_many = textwrap.dedent("""\
            # Changelog

            ## v2.0.0

            <!-- RELEASE_NOTES v2.0.0
            🔧 Fix 1
            🔧 Fix 2
            🔧 Fix 3
            🔧 Fix 4
            🔧 Fix 5
            🔧 Fix 6
            🔧 Fix 7
            -->
        """)
        notes = parse_release_notes(changelog_with_many, "2.0.0")
        assert notes is not None
        # Parser should cap at 5 entries
        assert len(notes) <= 5

    def test_format_deploy_message_empty_fallback(self):
        """Empty fallback list produces clean version-only message (no stale bullets)."""
        msg = format_deploy_message("1.8.3", None, fallback_bullets=[])
        assert "v1.8.3" in msg
        assert "•" not in msg  # No bullet points


class TestChangelogPathResolution:
    """Verify CHANGELOG.md is found relative to version.py, not cwd."""

    def test_changelog_path_relative_to_version_py(self):
        """get_release_notes_for_current_version() uses __file__-relative path."""
        import app.version as version_mod
        version_py = Path(version_mod.__file__)
        changelog_path = version_py.parent.parent / "CHANGELOG.md"
        assert changelog_path.exists(), (
            f"CHANGELOG.md not found at {changelog_path}. "
            f"version.py is at {version_py}"
        )

    def test_get_release_notes_finds_current_version(self):
        """get_release_notes_for_current_version() returns notes for __version__."""
        notes = get_release_notes_for_current_version()
        assert notes is not None, (
            "get_release_notes_for_current_version() returned None — "
            "CHANGELOG.md is missing or has no RELEASE_NOTES block for current version"
        )
        assert len(notes) >= 1

    def test_changelog_included_in_dockerfile(self):
        """Dockerfile includes COPY CHANGELOG.md so it's available in the container."""
        dockerfile = Path(__file__).parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "COPY CHANGELOG.md" in content, (
            "Dockerfile must COPY CHANGELOG.md for deploy messages to work"
        )

    def test_dockerignore_allows_changelog(self):
        """CHANGELOG.md is not excluded by .dockerignore."""
        dockerignore = Path(__file__).parent.parent / ".dockerignore"
        content = dockerignore.read_text()
        # *.md excludes all markdown, but !CHANGELOG.md should re-include it
        if "*.md" in content:
            assert "!CHANGELOG.md" in content, (
                ".dockerignore excludes *.md but does not re-include !CHANGELOG.md"
            )
