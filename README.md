# Mustafa — ERG Controls Ops Bot

A Slack bot for ERG Controls that manages IoT customer support operations through natural conversation in Turkish/English. Parses team messages, extracts structured data, and writes to a centralized Google Sheet.

## Status

**Session 1: Core Engine** — Complete (58 tests passing)

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
pytest
```

## What's Working (Session 1)

- **Message parsing** via Claude Haiku 4.5 — Turkish and English natural language to structured JSON
- **9 operation types** recognized: log_support, create_site, update_support, update_site, update_hardware, update_implementation, update_stock, query, help
- **Validators** — Site ID format, future date rejection, old date warnings, resolved-after-received, required fields, dropdown values, positive integers
- **Site resolver** — exact match, abbreviations, aliases, fuzzy matching via `thefuzz`
- **Slack Block Kit formatters** — confirmation messages with buttons, query responses, error messages, Turkish help guide
- **System prompt** with vocabulary and team context for accurate Turkish/English parsing

## Project Structure

```
app/
├── config.py               — Environment configuration
├── models/operations.py    — Pydantic models, enums, required field definitions
├── services/
│   ├── claude.py           — Claude API integration + prompt building
│   └── site_resolver.py    — Customer name → Site ID resolution (fuzzy)
├── prompts/
│   ├── system_prompt.md    — Main Claude system prompt
│   ├── vocabulary.md       — Turkish ↔ English mappings
│   └── team_context.md     — Team members, site aliases, business rules
└── utils/
    ├── validators.py       — Field validation (dates, enums, required fields)
    └── formatters.py       — Slack Block Kit message formatting

tests/
├── test_parsing.py         — Claude message parsing (10 integration tests)
├── test_validators.py      — Field validation (31 tests)
├── test_site_resolver.py   — Site name resolution (11 tests)
└── test_formatters.py      — Slack message formatting (6 tests)
```

## Test Scenarios Covered

| # | Scenario | Status |
|---|----------|--------|
| 1 | Turkish support log (resolved visit) | Pass |
| 2 | Support log with missing fields | Pass |
| 3 | False alarm → User Error root cause | Pass |
| 4 | English support log | Pass |
| 5 | First person "ben gittim" → technician = sender | Pass |
| 6 | Create site → suggested Site ID | Pass |
| 7 | Query → correct query_type | Pass |
| 8 | Bulk hardware with sub-types → 6 entries | Pass |
| 9 | Future date → rejected | Pass |
| 10 | Date > 90 days ago → warning | Pass |

## Architecture

See [yika-ops-bot-spec.md](yika-ops-bot-spec.md) for the full specification.

## Next: Session 2

Slack integration + Google Sheets read/write. See [CLAUDE.md](CLAUDE.md) for the full roadmap.
