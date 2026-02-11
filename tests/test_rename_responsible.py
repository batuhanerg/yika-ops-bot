"""Tests for the Technician → Responsible rename (Item 2, Session 4).

Validates that the rename is complete: models, sheets, formatters, prompts, and migration script.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestModelRename:
    """Verify the field is 'responsible' in models and required fields."""

    def test_required_fields_uses_responsible(self):
        from app.models.operations import REQUIRED_FIELDS
        assert "responsible" in REQUIRED_FIELDS["log_support"]
        assert "technician" not in REQUIRED_FIELDS["log_support"]

    def test_support_key_map_uses_responsible(self):
        from app.services.sheets import _SUPPORT_KEY_MAP
        assert "responsible" in _SUPPORT_KEY_MAP
        assert "technician" not in _SUPPORT_KEY_MAP
        assert _SUPPORT_KEY_MAP["responsible"] == "Responsible"

    def test_support_log_columns_uses_responsible(self):
        from app.services.sheets import SUPPORT_LOG_COLUMNS
        assert "Responsible" in SUPPORT_LOG_COLUMNS
        assert "Technician" not in SUPPORT_LOG_COLUMNS

    def test_field_labels_uses_responsible(self):
        from app.utils.formatters import FIELD_LABELS
        assert "responsible" in FIELD_LABELS
        assert "technician" not in FIELD_LABELS


class TestMigrationScript:
    """Test the column header migration script."""

    def test_migrate_renames_technician_header(self):
        from scripts.migrate_technician_to_responsible import migrate

        mock_ws = MagicMock()
        mock_ws.row_values.return_value = [
            "Ticket ID", "Site ID", "Received Date", "Resolved Date",
            "Type", "Status", "Root Cause", "Reported By",
            "Issue Summary", "Resolution", "Devices Affected",
            "Technician", "Notes",
        ]

        migrate(mock_ws)

        # Should update cell at row 1, column 12 (Technician is index 11, 1-based = 12)
        mock_ws.update_cell.assert_called_once_with(1, 12, "Responsible")

    def test_migrate_noop_if_already_renamed(self):
        from scripts.migrate_technician_to_responsible import migrate

        mock_ws = MagicMock()
        mock_ws.row_values.return_value = [
            "Ticket ID", "Site ID", "Received Date", "Resolved Date",
            "Type", "Status", "Root Cause", "Reported By",
            "Issue Summary", "Resolution", "Devices Affected",
            "Responsible", "Notes",
        ]

        migrate(mock_ws)

        mock_ws.update_cell.assert_not_called()


class TestPromptRename:
    """Verify prompt files reference 'responsible' not 'technician'."""

    def test_system_prompt_uses_responsible(self):
        import os
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "prompts", "system_prompt.md"
        )
        content = open(prompt_path).read()
        # Should use "Responsible" as the field name
        assert "responsible" in content.lower()
        # Should NOT reference "technician" as a field name
        # (contextual references like "field technician" role are OK)
        assert "### Technician" not in content

    def test_team_context_uses_responsible(self):
        import os
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "prompts", "team_context.md"
        )
        content = open(prompt_path).read()
        assert "Responsible" in content
