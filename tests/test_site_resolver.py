"""Tests for customer name → Site ID resolution."""

import pytest

from app.services.site_resolver import SiteResolver


@pytest.fixture
def resolver(sample_sites) -> SiteResolver:
    """Create a SiteResolver loaded with sample site data."""
    return SiteResolver(sample_sites)


class TestExactSiteIdMatch:
    def test_exact_site_id(self, resolver: SiteResolver):
        results = resolver.resolve("ASM-TR-01")
        assert len(results) == 1
        assert results[0]["Site ID"] == "ASM-TR-01"

    def test_exact_site_id_case_insensitive(self, resolver: SiteResolver):
        results = resolver.resolve("asm-tr-01")
        assert len(results) == 1
        assert results[0]["Site ID"] == "ASM-TR-01"


class TestExactCustomerNameMatch:
    def test_exact_customer_name(self, resolver: SiteResolver):
        results = resolver.resolve("Migros")
        assert len(results) == 1
        assert results[0]["Site ID"] == "MIG-TR-01"

    def test_exact_customer_name_mcdonalds(self, resolver: SiteResolver):
        results = resolver.resolve("McDonald's")
        assert len(results) == 1
        assert results[0]["Site ID"] == "MCD-EG-01"


class TestAbbreviationMatch:
    def test_abbreviation_asm(self, resolver: SiteResolver):
        results = resolver.resolve("ASM")
        assert len(results) == 1
        assert results[0]["Site ID"] == "ASM-TR-01"

    def test_abbreviation_mig(self, resolver: SiteResolver):
        results = resolver.resolve("MIG")
        assert len(results) == 1
        assert results[0]["Site ID"] == "MIG-TR-01"

    def test_abbreviation_mcd(self, resolver: SiteResolver):
        results = resolver.resolve("MCD")
        assert len(results) == 1
        assert results[0]["Site ID"] == "MCD-EG-01"


class TestFuzzyMatch:
    def test_fuzzy_anadolu(self, resolver: SiteResolver):
        results = resolver.resolve("Anadolu")
        assert len(results) == 1
        assert results[0]["Site ID"] == "ASM-TR-01"

    def test_fuzzy_mcdonalds_no_apostrophe(self, resolver: SiteResolver):
        results = resolver.resolve("McDonalds")
        assert len(results) == 1
        assert results[0]["Site ID"] == "MCD-EG-01"


class TestAmbiguousMatch:
    def test_ambiguous_returns_multiple(self, resolver: SiteResolver):
        """A very generic query could match multiple sites."""
        # Add sites with similar names
        sites = [
            {"Site ID": "TST-TR-01", "Customer": "Test Food Istanbul"},
            {"Site ID": "TST-TR-02", "Customer": "Test Food Ankara"},
        ]
        r = SiteResolver(sites)
        results = r.resolve("Test Food")
        assert len(results) == 2


class TestNoMatch:
    def test_no_match_returns_empty(self, resolver: SiteResolver):
        results = resolver.resolve("Nonexistent Company XYZ 12345")
        assert results == []
