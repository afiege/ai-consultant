"""Tests for markdown section extraction logic used across services."""

import re
import pytest
from typing import Optional


def extract_section(text: str, section_name: str) -> Optional[str]:
    """Standalone version of _extract_section used in consultation/business_case/cost services."""
    pattern = rf"##\s*{section_name}[^\n]*\n(.*?)(?=##|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


class TestExtractSection:
    """Tests for ## header-based section extraction."""

    def test_extract_first_section(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "Business Objectives")
        assert "Reduce scrap rate" in result
        assert "IATF 16949" in result

    def test_extract_middle_section(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "Situation Assessment")
        assert "paper-based" in result
        assert "No digital defect tracking" in result

    def test_extract_last_section(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "Project Plan")
        assert "Tablet-based documentation" in result
        assert "Camera deployment" in result

    def test_missing_section_returns_none(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "Non-Existent Section")
        assert result is None

    def test_empty_text_returns_none(self):
        result = extract_section("", "Business Objectives")
        assert result is None

    def test_case_insensitive(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "business objectives")
        assert result is not None
        assert "Reduce scrap rate" in result

    def test_german_sections(self, sample_markdown_sections_de):
        result = extract_section(sample_markdown_sections_de, "Geschäftsziele")
        assert "Ausschussrate" in result

    def test_section_at_end_no_trailing_header(self):
        text = "## Only Section\nThis is the content."
        result = extract_section(text, "Only Section")
        assert result == "This is the content."

    def test_section_content_excludes_next_header(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "Business Objectives")
        assert "Situation Assessment" not in result
        assert "paper-based" not in result

    def test_multiline_content_preserved(self, sample_markdown_sections):
        result = extract_section(sample_markdown_sections, "AI Goals")
        assert "visual defect detection" in result
        assert "measurement device data" in result

    def test_whitespace_after_header(self):
        text = "##   Spaced Header  \nContent here."
        result = extract_section(text, "Spaced Header")
        assert result == "Content here."

    def test_header_with_trailing_parenthetical(self):
        """Headers like '## RECURRING COSTS (Monthly/Annual)' should match 'RECURRING COSTS'."""
        text = (
            "## RECURRING COSTS (Monthly/Annual)\n"
            "Cloud hosting: $500/month\n"
            "Licenses: $200/month\n"
            "\n"
            "## MAINTENANCE (Annual)\n"
            "Support contract: $2,400/year\n"
        )
        result = extract_section(text, "RECURRING COSTS")
        assert result is not None
        assert "Cloud hosting" in result
        assert "Licenses" in result
        # Should not bleed into the next section
        assert "Support contract" not in result

    def test_header_with_trailing_parenthetical_german(self):
        """German headers with parenthetical text should also match."""
        text = (
            "## LAUFENDE KOSTEN (Monatlich/Jährlich)\n"
            "Cloud-Hosting: 500€/Monat\n"
            "\n"
            "## WARTUNG (Jährlich)\n"
            "Wartungsvertrag: 2.400€/Jahr\n"
        )
        result = extract_section(text, "LAUFENDE KOSTEN")
        assert result is not None
        assert "Cloud-Hosting" in result

    def test_header_with_tco_parenthetical(self):
        """TCO header with '(TCO)' suffix should match."""
        text = (
            "## 3-YEAR TOTAL COST OF OWNERSHIP (TCO)\n"
            "Total: $150,000\n"
        )
        result = extract_section(text, "3-YEAR TOTAL COST OF OWNERSHIP")
        assert result is not None
        assert "Total: $150,000" in result
