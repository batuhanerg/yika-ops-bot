# Changelog

## Session 1 — Core Engine (2026-02-10)

### Added
- Pydantic models for all 9 operation types with enum definitions and required field mappings
- Claude Haiku 4.5 integration for parsing Turkish/English messages into structured JSON
- System prompt with vocabulary mappings and team context for accurate extraction
- Field validators: Site ID format, future date rejection, old date warnings, resolved-after-received, required fields, dropdown values, positive integers
- Site resolver with exact match, abbreviation, alias, and fuzzy matching (thefuzz)
- Slack Block Kit formatters: confirmation messages with buttons, query responses, error messages
- Turkish help guide text (Kullanim Kilavuzu)
- 58 tests (10 integration + 48 unit) — all passing
