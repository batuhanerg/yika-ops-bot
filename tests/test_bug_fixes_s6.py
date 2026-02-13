"""Tests for Session 6 bug fixes."""

import pytest

from app.services.site_resolver import SiteResolver
from app.utils.formatters import format_chain_input_prompt
from app.utils.missing_fields import enforce_must_fields


class TestBug1ChainSiteIdContext:
    """Bug 1: Chain step should not ask for site_id when it's already known."""

    def test_chain_step_hardware_site_id_not_in_missing(self):
        """Chain step 2 (hardware) with site_id in data → site_id not in missing."""
        data = {"site_id": "TCO-TR-01", "device_type": "Gateway", "qty": 5}
        missing = enforce_must_fields("update_hardware", data, [])
        assert "site_id" not in missing

    def test_chain_step_hardware_site_id_removed_from_claude_missing(self):
        """Even if Claude reports site_id as missing, enforce removes it when present."""
        data = {"site_id": "TCO-TR-01", "device_type": "Gateway", "qty": 5}
        missing = enforce_must_fields("update_hardware", data, ["site_id"])
        assert "site_id" not in missing

    def test_chain_step_implementation_site_id_not_in_missing(self):
        """Chain step 3 (implementation) with site_id in data → site_id not in missing."""
        data = {"site_id": "TCO-TR-01", "internet_provider": "ERG Controls", "ssid": "ERG-Net"}
        missing = enforce_must_fields("update_implementation", data, [])
        assert "site_id" not in missing

    def test_chain_prompt_excludes_site_id(self):
        """format_chain_input_prompt() should not list site_id in must fields."""
        blocks = format_chain_input_prompt(2, 4, "update_hardware")
        body_text = blocks[0]["text"]["text"]
        assert "Hangi müşteri/saha için?" not in body_text
        # Should still mention other must fields
        assert "Hangi cihaz türü?" in body_text
        assert "Kaç adet?" in body_text

    def test_chain_prompt_excludes_site_id_for_implementation(self):
        """format_chain_input_prompt() for implementation should not ask for site."""
        blocks = format_chain_input_prompt(3, 4, "update_implementation", facility_type="Food")
        body_text = blocks[0]["text"]["text"]
        assert "Hangi müşteri/saha için?" not in body_text
        # Should still mention implementation must fields
        assert "İnternet" in body_text or "SSID" in body_text


class TestBug2EsteNoveResolution:
    """Bug 2: 'este nove' should resolve to EST-TR-01, not EST-BR-09."""

    def test_este_nove_lowercase_resolves_correctly(self):
        """Even with same-prefix sites, exact customer match should win."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove Test"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("este nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"

    def test_este_nove_titlecase_resolves_correctly(self):
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove Test"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("Este Nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"

    def test_duplicate_customer_name_returns_all_matches(self):
        """Two sites with identical customer name → return both as ambiguous."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Este Nove"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("Este Nove")
        # Both match — ambiguous, return both
        assert len(results) == 2
        site_ids = {s["Site ID"] for s in results}
        assert "EST-TR-01" in site_ids
        assert "EST-BR-09" in site_ids

    def test_short_alias_does_not_outmatch_full_customer_name(self):
        """'est' alias should not beat exact customer match for 'este nove'."""
        sites = [
            {"Site ID": "EST-TR-01", "Customer": "Este Nove"},
            {"Site ID": "EST-BR-09", "Customer": "Something Else"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("este nove")
        assert len(results) == 1
        assert results[0]["Site ID"] == "EST-TR-01"


class TestBug3SahaTerm:
    """Bug 3: Turkish-facing text should use 'saha' not 'site'."""

    def test_no_turkish_site_in_user_facing_py_strings(self):
        """No Turkish-inflected 'site' in .py files under app/ (user-facing text)."""
        import re
        from pathlib import Path

        # Turkish suffixes that would indicate "site" is used as a Turkish word
        # e.g. "siteye", "sitesi", "siteyi", "sitede", "siteler", "mevcut bir site"
        pattern = re.compile(
            r'(?:mevcut\s+bir\s+site|bir\s+site[ysd]|site[ysd][ieaı]|siteler|sitesi)',
            re.IGNORECASE,
        )
        app_dir = Path(__file__).parent.parent / "app"
        violations: list[str] = []
        for py_file in app_dir.rglob("*.py"):
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
        assert violations == [], f"Turkish 'site' found:\n" + "\n".join(violations)

    def test_system_prompt_has_saha_rule(self):
        """System prompt should instruct Claude to use 'saha' in Turkish."""
        from pathlib import Path
        prompt = (Path(__file__).parent.parent / "app" / "prompts" / "system_prompt.md").read_text()
        assert "saha" in prompt.lower()


class TestBug4FeedbackWording:
    """Bug 4: 👎 should say 'Nasıl daha iyi yapabilirdim?' for all interaction types."""

    def test_feedback_negative_uses_new_wording(self):
        """The feedback_negative handler should use unified wording."""
        import inspect
        from app.handlers import actions
        source = inspect.getsource(actions.register)
        assert "Nasıl daha iyi yapabilirdim?" in source, \
            "feedback_negative handler should use 'Nasıl daha iyi yapabilirdim?'"

    def test_feedback_negative_not_old_wording(self):
        """Old write-specific wording should not appear."""
        import inspect
        from app.handlers import actions
        source = inspect.getsource(actions.register)
        assert "Ne olmalıydı" not in source, \
            "Old write-specific wording 'Ne olmalıydı' should be removed"
