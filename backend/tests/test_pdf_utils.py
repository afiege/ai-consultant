"""Tests for PDF generation utility functions."""

import pytest
from app.services.pdf_generator import markdown_to_reportlab


class TestMarkdownToReportlab:
    """Tests for markdown-to-ReportLab HTML conversion."""

    def test_empty_input(self):
        assert markdown_to_reportlab("") == ""

    def test_none_input(self):
        assert markdown_to_reportlab(None) == ""

    def test_bold_conversion(self):
        result = markdown_to_reportlab("This is **bold** text")
        assert "<b>bold</b>" in result

    def test_italic_conversion(self):
        result = markdown_to_reportlab("This is *italic* text")
        assert "<i>italic</i>" in result

    def test_bold_not_double_italic(self):
        """Bold markers should not be treated as nested italics."""
        result = markdown_to_reportlab("**bold text**")
        assert "<b>bold text</b>" in result
        assert "<i>" not in result

    def test_h1_to_bold(self):
        result = markdown_to_reportlab("# Header One")
        assert "<b>Header One</b>" in result

    def test_h2_to_bold(self):
        result = markdown_to_reportlab("## Header Two")
        assert "<b>Header Two</b>" in result

    def test_h3_to_bold(self):
        result = markdown_to_reportlab("### Header Three")
        assert "<b>Header Three</b>" in result

    def test_html_escaping_ampersand(self):
        result = markdown_to_reportlab("A & B")
        assert "&amp;" in result

    def test_html_escaping_angle_brackets(self):
        result = markdown_to_reportlab("a < b > c")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_newlines_to_br(self):
        result = markdown_to_reportlab("line1\nline2")
        assert "<br/>" in result

    def test_wiki_link_with_display(self):
        result = markdown_to_reportlab("See [[target|Display Text]] here")
        assert "Display Text" in result
        assert "[[" not in result
        assert "target" not in result

    def test_wiki_link_without_display(self):
        result = markdown_to_reportlab("See [[target_name]] here")
        assert "target_name" in result
        assert "[[" not in result

    def test_plain_text_unchanged(self):
        result = markdown_to_reportlab("Just plain text")
        assert "Just plain text" in result

    def test_combined_formatting(self):
        result = markdown_to_reportlab("**Bold** and *italic* in one line")
        assert "<b>Bold</b>" in result
        assert "<i>italic</i>" in result
