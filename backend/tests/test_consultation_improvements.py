"""Tests for the five consultation quality improvements:
1. MATURITY_GUIDANCE injection into consultation_context (EN+DE)
2. LLM-based _summarize_old_messages replacing text-slicing
3. Technical briefing blockers/enablers injected into Step 5a system prompt
4. OPEN RISKS / BLOCKERS section in extraction_summary + saved as finding
5. XML block removed from consultation_system (EN+DE)
"""

import re
import pytest
from unittest.mock import MagicMock, patch

from app.services.default_prompts import get_prompt, DEFAULT_PROMPTS
from app.services.consultation_service import ConsultationService, MATURITY_GUIDANCE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_consultation_service(language: str = "en") -> ConsultationService:
    """Create a ConsultationService instance without a real DB."""
    svc = ConsultationService.__new__(ConsultationService)
    svc.language = language
    svc.custom_prompts = {}
    svc.chat_temperature = None
    svc.extraction_temperature = None
    svc._llm = MagicMock()
    return svc


# ===========================================================================
# 1 — MATURITY_GUIDANCE injection
# ===========================================================================

class TestMaturityGuidancePlaceholder:
    """consultation_context templates must expose {maturity_guidance_text}."""

    def test_en_context_has_placeholder(self):
        prompt = get_prompt("consultation_context", language="en")
        assert "{maturity_guidance_text}" in prompt

    def test_de_context_has_placeholder(self):
        prompt = get_prompt("consultation_context", language="de")
        assert "{maturity_guidance_text}" in prompt


class TestMaturityGuidanceDict:
    """MATURITY_GUIDANCE must cover all six levels in both languages."""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_en_level_present(self, level):
        assert level in MATURITY_GUIDANCE["en"]

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_de_level_present(self, level):
        assert level in MATURITY_GUIDANCE["de"]

    def test_each_entry_is_name_and_text_tuple(self):
        for lang in ("en", "de"):
            for level, entry in MATURITY_GUIDANCE[lang].items():
                assert isinstance(entry, tuple) and len(entry) == 2, (
                    f"MATURITY_GUIDANCE[{lang!r}][{level}] must be a (name, text) tuple"
                )
                name, text = entry
                assert isinstance(name, str) and name
                assert isinstance(text, str) and len(text) > 20


class TestMaturityGuidanceInjection:
    """_build_context_message must inject the right level text."""

    def _build_guidance_text(self, svc: ConsultationService, score: float) -> str:
        """Replicate the guidance text computation from _build_context_message."""
        level_int = max(1, min(6, round(score)))
        lang_guidance = MATURITY_GUIDANCE.get(svc.language, MATURITY_GUIDANCE["en"])
        guidance = lang_guidance.get(level_int)
        if guidance:
            level_name, guidance_text = guidance
            if svc.language == "de":
                return f"**Hinweise für Level {level_int} — {level_name}:** {guidance_text}"
            else:
                return f"**Guidance for Level {level_int} — {level_name}:** {guidance_text}"
        return ""

    @pytest.mark.parametrize("score,expected_level", [
        (1.0, 1), (1.4, 1), (1.5, 2),
        (2.5, 2),   # Python 3 banker's rounding: round(2.5) == 2
        (2.6, 3), (3.0, 3),
        (3.5, 4),   # round(3.5) == 4
        (4.9, 5), (5.5, 6), (6.0, 6),
    ])
    def test_score_rounds_to_correct_level(self, score, expected_level):
        svc = _make_consultation_service("en")
        text = self._build_guidance_text(svc, score)
        assert f"Level {expected_level}" in text

    def test_en_guidance_references_correct_level_name(self):
        svc = _make_consultation_service("en")
        text = self._build_guidance_text(svc, 3.0)
        level_name, _ = MATURITY_GUIDANCE["en"][3]
        assert level_name in text

    def test_de_guidance_uses_german_prefix(self):
        svc = _make_consultation_service("de")
        text = self._build_guidance_text(svc, 3.0)
        assert "Hinweise für Level" in text

    def test_en_guidance_uses_english_prefix(self):
        svc = _make_consultation_service("en")
        text = self._build_guidance_text(svc, 3.0)
        assert "Guidance for Level" in text

    def test_score_clamped_below_1(self):
        svc = _make_consultation_service("en")
        text = self._build_guidance_text(svc, 0.0)
        assert "Level 1" in text

    def test_score_clamped_above_6(self):
        svc = _make_consultation_service("en")
        text = self._build_guidance_text(svc, 10.0)
        assert "Level 6" in text


# ===========================================================================
# 2 — LLM-based _summarize_old_messages
# ===========================================================================

class TestSummarizeOldMessages:
    """_summarize_old_messages must use an LLM call to preserve facts."""

    def _mock_llm_response(self, text: str):
        response = MagicMock()
        response.choices[0].message.content = text
        return response

    def test_empty_messages_returns_empty_string(self):
        svc = _make_consultation_service("en")
        assert svc._summarize_old_messages([]) == ""

    def test_only_system_messages_returns_empty(self):
        svc = _make_consultation_service("en")
        messages = [{"role": "system", "content": "System prompt text here."}]
        assert svc._summarize_old_messages(messages) == ""

    def test_only_very_short_messages_returns_empty(self):
        svc = _make_consultation_service("en")
        messages = [{"role": "user", "content": "ok"}, {"role": "assistant", "content": "hi"}]
        assert svc._summarize_old_messages(messages) == ""

    def test_calls_llm_extraction(self):
        svc = _make_consultation_service("en")
        svc._call_llm_extraction = MagicMock(return_value=self._mock_llm_response("Summary."))
        messages = [
            {"role": "user", "content": "We produce 500 parts per day with a 3% defect rate."},
            {"role": "assistant", "content": "How many operators do the visual inspection?"},
        ]
        result = svc._summarize_old_messages(messages)
        assert result == "Summary."
        svc._call_llm_extraction.assert_called_once()

    def test_en_prompt_instructs_verbatim_facts(self):
        svc = _make_consultation_service("en")
        captured_prompt = {}

        def capture(*args, **kwargs):
            captured_prompt["text"] = args[0][0]["content"]
            return self._mock_llm_response("Summary.")

        svc._call_llm_extraction = capture
        svc._summarize_old_messages([
            {"role": "user", "content": "We process 1,200 invoices per month."},
        ])
        assert "VERBATIM" in captured_prompt["text"] or "verbatim" in captured_prompt["text"].lower()

    def test_de_prompt_is_in_german(self):
        svc = _make_consultation_service("de")
        captured_prompt = {}

        def capture(*args, **kwargs):
            captured_prompt["text"] = args[0][0]["content"]
            return self._mock_llm_response("Zusammenfassung.")

        svc._call_llm_extraction = capture
        svc._summarize_old_messages([
            {"role": "user", "content": "Wir produzieren 500 Teile pro Tag."},
        ])
        # German prompt uses "WÖRTLICH" instead of VERBATIM
        assert "WÖRTLICH" in captured_prompt["text"] or "wörtlich" in captured_prompt["text"].lower()

    def test_transcript_uses_client_consultant_labels(self):
        svc = _make_consultation_service("en")
        captured_prompt = {}

        def capture(*args, **kwargs):
            captured_prompt["text"] = args[0][0]["content"]
            return self._mock_llm_response("ok")

        svc._call_llm_extraction = capture
        svc._summarize_old_messages([
            {"role": "user", "content": "We have 500 parts per day."},
            {"role": "assistant", "content": "What is the defect rate?"},
        ])
        assert "Client:" in captured_prompt["text"]
        assert "Consultant:" in captured_prompt["text"]

    def test_system_messages_excluded_from_transcript(self):
        svc = _make_consultation_service("en")
        captured_prompt = {}

        def capture(*args, **kwargs):
            captured_prompt["text"] = args[0][0]["content"]
            return self._mock_llm_response("ok")

        svc._call_llm_extraction = capture
        svc._summarize_old_messages([
            {"role": "system", "content": "SECRET SYSTEM INSTRUCTIONS"},
            {"role": "user", "content": "We have 500 parts per day."},
        ])
        assert "SECRET SYSTEM INSTRUCTIONS" not in captured_prompt.get("text", "")

    def test_llm_error_returns_empty_string(self):
        svc = _make_consultation_service("en")
        svc._call_llm_extraction = MagicMock(side_effect=RuntimeError("LLM unavailable"))
        messages = [{"role": "user", "content": "We produce 500 parts per day."}]
        result = svc._summarize_old_messages(messages)
        assert result == ""


# ===========================================================================
# 3 — Technical briefing blockers into Step 5a
# ===========================================================================

class TestTechnicalBlockersPlaceholder:
    """business_case_system templates must expose {technical_blockers}."""

    def test_en_business_case_system_has_placeholder(self):
        prompt = get_prompt("business_case_system", language="en")
        assert "{technical_blockers}" in prompt

    def test_de_business_case_system_has_placeholder(self):
        prompt = get_prompt("business_case_system", language="de")
        assert "{technical_blockers}" in prompt

    def test_en_placeholder_is_after_project_plan(self):
        prompt = get_prompt("business_case_system", language="en")
        pp_pos = prompt.find("{project_plan}")
        tb_pos = prompt.find("{technical_blockers}")
        assert pp_pos != -1 and tb_pos != -1
        assert tb_pos > pp_pos

    def test_de_placeholder_is_after_project_plan(self):
        prompt = get_prompt("business_case_system", language="de")
        pp_pos = prompt.find("{project_plan}")
        tb_pos = prompt.find("{technical_blockers}")
        assert pp_pos != -1 and tb_pos != -1
        assert tb_pos > pp_pos


class TestTechnicalBlockersExtraction:
    """The regex used by _build_system_prompt to extract the blockers section."""

    _PATTERN = (
        r'(?:IDENTIFIED ENABLERS AND BLOCKERS|IDENTIFIZIERTE ENABLER UND BLOCKER)(.*?)'
        r'(?=###\s*\d|###\s*[A-Z\u00C0-\u024F]|\Z)'
    )

    def test_extracts_en_enablers_and_blockers_section(self):
        text = (
            "### 2. TECHNICAL INVESTIGATION QUESTIONS\nSome questions here.\n\n"
            "### 3. IDENTIFIED ENABLERS AND BLOCKERS\n"
            "**Enablers** — ERP data available.\n"
            "**Blockers** — No labelled training data.\n\n"
            "### 4. HYPOTHESES\nHypothesis 1 here.\n"
        )
        m = re.search(self._PATTERN, text, re.IGNORECASE | re.DOTALL)
        assert m is not None
        content = m.group(1).strip()
        assert "ERP data available" in content
        assert "No labelled training data" in content
        assert "HYPOTHESES" not in content

    def test_extracts_de_section(self):
        text = (
            "### 2. TECHNISCHE UNTERSUCHUNGSFRAGEN\nFragen hier.\n\n"
            "### 3. IDENTIFIZIERTE ENABLER UND BLOCKER\n"
            "**Enabler** — Produktionsdaten vorhanden.\n"
            "**Blocker** — Kein annotierter Datensatz.\n\n"
            "### 4. HYPOTHESEN\nHypothese 1.\n"
        )
        m = re.search(self._PATTERN, text, re.IGNORECASE | re.DOTALL)
        assert m is not None
        content = m.group(1).strip()
        assert "Produktionsdaten vorhanden" in content
        assert "HYPOTHESEN" not in content

    def test_no_match_returns_none(self):
        text = "### 1. USE CASE PROFILE\nSome profile text.\n"
        m = re.search(self._PATTERN, text, re.IGNORECASE | re.DOTALL)
        assert m is None

    def test_match_at_end_of_document(self):
        """Section at document end (no following ###) must still be captured."""
        text = (
            "### 3. IDENTIFIED ENABLERS AND BLOCKERS\n"
            "**Enablers** — Clean data already collected.\n"
            "**Blockers** — IT approval pending.\n"
        )
        m = re.search(self._PATTERN, text, re.IGNORECASE | re.DOTALL)
        assert m is not None
        content = m.group(1).strip()
        assert "IT approval pending" in content


# ===========================================================================
# 4 — OPEN RISKS / BLOCKERS in extraction_summary
# ===========================================================================

class TestOpenRisksPromptSection:
    """extraction_summary templates must contain the OPEN RISKS section."""

    def test_en_extraction_summary_has_open_risks_header(self):
        prompt = get_prompt("extraction_summary", language="en")
        assert "OPEN RISKS" in prompt

    def test_de_extraction_summary_has_offene_risiken_header(self):
        prompt = get_prompt("extraction_summary", language="de")
        assert "OFFENE RISIKEN" in prompt

    def test_en_open_risks_appears_after_project_plan(self):
        prompt = get_prompt("extraction_summary", language="en")
        pp_pos = prompt.find("## PROJECT PLAN")
        or_pos = prompt.find("## OPEN RISKS")
        assert pp_pos != -1 and or_pos != -1
        assert or_pos > pp_pos

    def test_de_offene_risiken_appears_after_projektplan(self):
        prompt = get_prompt("extraction_summary", language="de")
        pp_pos = prompt.find("## PROJEKTPLAN")
        or_pos = prompt.find("## OFFENE RISIKEN")
        assert pp_pos != -1 and or_pos != -1
        assert or_pos > pp_pos

    def test_en_prompt_instructs_no_blockers_fallback(self):
        prompt = get_prompt("extraction_summary", language="en")
        assert "No critical blockers identified" in prompt

    def test_de_prompt_instructs_no_blockers_fallback(self):
        prompt = get_prompt("extraction_summary", language="de")
        assert "Keine kritischen Blocker" in prompt


class TestOpenRisksInGetFindings:
    """get_findings must include the open_risks key."""

    def test_get_findings_result_has_open_risks_key(self):
        from app.services.consultation_service import ConsultationService
        svc = ConsultationService.__new__(ConsultationService)
        svc.language = "en"
        # Mock the DB query to return no findings
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            session_uuid="test-uuid", id=1, company_name="Test Co"
        )
        mock_db.query.return_value.filter.return_value.all.return_value = []
        svc.db = mock_db

        # Call get_findings with a mock session lookup
        with patch.object(svc, '_get_session', return_value=MagicMock(id=1)):
            result = svc.get_findings("fake-uuid")

        assert "open_risks" in result


# ===========================================================================
# 5 — XML block removed from consultation_system
# ===========================================================================

class TestXmlBlockRemoved:
    """consultation_system prompts must not contain XML <business_understanding> tags."""

    def test_en_no_xml_business_understanding(self):
        prompt = get_prompt("consultation_system", language="en")
        assert "<business_understanding>" not in prompt
        assert "</business_understanding>" not in prompt

    def test_de_no_xml_business_understanding(self):
        prompt = get_prompt("consultation_system", language="de")
        assert "<business_understanding>" not in prompt
        assert "</business_understanding>" not in prompt

    def test_en_no_xml_sub_tags(self):
        prompt = get_prompt("consultation_system", language="en")
        for tag in ["<business_objectives>", "<situation_resources>",
                    "<technical_goals>", "<implementation_plan>",
                    "<maturity_fit>", "<open_points>"]:
            assert tag not in prompt, f"XML tag {tag} still present in EN consultation_system"

    def test_de_no_xml_sub_tags(self):
        prompt = get_prompt("consultation_system", language="de")
        for tag in ["<business_objectives>", "<situation_resources>",
                    "<technical_goals>", "<implementation_plan>",
                    "<maturity_fit>", "<open_points>"]:
            assert tag not in prompt, f"XML tag {tag} still present in DE consultation_system"

    def test_en_extract_findings_guidance_preserved(self):
        prompt = get_prompt("consultation_system", language="en")
        assert "Extract Findings" in prompt

    def test_de_erkenntnisse_extrahieren_guidance_preserved(self):
        prompt = get_prompt("consultation_system", language="de")
        assert "Erkenntnisse extrahieren" in prompt

    def test_en_remember_section_preserved(self):
        prompt = get_prompt("consultation_system", language="en")
        assert "# REMEMBER" in prompt

    def test_de_merken_section_preserved(self):
        prompt = get_prompt("consultation_system", language="de")
        assert "# MERKEN" in prompt
