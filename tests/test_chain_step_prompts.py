"""Tests for Item 2: Chain steps prompt for must fields.

Validates that chain step prompts show must and important fields
using friendly Turkish names from FIELD_REQUIREMENTS.
"""

import json
import pytest

from app.utils.formatters import format_chain_input_prompt


class TestChainStepHardwarePrompt:
    """Hardware chain step should show device_type and qty as must."""

    def test_hardware_step_shows_must_fields(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Hangi cihaz türü?" in text
        assert "Kaç adet?" in text

    def test_hardware_step_shows_important_fields(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        # HW/FW version are conditionally important
        assert "Donanım versiyonu" in text or "Firmware" in text or "faydalı" in text.lower()

    def test_hardware_step_has_skip_button(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Atla" in text


class TestChainStepImplementationFoodPrompt:
    """Implementation chain step for Food site should show food must fields."""

    def test_food_site_shows_food_must_fields(self):
        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Food")
        text = json.dumps(blocks, ensure_ascii=False)
        # internet_provider and ssid are must
        assert "İnternet" in text or "SSID" in text
        # Food-specific must fields
        assert "Clean hygiene" in text or "clean hygiene" in text.lower() or "hygiene" in text.lower()

    def test_food_site_shows_friendly_names(self):
        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Food")
        text = json.dumps(blocks, ensure_ascii=False)
        # Should use friendly Turkish questions, not raw field names
        assert "internet_provider" not in text
        assert "ssid" not in text.split("SSID")[0] if "SSID" in text else True


class TestChainStepImplementationHealthcarePrompt:
    """Implementation chain step for Healthcare site."""

    def test_healthcare_site_shows_tag_clean_to_red(self):
        blocks = format_chain_input_prompt(3, 3, "update_implementation", facility_type="Healthcare")
        text = json.dumps(blocks, ensure_ascii=False)
        # tag_clean_to_red_timeout is must for Healthcare
        assert "temiz" in text.lower() or "kırmızı" in text.lower() or "clean-to-red" in text.lower()


class TestChainStepSupportLogPrompt:
    """Support log chain step should show all must fields."""

    def test_support_log_shows_must_fields(self):
        blocks = format_chain_input_prompt(4, 4, "log_support")
        text = json.dumps(blocks, ensure_ascii=False)
        # Must fields: site_id, received_date, type, status, issue_summary, responsible
        assert "kim ilgileniyor" in text  # responsible friendly name
        assert "ne zaman" in text.lower() or "tarih" in text.lower()  # received_date


class TestChainStepStructure:
    """Verify the prompt has correct structure."""

    def test_prompt_has_step_indicator(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "Adım 2/3" in text

    def test_prompt_has_must_header(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "gerekli" in text.lower()

    def test_prompt_has_write_or_skip_instruction(self):
        blocks = format_chain_input_prompt(2, 3, "update_hardware")
        text = json.dumps(blocks, ensure_ascii=False)
        assert "yazın" in text.lower() or "atlayın" in text.lower()
