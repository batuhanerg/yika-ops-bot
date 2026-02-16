"""Claude API integration — parses user messages into structured JSON."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import anthropic

from app.models.operations import ParseResult
from app.utils.validators import validate_date_not_future, validate_date_not_too_old

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def build_sites_context(sites: list[dict]) -> str:
    """Build a compact sites reference string for Claude's system prompt.

    Returns a newline-separated list of "Site ID | Customer Name" entries,
    preceded by an instruction header.  Returns "" if sites is empty.
    """
    lines = []
    for s in sites:
        sid = s.get("Site ID", "").strip()
        if not sid:
            continue
        customer = s.get("Customer", "").strip()
        lines.append(f"{sid} | {customer}")
    if not lines:
        return ""
    header = (
        "## Existing Sites\n\n"
        "The following sites already exist. When the user references a customer "
        "or site by name, match it against this list. If it matches an existing "
        "site, use `update_site` — never `create_site` for an existing customer.\n\n"
        "Site ID | Customer\n"
        "---|---"
    )
    return header + "\n" + "\n".join(lines)


class ClaudeService:
    """Parses user messages via Claude Haiku into structured ParseResult."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=key)
        # Cache the static parts of the prompt (everything except today's date)
        self._static_prompt = "\n".join([
            _load_prompt("system_prompt.md"),
            "\n---\n",
            _load_prompt("vocabulary.md"),
            "\n---\n",
            _load_prompt("team_context.md"),
        ])

    def _build_system_prompt(self, sites_context: str = "") -> str:
        parts = [self._static_prompt]
        if sites_context:
            parts.append(f"\n---\n{sites_context}")
        parts.append(f"\n---\nToday's date: {date.today().isoformat()}")
        return "".join(parts)

    def parse_message(
        self,
        message: str,
        sender_name: str,
        thread_context: list[dict] | None = None,
        sites_context: str = "",
    ) -> ParseResult:
        """Parse a user message and return structured data."""
        user_content = f"[Sender: {sender_name}]\n{message}"

        messages = []
        if thread_context:
            for ctx in thread_context:
                messages.append({"role": ctx["role"], "content": ctx["content"]})
        messages.append({"role": "user", "content": user_content})

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=self._build_system_prompt(sites_context=sites_context),
            messages=messages,
        )

        raw_text = response.content[0].text.strip()
        return self._parse_response(raw_text, sender_name)

    def _parse_response(self, raw_text: str, sender_name: str) -> ParseResult:
        """Parse Claude's JSON response into a ParseResult, applying validations."""
        # Extract JSON from response (handle markdown code fences)
        json_str = raw_text
        if "```" in json_str:
            # Extract content between code fences
            parts = json_str.split("```")
            for part in parts[1:]:
                # Skip the language identifier line if present
                lines = part.strip().split("\n")
                if lines[0].strip().lower() in ("json", ""):
                    lines = lines[1:]
                candidate = "\n".join(lines).strip()
                if candidate.startswith("{"):
                    json_str = candidate
                    break

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            return ParseResult(
                operation="error",
                data={"_raw": raw_text[:200]},
                error="json_parse_failure",
            )

        operation = parsed.get("operation", "unknown")

        # Handle clarify operation
        if operation == "clarify":
            return ParseResult(
                operation="clarify",
                data={"message": parsed.get("message", "")},
                language=parsed.get("language", "tr"),
            )

        # Handle error operation from Claude
        if operation == "error":
            return ParseResult(
                operation="error",
                data={"message": parsed.get("message", "")},
                error=parsed.get("message", "unknown_error"),
                language=parsed.get("language", "tr"),
            )
        data = parsed.get("data", {})
        missing_fields = parsed.get("missing_fields", [])
        error = parsed.get("error")
        language = parsed.get("language", "tr")
        warnings: list[str] = parsed.get("warnings") or []
        extra_operations = parsed.get("extra_operations")

        # If Claude already flagged a future date error, preserve it
        if error == "future_date" or data.get("_future_date_warning"):
            error = "future_date"
            data["_future_date_warning"] = True

        # Post-processing: validate dates
        received_date_str = data.get("received_date")
        if received_date_str and operation in ("log_support", "update_support"):
            try:
                received_date = date.fromisoformat(received_date_str)

                # Future date check
                future_check = validate_date_not_future(received_date)
                if not future_check.valid:
                    error = "future_date"
                    data["_future_date_warning"] = True

                # Old date check
                old_check = validate_date_not_too_old(received_date)
                if old_check.warning:
                    warnings.append("old_date")
            except ValueError:
                pass

        return ParseResult(
            operation=operation,
            data=data,
            missing_fields=missing_fields,
            error=error,
            warnings=warnings if warnings else None,
            language=language,
            extra_operations=extra_operations if extra_operations else None,
        )
