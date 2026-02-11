# Mustafa — ERG Controls Ops Bot

A Slack bot for ERG Controls that manages IoT customer support operations through natural conversation in Turkish/English. Parses team messages, extracts structured data, and writes to a centralized Google Sheet.

## Status

**Session 4: Polish, Feedback Loop, and Data Quality** — Complete (181 tests passing)
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

## Project Structure

```
app/
├── main.py                 — Entry point, Slack Bolt app init
├── config.py               — Environment configuration
├── models/operations.py    — Pydantic models, enums, required fields
├── services/
│   ├── claude.py           — Claude API integration + prompt building
│   ├── sheets.py           — Google Sheets read/write operations
│   ├── site_resolver.py    — Customer name → Site ID resolution
│   └── data_quality.py     — Missing/stale data detection
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
    └── formatters.py       — Slack Block Kit message formatting

tests/
├── test_parsing.py         — Claude parsing (10 integration tests)
├── test_validators.py      — Field validation (31 tests)
├── test_site_resolver.py   — Site resolution (11 tests)
├── test_formatters.py      — Message formatting (6 tests)
├── test_sheets.py          — Sheets operations (16 tests, mocked)
├── test_threads.py         — Thread state (7 tests)
├── test_chain.py           — Chain wizard + normalization (20 tests)
├── test_data_quality.py    — Missing/stale data queries (19 tests)
├── test_stock_audit.py     — Stock readback + key mapping (5 tests)
├── test_audit_guardrails.py — Failed/cancelled audit logging (12 tests)
├── test_feedback.py        — Feedback loop (thumbs up/down)
├── test_rename_responsible.py — Technician→Responsible rename
└── test_help_and_readback.py  — Help text + Sheet link readback
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

## Architecture

See [yika-ops-bot-spec.md](yika-ops-bot-spec.md) for the full specification.
