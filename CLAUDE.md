# CLAUDE.md — Development Guide for Claude Code

## What This Project Is

A Slack bot ("Mustafa") for ERG Controls that manages IoT customer support operations through natural conversation in Turkish/English. It parses team messages, extracts structured data, and writes to a centralized Google Sheet.

**Read `yika-ops-bot-spec.md` first** — it's the complete specification.

## Development Approach

**Test-Driven Development (TDD), session by session.**

Each session:
1. Read the session's scope below
2. Write tests for that session's deliverables
3. Confirm tests fail (no implementation yet)
4. Implement until all tests pass
5. Update `README.md` and `CHANGELOG.md`
6. Result: a clean, committable increment

**Every session must end with all tests passing and a working deliverable.**

## Code Conventions

- Python 3.12, type hints everywhere
- Pydantic for data models
- Slack Bolt for Python (`slack-bolt`) for Slack integration
- Google Sheets via `gspread` (simpler than raw google-api-python-client)
- Slack messages use Block Kit formatting
- Tests with pytest (keep tests practical, not overkill)
- Environment config via `os.environ` with `.env` support via `python-dotenv`

## Project Structure

```
yika-ops-bot/
├── README.md
├── CHANGELOG.md
├── CLAUDE.md
├── yika-ops-bot-spec.md
├── requirements.txt
├── Dockerfile
├── .env.example
│
├── app/
│   ├── __init__.py
│   ├── main.py                  # Entry point, Slack Bolt app init
│   ├── config.py                # Environment config, constants
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── mentions.py          # @mustafa mention handler in channels
│   │   ├── messages.py          # DM message handler
│   │   ├── actions.py           # Button click handlers (confirm/cancel)
│   │   └── threads.py           # Thread context/state management
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── claude.py            # Claude API integration + prompt building
│   │   ├── sheets.py            # Google Sheets read/write operations
│   │   ├── site_resolver.py     # Customer name → Site ID resolution
│   │   └── data_quality.py      # Missing/stale data detection
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── operations.py        # Pydantic models for each operation type
│   │
│   ├── field_config/
│   │   ├── __init__.py
│   │   ├── field_requirements.py # FIELD_REQUIREMENTS + CONTEXT_RULES
│   │   └── friendly_fields.py   # FRIENDLY_FIELD_MAP (field → Turkish question)
│   │
│   ├── prompts/
│   │   ├── system_prompt.md     # Main Claude system prompt
│   │   ├── vocabulary.md        # Turkish↔English mappings
│   │   └── team_context.md      # Team members, site aliases, business rules
│   │
│   └── utils/
│       ├── __init__.py
│       ├── validators.py        # Field validation (dates, enums, required fields)
│       ├── formatters.py        # Slack Block Kit message formatting
│       └── missing_fields.py    # Friendly missing fields formatter
│
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_parsing.py          # Claude message parsing
│   ├── test_validators.py       # Field validation
│   ├── test_sheets.py           # Sheets read/write
│   ├── test_site_resolver.py    # Site name resolution
│   ├── test_formatters.py       # Slack message formatting
│   ├── test_chain.py            # Chain wizard + normalization
│   ├── test_data_quality.py     # Data quality with severity
│   ├── test_field_requirements.py # Field config structure
│   └── test_friendly_fields.py  # Friendly field messages
│
├── Dockerfile                   # Cloud Run deployment
└── .dockerignore
```

---

## SESSION 1: Core Engine (no Slack, no Sheets)

**Goal:** Build and test the parsing + validation + formatting core. Everything runs locally with mocked I/O. No external services needed.

**Deliverables:**
- Pydantic models for all operation types
- Claude API service (parses messages → structured JSON)
- System prompt + vocabulary + team context prompt files
- Validators (dates, enums, required fields, Site ID format)
- Site resolver (customer name → Site ID with fuzzy matching)
- Slack Block Kit formatters (confirmation messages, query responses, error messages)
- Turkish help text (for `/mustafa yardım` command — just the formatted string for now)

**Tests to write FIRST:**

`test_parsing.py` — Test that Claude returns correct structured JSON for each scenario. These call the real Claude API (Haiku) so they're integration tests. Use the test scenarios from the spec:
- Turkish support log (resolved visit) → correct operation, fields, root cause
- Support log with missing fields → correct missing_fields list
- False alarm → User Error root cause
- English support log → works the same
- First person "ben gittim" → technician = sender
- Create site → suggested Site ID correct
- Query → correct query_type
- Bulk hardware with sub-types → multiple entries parsed
- Future date → rejected
- Date > 90 days ago → warning flag

`test_validators.py`:
- Valid/invalid Site ID format (XXX-CC-NN)
- Future date rejection for support log
- Old date (>90 days) warning
- Resolved date < received date rejection
- Required fields check per operation type
- Dropdown value validation (valid and invalid)
- Positive integer check for quantities

`test_site_resolver.py`:
- Exact Site ID match
- Exact customer name match
- Abbreviation match ("ASM" → ASM-TR-01)
- Fuzzy match ("Anadolu" → ASM-TR-01)
- Ambiguous match (returns multiple candidates)
- No match (returns empty)

`test_formatters.py`:
- Confirmation message contains all fields
- Confirmation message has ✅/❌ buttons
- Query response for site summary is formatted
- Error message for unknown site is formatted
- Help text is in Turkish and contains all sections

**Implementation order:**
1. `app/models/operations.py` — Pydantic models
2. `app/prompts/*` — system prompt, vocabulary, team context
3. `app/utils/validators.py` — all validation logic
4. `app/services/site_resolver.py` — name resolution
5. `app/utils/formatters.py` — Block Kit formatting + help text
6. `app/services/claude.py` — Claude API integration
7. `app/config.py` — env config

**Environment needed:** Only `ANTHROPIC_API_KEY` for parsing tests.

**Commit message:** `feat: core parsing engine with validators, formatters, and site resolver`

---

## SESSION 2: Google Sheets + Slack Integration

**Goal:** Wire up Sheets read/write and Slack event handling. Bot can receive messages, parse them, show confirmations, and write to the sheet. Test locally with ngrok.

**Pre-session setup the developer must do manually:**
1. Create Google Sheet (upload v4 xlsx → Google Sheets)
2. Create GCP service account, download JSON key, share sheet as Editor
3. Enable Google Sheets API in GCP project
4. Create Slack App at api.slack.com with required scopes
5. Install app to workspace, get Bot Token + Signing Secret
6. Install ngrok (`brew install ngrok` or equivalent)

**Deliverables:**
- Sheets service (read all tabs, write rows, update cells, append to audit log)
- Slack Bolt app with mention handler, DM handler, button actions
- Thread state management (in-memory dict)
- Multi-turn conversation flow
- Confirmation → write → read-back flow
- Stock cross-reference inquiry after device changes
- `/mustafa yardım` help command
- Audit Log writes on every operation

**Tests to write FIRST:**

`test_sheets.py` — These use a real test sheet (or mock gspread):
- Read sites tab → returns list of site dicts
- Read hardware for a site → returns filtered rows
- Read support log for a site → returns filtered rows
- Append support log entry → row appears in sheet
- Update support log entry → specific cells changed
- Append hardware row → row appears
- Create site (write to Sites tab) → row appears
- Update implementation detail cell → correct cell updated
- Append audit log entry → row appears with timestamp
- Read stock → returns filtered rows

`test_threads.py` (new file):
- Store thread state → retrievable by thread_ts
- Accumulate data across turns → merged correctly
- Expire old thread state (manual trigger for now)
- Clear state on confirm/cancel

**Implementation order:**
1. `app/services/sheets.py` — all Sheets operations
2. `app/handlers/threads.py` — thread state management
3. `app/handlers/mentions.py` — @mustafa mention handler
4. `app/handlers/messages.py` — DM handler
5. `app/handlers/actions.py` — ✅/❌ button handlers
6. `app/main.py` — Bolt app init, route registration, `/mustafa yardım`
7. `.env.example` — all required env vars documented
8. End-to-end test: run locally + ngrok, send real messages in Slack

**Environment needed:**
```
ANTHROPIC_API_KEY=...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
GOOGLE_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
```

**Commit message:** `feat: sheets integration and slack bot with confirmation flow`

---

## SESSION 3: Deploy + End-to-End Testing ✅

**Status:** Complete — deployed to Cloud Run, 103 tests passing.

**What was built:**
- Dockerfile + `.dockerignore` for Cloud Run deployment
- Create-site wizard with chained operations (create_site → update_hardware → update_implementation → log_support)
  - Roadmap message, step indicators, final summary
- Multi-tab extraction: Claude extracts site + hardware + implementation + support from a single message
- Last Verified date auto-injection for hardware/implementation
- Duplicate site_id prevention
- Event deduplication (Slack retry protection)
- List value serialization fix for Sheets API

**Deployment:** Cloud Run `europe-west1`, service `mustafa-bot`, revision `mustafa-bot-00010-qzv`

**Known issues to address:**
- Mid-chain text replies can overwrite chain state (need thread lock during active chain)
- Technician resolves to Slack display name, not short team name

**22 new tests** in `tests/test_chain.py` (normalization, roadmap, step indicators, final summary, list serialization)

---

## SESSION 5: Schema Changes, Field Classification, and Data Quality Overhaul ✅

**Status:** Complete — 226 tests passing.

**What was built:**
- Implementation Details columns restructured: "Internet Connection" → Internet Provider (dropdown), SSID, Password
- WhatsApp Group column added to Sites tab
- Contract Status: "Pending" → "Awaiting Installation"
- Field classification config (`app/field_config/field_requirements.py`): must/important/important_conditional/optional per tab
- Context rules: "Awaiting Installation" sites skip hardware/implementation/support checks
- Data quality engine fully rewritten to use FIELD_REQUIREMENTS with severity levels (🔴 must / 🟡 important)
- Friendly missing fields messages: Turkish questions instead of raw field names
- Missing fields flow: only must fields block; important fields shown as suggestions
- "saha" terminology throughout all user-facing Turkish text
- Internet Provider dropdown validation ("ERG Controls", "Müşteri")

**New packages:** `app/field_config/` (field_requirements.py, friendly_fields.py), `app/utils/missing_fields.py`

**31 new tests** in `tests/test_field_requirements.py` (16) and `tests/test_friendly_fields.py` (15)

---

## v1.7.1: Live Sheet Alignment ✅

**Status:** Complete — 384+ tests passing.

**What was done:**
- Priority 1 (code fixes): Stock `Last Verified` column added to `STOCK_COLUMNS`, `read_sites()` now strips helper columns (`_SiteLabel`, etc.)
- Priority 2 (manual): Column order aligned in live sheet, missing helper columns added
- Priority 3 (partial): Conditional formatting script rewritten to match live sheet (7 fixes: stale verified 3 tabs, stale ticket 3-day threshold, Gateway in device type rules, facility type red severity, SL conditional rules, devices_affected important, AI guard for Awaiting Installation)
- Migration scripts (`scripts/`) are standalone manual tools, not called by runtime code

**16 new tests** in conditional formatting + 1 new sheets helper column test

---

## Important Rules (all sessions)

1. **Never write to Google Sheets without user confirmation.** Parse → show confirmation → wait for ✅ → write.
2. **Dropdown values always in English** regardless of conversation language.
3. **Free-text stays in user's language.**
4. **No future dates** in Support Log. Dates > 90 days ago get a warning (but allowed if confirmed).
5. **Only the initiating user** can click ✅/❌.
6. **Sheet is read-only for humans.** Only the service account writes.
7. **Bot responds in the same language the user writes in.**

## Maintaining Docs

After EVERY session:
- Update `README.md` with any new setup steps or usage instructions
- Update `CHANGELOG.md` with what was added/changed
- Keep `CLAUDE.md` accurate if anything deviates from plan

## Future Enhancements (NOT in v1)

These are documented for later implementation. Do not build these now:
- Rate limiting (per-user, per-channel daily limits)
- Token budget tracking and monthly spend alerts
- Message length limits
- Thread timeout with auto-cancel
- Weekly summary messages posted to channel
- Slash commands beyond `/mustafa yardım`
- Photo attachments from site visits
- Integration with YIKA SaaS dashboard API
- Auto-deploy via Cloud Build
