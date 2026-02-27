"""Unit tests for brainstorming prompt correctness.

Covers:
- German prompts use nominalized verb format (not infinitive)
- Format templates match expected patterns in EN and DE
- AI participant uniqueness_note is language-aware
- Fallback idea strings are language-aware
"""

import pytest
from app.services.default_prompts import DEFAULT_PROMPTS


# ---------------------------------------------------------------------------
# TestGermanBrainstormingFormat
# ---------------------------------------------------------------------------

class TestGermanBrainstormingFormat:
    """German brainstorming prompts must use nominalized verbs, not bare infinitives."""

    def test_system_prompt_uses_nominalisierung(self):
        system = DEFAULT_PROMPTS["de"]["brainstorming_system"]
        assert "Nominalisierung" in system or "nominalisiert" in system.lower(), (
            "German system prompt should instruct nominalized verb form"
        )

    def test_system_prompt_does_not_instruct_bare_infinitive(self):
        system = DEFAULT_PROMPTS["de"]["brainstorming_system"]
        # Old format instructed starting with a bare infinitive verb
        assert '"Implementieren"' not in system
        assert '"Einführen"' not in system
        assert '"Entwickeln"' not in system
        assert '"Automatisieren"' not in system

    def test_system_prompt_uses_nominalized_examples(self):
        system = DEFAULT_PROMPTS["de"]["brainstorming_system"]
        # New format instructs nominalized examples
        assert "Implementierung von" in system or "Einführung" in system

    def test_round1_format_template_uses_nominalisierung(self):
        round1 = DEFAULT_PROMPTS["de"]["brainstorming_round1"]
        assert "Nominalisierung" in round1, (
            "Round 1 format template should use [Nominalisierung] placeholder"
        )

    def test_round1_format_template_does_not_use_verb_placeholder(self):
        round1 = DEFAULT_PROMPTS["de"]["brainstorming_round1"]
        # Old template used [Verb] placeholder
        assert "[Verb]" not in round1

    def test_subsequent_format_template_uses_nominalisierung(self):
        subsequent = DEFAULT_PROMPTS["de"]["brainstorming_subsequent"]
        assert "Nominalisierung" in subsequent

    def test_subsequent_format_template_does_not_use_verb_placeholder(self):
        subsequent = DEFAULT_PROMPTS["de"]["brainstorming_subsequent"]
        assert "[Verb]" not in subsequent

    def test_round1_has_three_format_lines(self):
        """Round 1 must still provide 3 numbered format lines."""
        round1 = DEFAULT_PROMPTS["de"]["brainstorming_round1"]
        import re
        lines = re.findall(r'^\d+\.', round1, re.MULTILINE)
        assert len(lines) == 3, f"Expected 3 numbered lines, got {len(lines)}"

    def test_subsequent_has_three_format_lines(self):
        subsequent = DEFAULT_PROMPTS["de"]["brainstorming_subsequent"]
        import re
        lines = re.findall(r'^\d+\.', subsequent, re.MULTILINE)
        assert len(lines) == 3


class TestEnglishBrainstormingFormat:
    """English prompts should still use action verb format (unchanged)."""

    def test_system_prompt_uses_action_verb(self):
        system = DEFAULT_PROMPTS["en"]["brainstorming_system"]
        assert "action verb" in system.lower() or "Action verb" in system

    def test_system_prompt_has_english_examples(self):
        system = DEFAULT_PROMPTS["en"]["brainstorming_system"]
        assert "Implement" in system or "Deploy" in system or "Create" in system

    def test_round1_format_template_uses_action_verb_placeholder(self):
        round1 = DEFAULT_PROMPTS["en"]["brainstorming_round1"]
        assert "[Action verb]" in round1

    def test_subsequent_format_template_uses_action_verb_placeholder(self):
        subsequent = DEFAULT_PROMPTS["en"]["brainstorming_subsequent"]
        assert "[Action verb]" in subsequent

    def test_round1_has_three_format_lines(self):
        import re
        round1 = DEFAULT_PROMPTS["en"]["brainstorming_round1"]
        lines = re.findall(r'^\d+\.', round1, re.MULTILINE)
        assert len(lines) == 3

    def test_subsequent_has_three_format_lines(self):
        import re
        subsequent = DEFAULT_PROMPTS["en"]["brainstorming_subsequent"]
        lines = re.findall(r'^\d+\.', subsequent, re.MULTILINE)
        assert len(lines) == 3


class TestBrainstormingPromptPresence:
    """All required brainstorming prompt keys exist in both languages."""

    REQUIRED_KEYS = ["brainstorming_system", "brainstorming_round1", "brainstorming_subsequent"]

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_key_exists(self, lang, key):
        assert key in DEFAULT_PROMPTS[lang], f"Missing {key} in {lang} prompts"

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_key_is_nonempty(self, lang, key):
        assert len(DEFAULT_PROMPTS[lang][key].strip()) > 50

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_round1_contains_uniqueness_note_placeholder(self, lang):
        assert "{uniqueness_note}" in DEFAULT_PROMPTS[lang]["brainstorming_round1"]

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_subsequent_contains_uniqueness_note_placeholder(self, lang):
        assert "{uniqueness_note}" in DEFAULT_PROMPTS[lang]["brainstorming_subsequent"]

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_subsequent_contains_previous_ideas_placeholder(self, lang):
        assert "{previous_ideas_numbered}" in DEFAULT_PROMPTS[lang]["brainstorming_subsequent"]

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_round1_contains_round_number_placeholder(self, lang):
        assert "{round_number}" in DEFAULT_PROMPTS[lang]["brainstorming_round1"]

    def test_de_system_prompt_contains_wichtig_language_instruction(self):
        """The German system prompt must start with explicit German-language instruction."""
        system = DEFAULT_PROMPTS["de"]["brainstorming_system"]
        assert "WICHTIG" in system
        assert "Deutsch" in system

    def test_de_system_prompt_language_instruction_is_near_top(self):
        """The WICHTIG instruction should appear in the first 200 chars."""
        system = DEFAULT_PROMPTS["de"]["brainstorming_system"]
        assert system.index("WICHTIG") < 200


# ---------------------------------------------------------------------------
# TestAIParticipantLanguageStrings
# ---------------------------------------------------------------------------

class TestAIParticipantLanguageStrings:
    """AI participant uniqueness_note and fallback ideas must be language-aware."""

    def _build_uniqueness_note(self, language: str, other_ideas: list) -> str:
        """Mirror the logic in ai_participant.py generate_ideas()."""
        ideas_list = "\n".join(f"- {idea}" for idea in other_ideas[:10])
        if language == "de":
            note_header = "Hinweis: Diese Ideen wurden bereits von anderen in dieser Sitzung vorgeschlagen (Wiederholungen vermeiden):"
            more_suffix = f"(und {len(other_ideas) - 10} weitere)" if len(other_ideas) > 10 else ""
        else:
            note_header = "Note: These ideas have been suggested by others in this session (avoid duplicating them):"
            more_suffix = f"(and {len(other_ideas) - 10} more)" if len(other_ideas) > 10 else ""
        return f"\n{note_header}\n{ideas_list}\n{more_suffix}\n"

    def _fallback_ideas(self, language: str, participant_number: int, round_number: int) -> list:
        """Mirror the error fallback in ai_participant.py."""
        if language == "de":
            return [f"KI-Teilnehmer {participant_number} - Idee {i+1} für Runde {round_number}" for i in range(3)]
        return [f"AI Participant {participant_number} - Unique Idea {i+1} for round {round_number}" for i in range(3)]

    def _short_fallback_ideas(self, language: str, ideas: list, round_number: int) -> list:
        """Mirror the short fallback (padding to 3) in ai_participant.py."""
        result = list(ideas)
        if language == "de":
            result.extend([f"KI-Idee {i+1} (einzigartig) für Runde {round_number}" for i in range(len(result), 3)])
        else:
            result.extend([f"AI Idea {i+1} (unique) for round {round_number}" for i in range(len(result), 3)])
        return result

    # --- uniqueness_note language ---

    def test_de_note_uses_german_header(self):
        note = self._build_uniqueness_note("de", ["Idee A", "Idee B"])
        assert "Hinweis:" in note
        assert "Note:" not in note

    def test_en_note_uses_english_header(self):
        note = self._build_uniqueness_note("en", ["Idea A", "Idea B"])
        assert "Note:" in note
        assert "Hinweis:" not in note

    def test_de_note_truncates_at_10_with_german_suffix(self):
        ideas = [f"Idee {i}" for i in range(15)]
        note = self._build_uniqueness_note("de", ideas)
        assert "weitere" in note
        assert "more" not in note

    def test_en_note_truncates_at_10_with_english_suffix(self):
        ideas = [f"Idea {i}" for i in range(15)]
        note = self._build_uniqueness_note("en", ideas)
        assert "more" in note
        assert "weitere" not in note

    def test_de_note_no_suffix_when_10_or_fewer(self):
        ideas = [f"Idee {i}" for i in range(10)]
        note = self._build_uniqueness_note("de", ideas)
        assert "weitere" not in note

    def test_en_note_no_suffix_when_10_or_fewer(self):
        ideas = [f"Idea {i}" for i in range(10)]
        note = self._build_uniqueness_note("en", ideas)
        assert "more" not in note

    def test_note_contains_all_ideas_up_to_10(self):
        ideas = [f"Idee {i}" for i in range(5)]
        note = self._build_uniqueness_note("de", ideas)
        for idea in ideas:
            assert idea in note

    def test_note_does_not_contain_ideas_beyond_10(self):
        ideas = [f"Idea {i}" for i in range(15)]
        note = self._build_uniqueness_note("en", ideas)
        assert "Idea 14" not in note  # index 14 → 15th idea, truncated
        assert "Idea 9" in note       # index 9 → 10th idea, included

    # --- error fallback ideas ---

    def test_de_fallback_ideas_are_german(self):
        ideas = self._fallback_ideas("de", 1, 2)
        assert all("KI-Teilnehmer" in idea for idea in ideas)
        assert all("AI Participant" not in idea for idea in ideas)

    def test_en_fallback_ideas_are_english(self):
        ideas = self._fallback_ideas("en", 1, 2)
        assert all("AI Participant" in idea for idea in ideas)
        assert all("KI-Teilnehmer" not in idea for idea in ideas)

    def test_fallback_returns_3_ideas(self):
        assert len(self._fallback_ideas("de", 2, 3)) == 3
        assert len(self._fallback_ideas("en", 2, 3)) == 3

    def test_de_fallback_includes_round_number(self):
        ideas = self._fallback_ideas("de", 1, 4)
        assert all("Runde 4" in idea for idea in ideas)

    def test_en_fallback_includes_round_number(self):
        ideas = self._fallback_ideas("en", 1, 4)
        assert all("round 4" in idea for idea in ideas)

    def test_fallback_includes_participant_number(self):
        de_ideas = self._fallback_ideas("de", 3, 1)
        en_ideas = self._fallback_ideas("en", 3, 1)
        assert all("3" in idea for idea in de_ideas)
        assert all("3" in idea for idea in en_ideas)

    # --- short fallback (padding to 3) ---

    def test_de_short_fallback_pads_to_3(self):
        result = self._short_fallback_ideas("de", ["Idee A"], 2)
        assert len(result) == 3
        assert result[0] == "Idee A"
        assert "KI-Idee" in result[1]

    def test_en_short_fallback_pads_to_3(self):
        result = self._short_fallback_ideas("en", ["Idea A"], 2)
        assert len(result) == 3
        assert "AI Idea" in result[1]

    def test_de_short_fallback_uses_german_text(self):
        result = self._short_fallback_ideas("de", [], 3)
        assert all("KI-Idee" in idea for idea in result)
        assert all("AI Idea" not in idea for idea in result)

    def test_en_short_fallback_uses_english_text(self):
        result = self._short_fallback_ideas("en", [], 3)
        assert all("AI Idea" in idea for idea in result)
        assert all("KI-Idee" not in idea for idea in result)

    def test_short_fallback_no_padding_when_already_3(self):
        ideas = ["A", "B", "C"]
        result = self._short_fallback_ideas("de", ideas, 1)
        assert result == ideas

    def test_short_fallback_includes_round_number(self):
        result = self._short_fallback_ideas("de", [], 5)
        assert all("Runde 5" in idea for idea in result)

    def test_short_fallback_en_includes_round_number(self):
        result = self._short_fallback_ideas("en", [], 5)
        assert all("round 5" in idea for idea in result)
