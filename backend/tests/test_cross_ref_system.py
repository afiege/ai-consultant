"""Unit tests for the wiki-link cross-reference system.

Covers:
- cross_ref_registry: SECTION_LABELS, ALL_IDS, STEP_AVAILABLE_IDS, build_cross_ref_block
- llm.normalize_wiki_links: ID normalization (case, underscores, camelCase)
- default_prompts: injection of correct step-scoped cross-ref blocks
"""

import re
import pytest

from app.utils.cross_ref_registry import (
    SECTION_LABELS,
    ALL_IDS,
    STEP_AVAILABLE_IDS,
    build_cross_ref_block,
)
from app.utils.llm import normalize_wiki_links
from app.services.default_prompts import DEFAULT_PROMPTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_block(prompt: str) -> str:
    """Return the cross-ref block from a prompt string, or '' if absent."""
    m = re.search(
        r'\n## (?:CROSS-REFERENCE LINKS|QUERVERWEISE)\n.*?\n\n',
        prompt,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _block_ids(prompt: str) -> list:
    """Return ordered list of section IDs listed in the cross-ref block."""
    block = _extract_block(prompt)
    return re.findall(r'^- \[\[([^\|]+)\|', block, re.MULTILINE)


# ---------------------------------------------------------------------------
# TestRegistry
# ---------------------------------------------------------------------------

class TestRegistry:
    """Tests for cross_ref_registry constants and build_cross_ref_block."""

    def test_all_ids_count(self):
        assert len(ALL_IDS) == 10

    def test_all_ids_content(self):
        expected = {
            "company_profile", "maturity_assessment", "business_objectives",
            "situation_assessment", "ai_goals", "project_plan",
            "business_case", "cost_tco", "swot_analysis", "technical_briefing",
        }
        assert ALL_IDS == expected

    def test_section_labels_languages(self):
        assert set(SECTION_LABELS.keys()) == {"en", "de"}

    def test_section_labels_en_count(self):
        assert len(SECTION_LABELS["en"]) == 10

    def test_section_labels_de_count(self):
        assert len(SECTION_LABELS["de"]) == 10

    def test_section_labels_keys_match_all_ids(self):
        assert set(SECTION_LABELS["en"].keys()) == ALL_IDS
        assert set(SECTION_LABELS["de"].keys()) == ALL_IDS

    def test_step_available_ids_all_steps_defined(self):
        required = {"consultation", "business_case", "cost_estimation", "swot", "technical_briefing"}
        assert required.issubset(set(STEP_AVAILABLE_IDS.keys()))

    def test_step_available_ids_are_subsets_of_all_ids(self):
        for step, ids in STEP_AVAILABLE_IDS.items():
            assert set(ids).issubset(ALL_IDS), f"{step} contains IDs not in ALL_IDS: {set(ids) - ALL_IDS}"

    def test_step_ids_monotone(self):
        """Each step's available IDs must be a superset of the previous step."""
        ordered = ["consultation", "business_case", "cost_estimation", "swot", "technical_briefing"]
        for i in range(1, len(ordered)):
            prev = set(STEP_AVAILABLE_IDS[ordered[i - 1]])
            curr = set(STEP_AVAILABLE_IDS[ordered[i]])
            assert prev.issubset(curr), (
                f"{ordered[i]} should be a superset of {ordered[i - 1]}; "
                f"missing: {prev - curr}"
            )

    def test_consultation_step_ids(self):
        assert STEP_AVAILABLE_IDS["consultation"] == ["company_profile", "maturity_assessment"]

    def test_technical_briefing_step_ids_excludes_self(self):
        assert "technical_briefing" not in STEP_AVAILABLE_IDS["technical_briefing"]

    def test_swot_step_excludes_technical_briefing(self):
        assert "technical_briefing" not in STEP_AVAILABLE_IDS["swot"]

    def test_business_case_step_excludes_future_sections(self):
        ids = STEP_AVAILABLE_IDS["business_case"]
        assert "business_case" not in ids
        assert "cost_tco" not in ids
        assert "swot_analysis" not in ids
        assert "technical_briefing" not in ids


class TestBuildCrossRefBlock:
    """Tests for build_cross_ref_block()."""

    def test_en_consultation_header(self):
        block = build_cross_ref_block("en", "consultation")
        assert "## CROSS-REFERENCE LINKS" in block

    def test_de_consultation_header(self):
        block = build_cross_ref_block("de", "consultation")
        assert "## QUERVERWEISE" in block

    def test_en_consultation_contains_only_two_ids(self):
        block = build_cross_ref_block("en", "consultation")
        ids = re.findall(r'^- \[\[([^\|]+)\|', block, re.MULTILINE)
        assert ids == ["company_profile", "maturity_assessment"]

    def test_de_consultation_contains_german_labels(self):
        block = build_cross_ref_block("de", "consultation")
        assert "Unternehmensprofil" in block
        assert "Reifegradanalyse" in block

    def test_en_business_case_contains_six_ids(self):
        block = build_cross_ref_block("en", "business_case")
        ids = re.findall(r'^- \[\[([^\|]+)\|', block, re.MULTILINE)
        assert len(ids) == 6
        assert ids == STEP_AVAILABLE_IDS["business_case"]

    def test_en_swot_excludes_technical_briefing(self):
        block = build_cross_ref_block("en", "swot")
        assert "technical_briefing" not in block

    def test_en_technical_briefing_has_nine_ids(self):
        block = build_cross_ref_block("en", "technical_briefing")
        ids = re.findall(r'^- \[\[([^\|]+)\|', block, re.MULTILINE)
        assert len(ids) == 9

    def test_unknown_step_returns_empty_list(self):
        block = build_cross_ref_block("en", "nonexistent_step")
        ids = re.findall(r'^- \[\[([^\|]+)\|', block, re.MULTILINE)
        assert ids == []

    def test_unknown_lang_falls_back_to_english(self):
        block = build_cross_ref_block("fr", "consultation")
        assert "Company Profile" in block  # falls back to en labels

    def test_block_starts_with_newline(self):
        block = build_cross_ref_block("en", "consultation")
        assert block.startswith("\n")

    def test_block_ends_with_newline(self):
        block = build_cross_ref_block("en", "consultation")
        assert block.endswith("\n")

    def test_de_cost_estimation_contains_business_case(self):
        block = build_cross_ref_block("de", "cost_estimation")
        assert "[[business_case|Business Case]]" in block

    def test_all_ids_in_block_are_valid(self):
        for step in STEP_AVAILABLE_IDS:
            block = build_cross_ref_block("en", step)
            ids = re.findall(r'\[\[([^\|]+)\|', block)
            # Skip the placeholder in the instruction text "[[section_id|..."
            real_ids = [i for i in ids if i != "section_id"]
            for sid in real_ids:
                assert sid in ALL_IDS, f"Unknown ID {sid!r} in block for step {step!r}"


# ---------------------------------------------------------------------------
# TestNormalizeWikiLinks
# ---------------------------------------------------------------------------

class TestNormalizeWikiLinks:
    """Tests for normalize_wiki_links() in llm.py."""

    # --- Correct IDs pass through unchanged ---

    def test_valid_id_unchanged(self):
        assert normalize_wiki_links("[[company_profile|Company]]") == "[[company_profile|Company]]"

    def test_valid_id_with_spaces_in_label_unchanged(self):
        text = "[[business_objectives|My Business Objectives]]"
        assert normalize_wiki_links(text) == text

    def test_all_valid_ids_pass_through(self):
        for sid in ALL_IDS:
            text = f"[[{sid}|Label]]"
            assert normalize_wiki_links(text) == text

    # --- Case normalization ---

    def test_uppercase_id_normalized(self):
        assert normalize_wiki_links("[[COMPANY_PROFILE|X]]") == "[[company_profile|X]]"

    def test_mixed_case_id_normalized(self):
        assert normalize_wiki_links("[[Company_Profile|X]]") == "[[company_profile|X]]"

    def test_allcaps_with_underscores_normalized(self):
        assert normalize_wiki_links("[[MATURITY_ASSESSMENT|X]]") == "[[maturity_assessment|X]]"

    def test_titlecase_with_underscores_normalized(self):
        assert normalize_wiki_links("[[Business_Objectives|X]]") == "[[business_objectives|X]]"

    # --- Dash normalization ---

    def test_dash_replaced_with_underscore(self):
        assert normalize_wiki_links("[[company-profile|X]]") == "[[company_profile|X]]"

    def test_dash_in_ai_goals(self):
        assert normalize_wiki_links("[[ai-goals|X]]") == "[[ai_goals|X]]"

    # --- Space normalization ---

    def test_spaces_replaced_with_underscores(self):
        assert normalize_wiki_links("[[business case|X]]") == "[[business_case|X]]"

    def test_spaces_in_longer_id(self):
        assert normalize_wiki_links("[[situation assessment|X]]") == "[[situation_assessment|X]]"

    # --- camelCase normalization ---

    def test_camelcase_business_objectives(self):
        assert normalize_wiki_links("[[businessObjectives|X]]") == "[[business_objectives|X]]"

    def test_camelcase_company_profile(self):
        assert normalize_wiki_links("[[companyProfile|X]]") == "[[company_profile|X]]"

    def test_camelcase_maturity_assessment(self):
        assert normalize_wiki_links("[[maturityAssessment|X]]") == "[[maturity_assessment|X]]"

    def test_camelcase_swot_analysis(self):
        assert normalize_wiki_links("[[swotAnalysis|X]]") == "[[swot_analysis|X]]"

    def test_camelcase_technical_briefing(self):
        assert normalize_wiki_links("[[technicalBriefing|X]]") == "[[technical_briefing|X]]"

    # --- Unknown IDs left unchanged ---

    def test_unknown_id_unchanged(self):
        text = "[[unknown_section|X]]"
        assert normalize_wiki_links(text) == text

    def test_hallucinated_id_unchanged(self):
        text = "[[data_analytics|Analytics]]"
        assert normalize_wiki_links(text) == text

    def test_typo_id_unchanged(self):
        # Double letter typo can't be fixed by normalization
        text = "[[situation_assessessment|X]]"
        assert normalize_wiki_links(text) == text

    # --- Display text is always preserved ---

    def test_display_text_preserved_on_normalization(self):
        result = normalize_wiki_links("[[Business_Objectives|My Custom Label]]")
        assert "My Custom Label" in result
        assert result == "[[business_objectives|My Custom Label]]"

    def test_display_text_preserved_on_passthrough(self):
        text = "[[company_profile|Specific Label Here]]"
        assert normalize_wiki_links(text) == text

    # --- Fallback when no display text ---

    def test_no_display_text_uses_id_as_display(self):
        # [[company_profile]] → [[company_profile|company_profile]]
        result = normalize_wiki_links("[[company_profile]]")
        assert result == "[[company_profile|company_profile]]"

    def test_no_display_text_normalized_id(self):
        result = normalize_wiki_links("[[Company_Profile]]")
        assert result == "[[company_profile|Company_Profile]]"

    # --- Multiple links in one string ---

    def test_multiple_links_in_sentence(self):
        text = "See [[businessObjectives|goals]] and [[Company-Profile|profile]] for details."
        result = normalize_wiki_links(text)
        assert "[[business_objectives|goals]]" in result
        assert "[[company_profile|profile]]" in result

    def test_multiple_links_mixed_valid_invalid(self):
        text = "[[maturity_assessment|MA]] and [[unknown_xyz|XYZ]]"
        result = normalize_wiki_links(text)
        assert "[[maturity_assessment|MA]]" in result
        assert "[[unknown_xyz|XYZ]]" in result  # unknown unchanged

    def test_no_links_unchanged(self):
        text = "No wiki links here, just plain text."
        assert normalize_wiki_links(text) == text

    def test_empty_string(self):
        assert normalize_wiki_links("") == ""


# ---------------------------------------------------------------------------
# TestDefaultPromptsInjection
# ---------------------------------------------------------------------------

class TestDefaultPromptsInjection:
    """Tests that _inject_cross_refs() correctly replaced all 10 hardcoded blocks."""

    STEP_MAP = {
        "extraction_summary":        "consultation",
        "business_case_extraction":  "business_case",
        "cost_estimation_extraction": "cost_estimation",
        "transition_briefing_system": "technical_briefing",
        "swot_analysis_system":      "swot",
    }

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("prompt_key,step", STEP_MAP.items())
    def test_block_ids_match_registry(self, lang, prompt_key, step):
        """Every prompt's cross-ref block must list exactly the registry IDs for its step."""
        prompt = DEFAULT_PROMPTS[lang][prompt_key]
        ids = _block_ids(prompt)
        expected = STEP_AVAILABLE_IDS[step]
        assert ids == expected, (
            f"{lang} {prompt_key}: expected {expected}, got {ids}"
        )

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_extraction_summary_only_two_ids(self, lang):
        ids = _block_ids(DEFAULT_PROMPTS[lang]["extraction_summary"])
        assert ids == ["company_profile", "maturity_assessment"]

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_extraction_summary_excludes_future_sections(self, lang):
        block = _extract_block(DEFAULT_PROMPTS[lang]["extraction_summary"])
        for future_id in ("business_case", "cost_tco", "swot_analysis", "technical_briefing"):
            assert future_id not in block, f"{lang} extraction_summary contains forward-ref: {future_id}"

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_business_case_extraction_excludes_future_sections(self, lang):
        block = _extract_block(DEFAULT_PROMPTS[lang]["business_case_extraction"])
        for future_id in ("cost_tco", "swot_analysis", "technical_briefing"):
            assert future_id not in block, f"{lang} business_case_extraction contains forward-ref: {future_id}"

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_cost_estimation_extraction_excludes_future_sections(self, lang):
        block = _extract_block(DEFAULT_PROMPTS[lang]["cost_estimation_extraction"])
        for future_id in ("swot_analysis", "technical_briefing"):
            assert future_id not in block, f"{lang} cost_estimation_extraction contains forward-ref: {future_id}"

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_swot_excludes_technical_briefing(self, lang):
        block = _extract_block(DEFAULT_PROMPTS[lang]["swot_analysis_system"])
        assert "technical_briefing" not in block

    @pytest.mark.parametrize("lang", ["en", "de"])
    def test_technical_briefing_includes_swot(self, lang):
        block = _extract_block(DEFAULT_PROMPTS[lang]["transition_briefing_system"])
        assert "swot_analysis" in block

    def test_en_block_uses_english_header(self):
        block = _extract_block(DEFAULT_PROMPTS["en"]["extraction_summary"])
        assert "## CROSS-REFERENCE LINKS" in block
        assert "## QUERVERWEISE" not in block

    def test_de_block_uses_german_header(self):
        block = _extract_block(DEFAULT_PROMPTS["de"]["extraction_summary"])
        assert "## QUERVERWEISE" in block
        assert "## CROSS-REFERENCE LINKS" not in block

    def test_de_block_uses_german_labels(self):
        block = _extract_block(DEFAULT_PROMPTS["de"]["extraction_summary"])
        assert "Unternehmensprofil" in block
        assert "Reifegradanalyse" in block

    def test_en_block_uses_english_labels(self):
        block = _extract_block(DEFAULT_PROMPTS["en"]["extraction_summary"])
        assert "Company Profile" in block
        assert "Maturity Assessment" in block

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("prompt_key", STEP_MAP.keys())
    def test_prompt_body_preserved_after_injection(self, lang, prompt_key):
        """The prompt text outside the cross-ref block should still exist."""
        prompt = DEFAULT_PROMPTS[lang][prompt_key]
        # Every prompt should still have substantial content beyond the cross-ref block
        block = _extract_block(prompt)
        rest = prompt.replace(block, "")
        assert len(rest) > 100, f"{lang} {prompt_key}: prompt body seems empty after block removal"

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("prompt_key", STEP_MAP.keys())
    def test_only_one_cross_ref_block_per_prompt(self, lang, prompt_key):
        """No prompt should have duplicate cross-ref blocks."""
        prompt = DEFAULT_PROMPTS[lang][prompt_key]
        headers = re.findall(r'## (?:CROSS-REFERENCE LINKS|QUERVERWEISE)', prompt)
        assert len(headers) == 1, f"{lang} {prompt_key}: found {len(headers)} cross-ref blocks"

    @pytest.mark.parametrize("lang", ["en", "de"])
    @pytest.mark.parametrize("prompt_key", STEP_MAP.keys())
    def test_all_block_ids_are_valid(self, lang, prompt_key):
        """No block should list IDs outside the known set."""
        ids = _block_ids(DEFAULT_PROMPTS[lang][prompt_key])
        for sid in ids:
            assert sid in ALL_IDS, f"{lang} {prompt_key}: unknown ID {sid!r} in block"
