"""Tests for prompt template retrieval and building."""

import pytest
from app.services.default_prompts import get_prompt, get_prompt_keys, DEFAULT_PROMPTS


class TestGetPrompt:
    """Tests for prompt retrieval with fallback logic."""

    def test_english_brainstorming_system(self):
        result = get_prompt("brainstorming_system", language="en")
        assert result != ""
        assert "6-3-5" in result

    def test_german_brainstorming_system(self):
        result = get_prompt("brainstorming_system", language="de")
        assert result != ""

    def test_english_consultation_system(self):
        result = get_prompt("consultation_system", language="en")
        assert result != ""

    def test_custom_prompt_overrides_default(self):
        custom = {"brainstorming_system": "My custom prompt"}
        result = get_prompt("brainstorming_system", language="en", custom_prompts=custom)
        assert result == "My custom prompt"

    def test_empty_custom_prompt_falls_back(self):
        custom = {"brainstorming_system": ""}
        result = get_prompt("brainstorming_system", language="en", custom_prompts=custom)
        assert result != ""
        assert "6-3-5" in result

    def test_unknown_key_returns_empty(self):
        result = get_prompt("nonexistent_prompt", language="en")
        assert result == ""

    def test_unknown_language_falls_back_to_english(self):
        result = get_prompt("brainstorming_system", language="fr")
        en_result = get_prompt("brainstorming_system", language="en")
        assert result == en_result

    def test_none_custom_prompts(self):
        result = get_prompt("brainstorming_system", language="en", custom_prompts=None)
        assert result != ""


class TestPromptKeys:
    """Tests for prompt key completeness."""

    def test_all_keys_exist_in_english(self):
        for key in get_prompt_keys():
            prompt = get_prompt(key, language="en")
            assert prompt != "", f"Missing English prompt for key: {key}"

    def test_all_keys_exist_in_german(self):
        for key in get_prompt_keys():
            prompt = get_prompt(key, language="de")
            assert prompt != "", f"Missing German prompt for key: {key}"

    def test_expected_keys_present(self):
        keys = get_prompt_keys()
        expected = [
            "brainstorming_system",
            "brainstorming_round1",
            "brainstorming_subsequent",
            "consultation_system",
            "consultation_context",
            "extraction_summary",
            "business_case_system",
            "business_case_extraction",
            "cost_estimation_system",
            "cost_estimation_extraction",
        ]
        for key in expected:
            assert key in keys, f"Expected key '{key}' not in prompt keys"


class TestPromptFormatVariables:
    """Tests that prompt templates contain expected format placeholders."""

    def test_brainstorming_system_has_company_context(self):
        prompt = get_prompt("brainstorming_system", language="en")
        assert "{company_context}" in prompt

    def test_brainstorming_round1_has_round_number(self):
        prompt = get_prompt("brainstorming_round1", language="en")
        assert "{round_number}" in prompt

    def test_brainstorming_subsequent_has_previous_ideas(self):
        prompt = get_prompt("brainstorming_subsequent", language="en")
        assert "{previous_ideas_numbered}" in prompt
        assert "{round_number}" in prompt
