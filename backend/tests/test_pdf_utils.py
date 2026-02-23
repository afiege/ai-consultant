"""Tests for PDF generation utility functions."""

import pytest
from app.services.pdf_generator import to_html, _extract_section


class TestToHtml:
    """Tests for markdown-to-HTML conversion (WeasyPrint pipeline)."""

    def test_empty_input(self):
        assert to_html("") == ""

    def test_none_input(self):
        assert to_html(None) == ""

    def test_bold_conversion(self):
        result = to_html("This is **bold** text")
        assert "<strong>bold</strong>" in result

    def test_italic_conversion(self):
        result = to_html("This is *italic* text")
        assert "<em>italic</em>" in result

    def test_bold_not_italic(self):
        """Bold markers should not produce italic tags."""
        result = to_html("**bold text**")
        assert "<strong>bold text</strong>" in result
        assert "<em>" not in result

    def test_h1_renders_as_heading(self):
        result = to_html("# Header One")
        assert "<h1>Header One</h1>" in result

    def test_h2_renders_as_heading(self):
        result = to_html("## Header Two")
        assert "<h2>Header Two</h2>" in result

    def test_h3_renders_as_heading(self):
        result = to_html("### Header Three")
        assert "<h3>Header Three</h3>" in result

    def test_wiki_link_with_display(self):
        result = to_html("See [[target|Display Text]] here")
        assert "Display Text" in result
        assert "[[" not in result
        assert "target" not in result

    def test_wiki_link_without_display(self):
        result = to_html("See [[target_name]] here")
        assert "target_name" in result
        assert "[[" not in result

    def test_plain_text_unchanged(self):
        result = to_html("Just plain text")
        assert "Just plain text" in result

    def test_combined_formatting(self):
        result = to_html("**Bold** and *italic* in one line")
        assert "<strong>Bold</strong>" in result
        assert "<em>italic</em>" in result


class TestExtractSection:
    """Tests for _extract_section markdown section extractor."""

    def test_extract_existing_section(self):
        text = "## First Steps\nDo this first.\n## Next Section\nOther content."
        result = _extract_section(text, "First Steps")
        assert "Do this first." in result
        assert "Next Section" not in result

    def test_extract_missing_section_returns_empty(self):
        text = "## Some Section\nContent here."
        result = _extract_section(text, "Nonexistent")
        assert result == ""

    def test_empty_input_returns_empty(self):
        assert _extract_section("", "First Steps") == ""
        assert _extract_section(None, "First Steps") == ""

    def test_case_insensitive(self):
        text = "## first steps\nDo this."
        result = _extract_section(text, "First Steps")
        assert "Do this." in result
