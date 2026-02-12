# Changelog

## v1.7.0 — Validation, Feedback, and Sheet Migrations (2026-02-12)

### Added
- **Must-field validation independent of Claude** — `enforce_must_fields()` validates required fields using `FIELD_REQUIREMENTS` before showing confirmation, catching fields Claude may have missed
- **Chain step must-field prompts** — each chain step shows required fields as friendly Turkish questions (e.g., "Hangi cihaz türü?") with `format_chain_input_prompt()`; facility-type-aware for implementation steps
- **Feedback on every interaction** — 👍/👎 buttons now appear after queries, data quality reports, cancel confirmations, and chain completions (previously only after writes)
  - Context-aware question: "Doğru kaydedildi mi?" for writes, "Faydalı oldu mu?" for queries
- **Help command field requirements section** — `/mustafa yardım` now shows required fields per operation with friendly Turkish names, dynamically generated from `FIELD_REQUIREMENTS` and `FRIENDLY_FIELD_MAP`
- **Dashboard migration script** (`scripts/migrate_dashboard.py`) — replaces "Total Devices" column with 5 device-type breakdown columns (Tags, Anchors, Gateways, Charging Docks, Other) using SUMIFS formulas
- **Site Viewer migration script** (`scripts/migrate_site_viewer.py`) — customer name selector ("Migros (MIG-TR-01)"), support log sorted by Received Date descending, widened key columns
- **Conditional formatting migration script** (`scripts/migrate_conditional_formatting.py`) — color-coded rules across all tabs: 🔴 red for empty must fields, 🟡 yellow for empty important fields, 🔵 blue for stale Last Verified (>30 days), 🟠 orange for aging open tickets (>7 days); supports `--dry-run` flag

### New Files
- `scripts/migrate_dashboard.py` — Dashboard device breakdown migration
- `scripts/migrate_site_viewer.py` — Site Viewer UX migration
- `scripts/migrate_conditional_formatting.py` — Conditional formatting migration
- `tests/test_chain_step_prompts.py` — 10 tests for chain step field prompts
- `tests/test_migrate_dashboard.py` — 11 tests for dashboard migration
- `tests/test_migrate_site_viewer.py` — 6 tests for site viewer migration
- `tests/test_migrate_conditional_formatting.py` — 22 tests for conditional formatting

### Changed
- `format_feedback_buttons()` now accepts `context` parameter ("write" or "query")
- `format_help_text()` dynamically generates field requirements from config
- Cancel handler sends feedback buttons after ending interaction
- Query handler stores `feedback_pending: True` in thread state

## v1.6.1 — Schema Patch: Column Alignment and Facility-Type Conditionals (2026-02-12)

### Fixed
- **Implementation Details column order** — mock and system prompt now match actual Google Sheet column order (Dispenser anchor power type at position 11, after Entry time)
- **"saha" terminology** — fixed remaining "site" → "saha" in Turkish ambiguous-match message

### Added
- **6 new Implementation Details columns** in field labels, system prompt, and friendly field map: Dispenser anchor placement, Clean hygiene time, HP alert time, Hand hygiene time, Hand hygiene interval, Hand hygiene type
- **`must_when_facility_type` classification** — Food sites require clean_hygiene_time, hp_alert_time, hand_hygiene_time, hand_hygiene_interval, hand_hygiene_type; Healthcare sites require tag_clean_to_red_timeout
- **Facility-type-aware data quality** — `find_missing_data()` evaluates implementation must fields based on site's Facility Type
- **Facility-type-aware missing fields** — `format_missing_fields_message()` accepts `facility_type` param for correct must/important classification
- 6 new facility-type data quality tests, 4 new facility-type classification tests, 2 new friendly field coverage tests

## v1.6.0 — Schema Changes, Field Classification, and Data Quality Overhaul (2026-02-12)

### Added
- **Field classification config** (`app/field_config/field_requirements.py`) — structured `must` / `important` / `important_conditional` / `optional` classification per tab, driving validation and data quality checks
- **Friendly missing fields messages** — missing fields shown as natural Turkish questions (e.g., "Bu konuyla kim ilgileniyor?") instead of raw field names; must fields block, important fields suggest
- **WhatsApp Group column** on Sites tab
- **Internet Provider / SSID / Password columns** replace "Internet Connection" on Implementation Details tab
- **Context-aware data quality** — "Awaiting Installation" sites skip hardware, implementation, and support log checks
- **Conditional field importance** — FW/HW Version only flagged for electronic devices (not Charging Dock, Power Bank, etc.); root_cause only flagged when status ≠ Open
- **Severity levels in data quality reports** — 🔴 for must fields, 🟡 for important fields
- `CONTEXT_RULES` config for status-based tab skipping
- `FRIENDLY_FIELD_MAP` with Turkish questions for all field names
- `format_missing_fields_message()` utility that classifies and formats missing fields

### Changed
- **Contract Status enum**: "Pending" renamed to "Awaiting Installation" across code, prompts, and vocabulary
- **Turkish terminology**: all user-facing Turkish text uses "saha" instead of "site" (e.g., "müşteri sahası", "Mevcut sahalar")
- **Data quality engine** (`data_quality.py`) fully rewritten to use `FIELD_REQUIREMENTS` instead of hardcoded field lists
- **Missing fields handling** in `common.py`: only must fields block the flow; important-only fields proceed to confirmation with a suggestion note
- `INTERNET_PROVIDERS` enum added: "ERG Controls", "Müşteri"
- `internet_provider` added to `DROPDOWN_FIELDS` for validation

### New Files
- `app/field_config/__init__.py` — field config package
- `app/field_config/field_requirements.py` — `FIELD_REQUIREMENTS` + `CONTEXT_RULES`
- `app/field_config/friendly_fields.py` — `FRIENDLY_FIELD_MAP`
- `app/utils/missing_fields.py` — `format_missing_fields_message()`
- `tests/test_field_requirements.py` — 16 tests for field config
- `tests/test_friendly_fields.py` — 15 tests for friendly field messages

## v1.5.0 — Create-Site Wizard, Data Quality, and UX Polish (2026-02-11)

### Added
- **Proactive chain wizard after create_site** — every new site now prompts for hardware and implementation details (with skip option), even if not mentioned in the original message
- **Empty chain step prompt** — when a chain step has no pre-filled data, shows "write your data or skip" with ⏭️ Atla button instead of an empty confirmation card
- **Explicit feedback via text** — users can type `feedback: ...` or `geri bildirim: ...` to log feedback directly to the Feedback sheet
- **Visible feedback confirmation** — clicking 👍 now shows "Teşekkürler, geri bildiriminiz kaydedildi!" with a closing message
- **Data quality: missing hardware/implementation** — `missing_data` query now flags sites with zero hardware or implementation records
- **Address in data quality checks** — missing Address is now flagged in the missing data report

### Fixed
- **Phone number formula parse error** — phone numbers starting with `+` (e.g., `+90...`) no longer cause `#ERROR!` in Google Sheets; all cell values are sanitized against formula injection (`+`, `=`, `@` prefixed with `'`)
- **Thread dies after feedback** — after 👍/👎 + closing message, thread is properly cleared with guidance to start a new thread
- **Chain context lost in follow-ups** — chain state (pending operations, step numbers, completed/skipped tracking) now survives through missing_fields prompts and multi-turn follow-ups in `process_message`
- **Chain step input misclassified** — when user provides data for a chain step (e.g., hardware details at step 2), Claude could misclassify it as a different operation (e.g., `update_stock`); now forces the operation to match the chain's expected step when `awaiting_chain_input` is set

### Changed
- `_normalize_create_site_data` always injects `update_hardware` and `update_implementation` as pending chain steps
- `_show_confirmation` accepts optional `chain_state` parameter for continuing existing chains
- `process_message` preserves chain context from existing thread state and passes it through to confirmation
- `_sanitize_cell()` applied to all `append_row` calls in sheets.py
- Post-feedback messages now include thread closure guidance

## v1.4.0 — Hotfix: Multi-turn Flow, Feedback, and Cancel (2026-02-11)

### Fixed
- **Missing fields reply lost create_site context** — when Claude re-classified a short reply (e.g., "İstanbul") as `update_site`, the bot cleared all `create_site` data; now keeps original operation when state has `missing_fields`
- **Feedback buttons not rendering** — `say(blocks=...)` without `text` fallback caused some Slack clients to not display the 👍/👎 buttons
- **Post-cancel replies ignored** — `thread_store.clear()` on cancel removed all state, so "tekrar yazabilirsiniz" was a lie; now keeps minimal thread state alive after cancel

### Added
- **Version announcement on deploy** — Mustafa posts a changelog message to the channel on first startup of each version (deduplicated via Audit Log)
- `app/version.py` with `__version__` and `RELEASE_NOTES`
- `SLACK_ANNOUNCE_CHANNEL` env var for deploy announcements

## v1.3.0 — Polish, Feedback Loop, and Data Quality (2026-02-11)

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

## v1.2.0 — Cloud Run Deploy + End-to-End Testing (2026-02-10/11)

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

### Fixed
- **Support log write error** (`gspread APIError: Invalid values — list_value`): `devices_affected` was passed as a Python list; now serialized to comma-separated string
- **Duplicate message processing**: roadmap and first card appeared twice due to Slack `app_mention` event retries when handler takes >3s (Claude API call)

### Changed
- `app/handlers/actions.py`: overhauled confirm/cancel handlers for chain tracking (pending_operations, completed_operations, skipped_operations, chain_steps)
- `app/handlers/common.py`: added `_normalize_create_site_data()` for contacts flattening, country code expansion, and extra_operations extraction
- `app/services/claude.py`: parses `extra_operations` from Claude JSON response
- `app/services/sheets.py`: list serialization in `append_support_log`, new methods for stock/hardware reads
- `app/prompts/system_prompt.md`: added multi-tab extraction rules and last_verified extraction instruction

## v1.1.0 — Sheets + Slack Integration (2026-02-10/11)

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

## v1.0.0 — Core Engine (2026-02-10)

### Added
- Pydantic models for all 9 operation types with enum definitions and required field mappings
- Claude Haiku 4.5 integration for parsing Turkish/English messages into structured JSON
- System prompt with vocabulary mappings and team context for accurate extraction
- Field validators: Site ID format, future date rejection, old date warnings, resolved-after-received, required fields, dropdown values, positive integers
- Site resolver with exact match, abbreviation, alias, and fuzzy matching (thefuzz)
- Slack Block Kit formatters: confirmation messages with buttons, query responses, error messages
- Turkish help guide text (Kullanim Kilavuzu)
