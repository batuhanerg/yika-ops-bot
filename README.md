# Mustafa — ERG Controls Ops Bot

A Slack bot for ERG Controls that manages IoT customer support operations through natural conversation in Turkish/English. Parses team messages, extracts structured data, and writes to a centralized Google Sheet.

## Status

**Session 2: Sheets + Slack Integration** — Complete (81 tests passing)

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

## Project Structure

```
app/
├── main.py                 — Entry point, Slack Bolt app init
├── config.py               — Environment configuration
├── models/operations.py    — Pydantic models, enums, required fields
├── services/
│   ├── claude.py           — Claude API integration + prompt building
│   ├── sheets.py           — Google Sheets read/write operations
│   └── site_resolver.py    — Customer name → Site ID resolution
├── handlers/
│   ├── common.py           — Shared message processing pipeline
│   ├── mentions.py         — @mustafa mention handler
│   ├── messages.py         — DM message handler
│   ├── actions.py          — Confirm/cancel button handlers
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
├── test_sheets.py          — Sheets operations (14 tests, mocked)
└── test_threads.py         — Thread state (7 tests)
```

## Architecture

See [yika-ops-bot-spec.md](yika-ops-bot-spec.md) for the full specification.

## Next: Session 3

Deploy to Cloud Run + end-to-end testing. See [CLAUDE.md](CLAUDE.md) for the roadmap.
