# Mustafa — ERG Controls Ops Bot

A Slack bot for ERG Controls that manages IoT customer support operations through natural conversation in Turkish/English. Parses team messages, extracts structured data, and writes to a centralized Google Sheet.

## Status

**v1.8.4** — 579 tests passing.
Deployed to Cloud Run (`europe-west1`), live in `#technical-operations`.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in all values in .env (see .env.example)
pytest
```

### Run the bot locally

```bash
# Start the Slack bot (HTTP mode for ngrok/Cloud Run)
python -m app.main

# In another terminal, start ngrok
ngrok http 8080

# Set Slack Event Subscription URL to: https://<ngrok-url>/slack/events
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Haiku |
| `SLACK_BOT_TOKEN` | Slack Bot Token (xoxb-...) |
| `SLACK_SIGNING_SECRET` | Slack Signing Secret |
| `GOOGLE_SHEET_ID` | Google Sheet ID from URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GCP service account JSON (single line) |
| `SLACK_CHANNEL_ID` | Slack channel ID for scheduled reports (e.g. `C_TECHOPS`) |
| `CRON_SECRET` | Shared secret for Cloud Scheduler authentication |
| `SLACK_ANNOUNCE_CHANNEL` | _(Optional)_ Channel ID for deploy announcements |

## What's Working

### Session 1: Core Engine
- Message parsing via Claude Haiku 4.5 (Turkish + English)
- 9 operation types: log_support, create_site, update_support, update_site, update_hardware, update_implementation, update_stock, query, help
- Validators (Site ID format, dates, dropdowns, required fields)
- Site resolver with fuzzy matching
- Slack Block Kit formatters with confirmation buttons

### Session 2: Sheets + Slack Integration
- Google Sheets service (read/write all tabs: Sites, Hardware, Implementation, Support Log, Stock, Audit Log)
- Slack Bolt app with `@mustafa` mention handler and DM handler
- Thread state management for multi-turn conversations
- Confirmation flow with buttons (only initiating user can confirm/cancel)
- Post-write readback summaries
- Stock cross-reference inquiry after device replacements
- `/mustafa yardım` slash command
- Audit Log writes on every operation

### Session 3: Cloud Run Deploy + E2E Testing
- Dockerized and deployed to Google Cloud Run (`europe-west1`)
- **Create-site wizard** — chained multi-step flow: create_site → update_hardware → update_implementation → log_support
  - Roadmap message, step indicators (Adım 1/4), final summary with ✅/⏭️ per step
- Multi-tab extraction: single message → site + hardware + implementation + support data
- Last Verified date auto-injected for hardware/implementation writes
- Duplicate site_id prevention
- Event deduplication against Slack retries

### Session 4: Polish, Feedback Loop, and Data Quality
- **Conversational queries** — follow-up questions in threads work naturally (site summary → implementation → hardware → ticket detail)
- New query types: implementation, hardware, support_history, ticket_detail
- Context inheritance: `site_id`/`ticket_id` carry forward across query → write and clarify → write transitions
- **Feedback loop** — 👍/👎 buttons after every write, negative feedback captures "what should have happened" → Feedback tab
- **Renamed Technician → Responsible** globally (code, prompts, sheet column)
- **Google Sheet link** in help text and post-action readback messages
- **Data quality queries** — `missing_data` and `stale_data` query types scan for incomplete/outdated records
- **Stock readback** after stock update confirmations
- **Audit log guardrails** — failed writes and cancellations now logged with FAILED/CANCELLED operation types

### Session 5: Schema Changes, Field Classification, and Data Quality Overhaul
- **Implementation Details columns restructured** — "Internet Connection" replaced with Internet Provider (dropdown), SSID, Password
- **WhatsApp Group column** added to Sites tab
- **Contract Status**: "Pending" renamed to "Awaiting Installation"
- **Field classification config** — `FIELD_REQUIREMENTS` with must/important/optional per tab; `CONTEXT_RULES` for status-based tab skipping
- **Data quality engine rewritten** — uses `FIELD_REQUIREMENTS` with severity levels (🔴 must, 🟡 important), context-aware skipping, conditional importance
- **Friendly missing fields** — Turkish questions instead of raw field names; only must fields block the flow
- **"saha" terminology** — all user-facing Turkish text uses "saha" instead of "site"

### Session 6: Validation, Feedback, and Sheet Migrations
- **Must-field validation independent of Claude** — `enforce_must_fields()` catches missing required fields before confirmation
- **Chain step field prompts** — each chain step shows required fields as friendly Turkish questions, facility-type-aware
- **Feedback on every interaction** — 👍/👎 buttons after writes, queries, cancels, and chain completions
- **Help command overhaul** — field requirements per operation shown with friendly Turkish names
- **Dashboard migration** — "Total Devices" → device-type breakdown (Tags, Anchors, Gateways, Charging Docks, Other)
- **Site Viewer migration** — customer name selector, descending date sort, widened columns
- **Conditional formatting migration** — color-coded rules for empty must/important fields, stale data, aging tickets

### Hotfixes (v1.8.x)
- **Stock prompt after hardware writes** — after confirming a hardware inventory write with device quantities, prompts to update stock; user replies with warehouse name to subtract/add, or declines
- **HW/FW Version normalization** — strips leading `v`/`V` prefix on write (`"v3.6.0"` → `"3.6.0"`)
- **Feedback button UX** — replaces interactive 👍/👎 buttons with static text after click via `chat_update()`
- **Human-readable deploy messages** — `RELEASE_NOTES` blocks in CHANGELOG.md parsed and posted to Slack on deploy

### Session 7: Scheduled Messaging
- **Weekly data quality report** — automated report posted to `#technical-operations` every Monday
  - Sections: 🔴 must, 🟡 important, 🟠 aging (3+ days), 🔵 stale (30+ days), ✅ overall status with completeness %
  - Resolution tracking: compares current vs last week's snapshot, shows "X/Y acil sorun çözüldü"
  - Excludes Awaiting Installation sites from resolution counts (status change ≠ resolution)
  - Feedback buttons on report; thread replies processed as normal operations
- **Daily aging alert** — posts when open tickets exceed 3 days, skips silently otherwise
- **HTTP endpoints** — `POST /cron/weekly-report` and `POST /cron/daily-aging` via Flask Blueprint
- **Flask migration** — app now runs as Flask wrapping Bolt via `SlackRequestHandler`
  - `GET /health` and `GET /` for Cloud Run health checks
  - `process_before_response=False` (Bolt default) ensures Slack 3-second timeout compliance

## Project Structure

```
app/
├── main.py                 — Entry point, Flask wrapping Bolt + cron routes
├── config.py               — Environment configuration
├── version.py              — Version and release notes
├── models/operations.py    — Pydantic models, enums, required fields
├── field_config/
│   ├── field_requirements.py — FIELD_REQUIREMENTS + CONTEXT_RULES
│   └── friendly_fields.py  — FRIENDLY_FIELD_MAP (field → Turkish question)
├── services/
│   ├── claude.py           — Claude API integration + prompt building
│   ├── sheets.py           — Google Sheets read/write operations
│   ├── site_resolver.py    — Customer name → Site ID resolution
│   ├── data_quality.py     — Missing/stale data detection
│   └── scheduled_reports.py — Weekly report + daily aging alert generation
├── routes/
│   └── cron.py             — HTTP endpoints for Cloud Scheduler
├── handlers/
│   ├── common.py           — Shared message processing pipeline
│   ├── mentions.py         — @mustafa mention handler
│   ├── messages.py         — DM message handler
│   ├── actions.py          — Confirm/cancel button handlers + chain logic
│   └── threads.py          — Thread state management
├── prompts/
│   ├── system_prompt.md    — Main Claude system prompt
│   ├── vocabulary.md       — Enum values & ERG-specific jargon
│   └── team_context.md     — Team members, site aliases, business rules
└── utils/
    ├── validators.py       — Field validation
    ├── formatters.py       — Slack Block Kit message formatting
    └── missing_fields.py   — Friendly missing fields formatter

tests/
├── test_parsing.py         — Claude parsing (10 integration tests)
├── test_validators.py      — Field validation (34 tests)
├── test_site_resolver.py   — Site resolution (13 tests)
├── test_formatters.py      — Message formatting (6 tests)
├── test_sheets.py          — Sheets operations (16 tests, mocked)
├── test_threads.py         — Thread state (7 tests)
├── test_chain.py           — Chain wizard + normalization (20 tests)
├── test_data_quality.py    — Data quality with severity (28 tests)
├── test_field_requirements.py — Field config structure (16 tests)
├── test_friendly_fields.py — Friendly field messages (15 tests)
├── test_stock_audit.py     — Stock readback + key mapping (5 tests)
├── test_audit_guardrails.py — Failed/cancelled audit logging (12 tests)
├── test_feedback.py        — Feedback loop (thumbs up/down)
├── test_rename_responsible.py — Technician→Responsible rename
├── test_session3_gaps.py   — Dedup, stock xref, permissions (14 tests)
├── test_help_and_readback.py  — Help text + Sheet link readback
├── test_chain_step_prompts.py — Chain step field prompts (10 tests)
├── test_migrate_dashboard.py  — Dashboard migration (11 tests)
├── test_migrate_site_viewer.py — Site Viewer migration (6 tests)
├── test_migrate_conditional_formatting.py — Conditional formatting (22 tests)
├── test_scheduled_reports.py — Weekly report + daily aging (28 tests)
├── test_cron.py             — Cron HTTP endpoints + auth (13 tests)
├── test_report_threads.py   — Report thread replies + feedback (6 tests)
├── test_deploy_message.py   — Deploy message formatting + CHANGELOG parsing (10 tests)
├── test_feedback_button_update.py — Feedback button replacement UX (14 tests)
├── test_stock_prompt.py     — Stock prompt after hardware writes (18 tests)
└── test_version_normalize.py — HW/FW version normalization (9 tests)

scripts/
├── migrate_technician_to_responsible.py — Column rename migration
├── migrate_dashboard.py    — Dashboard device breakdown migration
├── migrate_site_viewer.py  — Site Viewer UX migration
├── migrate_conditional_formatting.py — Conditional formatting migration
└── normalize_versions.py   — One-time HW/FW version prefix cleanup
```

### Deploy to Cloud Run

```bash
gcloud run deploy mustafa-bot \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 60
```

Then update the Slack Event Subscription URL to the Cloud Run service URL + `/slack/events`.

### Set Up Cloud Scheduler (Cron Jobs)

Two scheduled jobs post automated reports to `#technical-operations`:

1. **Generate a shared secret** and set it as an env var on Cloud Run:

```bash
# Generate a random secret
CRON_SECRET=$(openssl rand -hex 32)

# Update the Cloud Run service with the secret + channel ID
gcloud run services update mustafa-bot \
  --region europe-west1 \
  --set-env-vars "CRON_SECRET=$CRON_SECRET,SLACK_CHANNEL_ID=C_YOUR_CHANNEL_ID"
```

2. **Create the weekly report job** (every Monday at 09:00 Istanbul time):

```bash
gcloud scheduler jobs create http mustafa-weekly-report \
  --location europe-west1 \
  --schedule "0 9 * * 1" \
  --time-zone "Europe/Istanbul" \
  --uri "https://YOUR_CLOUD_RUN_URL/cron/weekly-report" \
  --http-method POST \
  --headers "Authorization=Bearer $CRON_SECRET" \
  --attempt-deadline 60s
```

3. **Create the daily aging alert job** (every weekday at 09:00 Istanbul time):

```bash
gcloud scheduler jobs create http mustafa-daily-aging \
  --location europe-west1 \
  --schedule "0 9 * * 1-5" \
  --time-zone "Europe/Istanbul" \
  --uri "https://YOUR_CLOUD_RUN_URL/cron/daily-aging" \
  --http-method POST \
  --headers "Authorization=Bearer $CRON_SECRET" \
  --attempt-deadline 60s
```

4. **Test manually:**

```bash
# Trigger weekly report immediately
gcloud scheduler jobs run mustafa-weekly-report --location europe-west1

# Trigger daily aging immediately
gcloud scheduler jobs run mustafa-daily-aging --location europe-west1
```

Replace `YOUR_CLOUD_RUN_URL` with the actual Cloud Run service URL and `C_YOUR_CHANNEL_ID` with the Slack channel ID for `#technical-operations`.

## Architecture

See [yika-ops-bot-spec.md](yika-ops-bot-spec.md) for the full specification.
