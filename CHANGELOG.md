# Changelog

## Session 4 — Polish, Feedback Loop, and Data Quality (2026-02-11)

### Added
- **Follow-up queries in threads** — queries now store thread state, enabling natural multi-query conversations without repeating `@mustafa`
- **New query types**: `implementation`, `hardware`, `support_history`, `ticket_detail`
  - Implementation: shows all site configuration parameters
  - Hardware: lists device inventory with totals
  - Support history: last 10 entries with status icons
  - Ticket detail: all fields for a specific ticket (e.g., SUP-004)
- **Context inheritance across operation transitions** — `site_id` and `ticket_id` carry forward from query → write and clarify → write transitions, so users don't need to re-specify identifiers
- **Feedback loop** — 👍/👎 buttons after every write operation; negative feedback captures "what should have happened" and writes to Feedback tab
- **Renamed Technician → Responsible** globally (code fields, prompts, sheet column header)
- **Google Sheet link** in help text and post-action readback messages via `get_google_sheet_url()`
- **Data quality queries** — two new query types:
  - `missing_data`: scans Sites, Hardware, Support Log for empty/incomplete fields
  - `stale_data`: reports records where Last Verified > 30 days old (configurable threshold)
- `format_data_quality_response()` formatter — groups issues by site with counts
- `read_all_implementation()` on SheetsService for cross-site stale data scans
- **Stock readback** after stock update confirmations (e.g., "📦 `İstanbul`: stokta toplam 45 birim")
- **Audit log guardrails** — failed writes logged with `FAILED` operation type (includes error snippet); cancellations logged with `CANCELLED` operation type
- `_build_audit_summary()` and `_operation_to_tab()` helpers in actions.py
- 78 new tests across 6 new test files — **181 total, all passing**

### Fixed
- **Follow-up queries silently ignored** — queries didn't store thread state, so thread replies after a query were dropped by the message handler
- **Clarify → write lost context** — clarify handler stored empty `data: {}`, losing `site_id`/`ticket_id` from previous state; multi-turn merge then cleared thread context on operation change
- **Query → write lost identifiers** — transitioning from a query to a write operation (e.g., "add a note to this ticket") cleared state and required re-specifying site_id
- **Stock readback always empty** — `_build_readback()` returned "" early when no `site_id`, but stock uses `location` not `site_id`; moved stock handler before the early return
- **Flaky `test_missing_fields_detected`** — Claude Haiku sometimes returned `clarify` instead of `log_support` for messages with many missing fields; sharpened prompt boundary between `clarify` (ambiguous intent) and `missing_fields` (known operation, incomplete data)

### Changed
- `_handle_query` now accepts `user_id`, `messages`, `language` params and stores thread state after every query response
- Clarify handler carries forward `site_id`/`ticket_id` from existing state into clarify state data
- Multi-turn merge treats `query` and `clarify` as transparent — inherits identifiers instead of clearing state
- System prompt: added `missing_data`/`stale_data` query types, sharpened `clarify` vs `missing_fields` boundary, strengthened `log_support` instruction
- Help text: added "Veri Kalitesi" section with data quality query examples
- `confirm_action` handler: wraps write in try/except with FAILED audit logging
- `cancel_action` handler: logs CANCELLED to audit before proceeding with chain

## Session 3 — Cloud Run Deploy + End-to-End Testing (2026-02-10/11)

### Added
- **Dockerfile** and `.dockerignore` for Cloud Run deployment
- **Create-site wizard** with chained operations: create_site → update_hardware → update_implementation → log_support
  - Roadmap message posted before first confirmation card
  - Step indicator on each card header ("Adım 1/4 — Yeni Site")
  - Final summary showing written vs skipped steps (`site ✅, donanım ✅, ayarlar ⏭️, destek kaydı ✅`)
  - Each step can be confirmed or skipped independently
- **Multi-tab extraction** in Claude prompt: single message can contain site + hardware + implementation + support data, returned as `extra_operations`
- **Last Verified date** injected automatically (defaults to today) for hardware and implementation writes; user can override via natural language
- **Duplicate site_id check** before create_site — warns if site already exists
- **Event deduplication** to prevent double-processing from Slack retries (thread-safe TTL cache on `event_ts`)
- **`extra_operations`** field on `ParseResult` model for chained operation support
- `build_chain_roadmap()` and `build_chain_final_summary()` formatters
- `CHAIN_LABELS` dict for short Turkish operation labels
- `step_info` parameter on `format_confirmation_message` for step indicators
- 22 new tests (20 chain + 2 sheets) — **103 total, all passing**

### Fixed
- **Support log write error** (`gspread APIError: Invalid values — list_value`): `devices_affected` was passed as a Python list; now serialized to comma-separated string
- **Duplicate message processing**: roadmap and first card appeared twice due to Slack `app_mention` event retries when handler takes >3s (Claude API call)

### Changed
- `app/handlers/actions.py`: overhauled confirm/cancel handlers for chain tracking (pending_operations, completed_operations, skipped_operations, chain_steps)
- `app/handlers/common.py`: added `_normalize_create_site_data()` for contacts flattening, country code expansion, and extra_operations extraction
- `app/services/claude.py`: parses `extra_operations` from Claude JSON response
- `app/services/sheets.py`: list serialization in `append_support_log`, new methods for stock/hardware reads
- `app/prompts/system_prompt.md`: added multi-tab extraction rules and last_verified extraction instruction

### Deployed
- Cloud Run: `europe-west1`, project `yika-ops-bot`
- Current revision: `mustafa-bot-00010-qzv`
- Slack Event Subscription URL pointed to Cloud Run service URL

### Known Issues
- Mid-chain text replies can overwrite chain state (thread lock not yet implemented)
- Technician name uses Slack display name, not short team name (acceptable for now)

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
