# Changelog

## Session 2 — Sheets + Slack Integration (2026-02-10/11)

### Added
- Google Sheets service: read/write all tabs (Sites, Hardware, Implementation Details, Support Log, Stock, Audit Log)
- Slack Bolt app with @mustafa mention handler, DM handler, and channel thread reply handler
- Thread state management (in-memory, keyed by thread_ts) with merge, expire, and clear
- Shared message processing pipeline: parse → validate → resolve site → confirm/ask
- Multi-turn conversation support: operation lock + data merge for thread follow-ups
- Code-level validation of missing fields (filters Claude's over-reporting)
- update_support row lookup: finds most recent non-resolved entry for the site
- Confirm/cancel button handlers with initiating-user enforcement
- Post-write readback summaries (total entries, open tickets)
- Stock cross-reference inquiry after device replacement mentions
- `/mustafa yardım` slash command
- Audit Log tab created in Google Sheet with proper headers
- Query handlers for site summary, open issues, and stock
- "Pending" root cause enum; root_cause optional when status is Open
- 23 new tests (14 sheets + 7 threads + 2 validators) — 81 total, all passing

### Fixed (live testing)
- Confirm button thread_ts lookup (was using bot message ts instead of thread root)
- Stale date in system prompt (now refreshed per parse_message call)
- Thread replies in private channels (requires message.groups event subscription)
- Multi-turn context not carried through confirmation state
- Claude switching operation type in follow-ups (code-level enforcement)

### Changed
- Simplified system prompt: removed verbose Turkish→English tables, condensed date/field rules
- Trimmed vocabulary.md to enum values + ERG-specific jargon only
- Trimmed team_context.md: removed duplicate vocabulary sections

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
