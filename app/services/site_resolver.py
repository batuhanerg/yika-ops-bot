"""Customer name → Site ID resolution with fuzzy matching."""

from __future__ import annotations

from thefuzz import fuzz

# Hard-coded aliases from team_context.md (augment at runtime from Sites tab)
KNOWN_ALIASES: dict[str, list[str]] = {
    "ASM-TR-01": ["ASM", "Anadolu Sağlık", "Anadolu", "Anadolu Sağlık Merkezi"],
    "MIG-TR-01": ["MIG", "Migros"],
    "MCD-EG-01": ["MCD", "McDonald's", "McDonalds", "Mek"],
}

FUZZY_THRESHOLD = 70


class SiteResolver:
    """Resolves customer names/aliases/abbreviations to Site ID(s)."""

    def __init__(self, sites: list[dict]) -> None:
        self.sites = sites
        self._build_index()

    def _build_index(self) -> None:
        """Build lookup indexes from site data + known aliases."""
        # site_id (upper) → site dict
        self.by_id: dict[str, dict] = {}
        # customer name (lower) → list of site dicts (handles duplicates)
        self.by_customer: dict[str, list[dict]] = {}
        # alias (lower) → list of site dicts (handles prefix collisions)
        self.by_alias: dict[str, list[dict]] = {}

        for site in self.sites:
            sid = site["Site ID"]
            self.by_id[sid.upper()] = site

            customer_key = site.get("Customer", "").strip().lower()
            if customer_key:
                self.by_customer.setdefault(customer_key, []).append(site)

            # Extract abbreviation from Site ID (prefix before first dash)
            prefix = sid.split("-")[0].lower()
            self.by_alias.setdefault(prefix, []).append(site)

        # Add known aliases (deduplicate by Site ID)
        for sid, aliases in KNOWN_ALIASES.items():
            site = self.by_id.get(sid.upper())
            if site:
                for alias in aliases:
                    key = alias.lower()
                    existing = self.by_alias.setdefault(key, [])
                    if not any(s["Site ID"] == sid for s in existing):
                        existing.append(site)

    def resolve(self, query: str) -> list[dict]:
        """Resolve a query to matching site(s).

        Returns a list of matching site dicts. Empty list = no match.
        Multiple entries = ambiguous.
        """
        q = query.strip()
        if not q:
            return []

        # 1. Exact Site ID match (case-insensitive)
        if q.upper() in self.by_id:
            return [self.by_id[q.upper()]]

        q_lower = q.lower()

        # 2. Exact customer name match
        if q_lower in self.by_customer:
            return list(self.by_customer[q_lower])

        # 3. Alias/abbreviation match
        if q_lower in self.by_alias:
            return list(self.by_alias[q_lower])

        # 4. Fuzzy match against customer names and aliases
        candidates: list[tuple[int, dict]] = []
        seen_ids: set[str] = set()

        for site in self.sites:
            customer = site.get("Customer", "")
            score = fuzz.partial_ratio(q_lower, customer.lower())
            if score >= FUZZY_THRESHOLD and site["Site ID"] not in seen_ids:
                candidates.append((score, site))
                seen_ids.add(site["Site ID"])

        # Also check aliases — use fuzz.ratio (not partial_ratio) to prevent
        # short aliases like "est" from matching long queries like "este nove"
        for alias_key, alias_sites in self.by_alias.items():
            score = fuzz.ratio(q_lower, alias_key)
            if score >= FUZZY_THRESHOLD:
                for site in alias_sites:
                    if site["Site ID"] not in seen_ids:
                        candidates.append((score, site))
                        seen_ids.add(site["Site ID"])

        if not candidates:
            return []

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [site for _, site in candidates]
