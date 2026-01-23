"""PDF generation service for consultation reports."""

import io
import re
from datetime import datetime
from typing import Optional, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF
from sqlalchemy.orm import Session

from ..models import (
    Session as SessionModel,
    CompanyInfo,
    Participant,
    IdeaSheet,
    Idea,
    Prioritization,
    ConsultationMessage,
    ConsultationFinding
)


def markdown_to_reportlab(text: str) -> str:
    """
    Convert markdown text to ReportLab-compatible HTML.
    Supports: **bold**, *italic*, bullet lists, numbered lists.
    """
    if not text:
        return ""

    # Escape HTML special characters first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Convert **bold** to <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # Convert *italic* to <i>italic</i> (but not if already part of bold)
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', text)

    # Convert headers (## Header) to bold
    text = re.sub(r'^##\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Convert newlines to <br/>
    text = text.replace('\n', '<br/>')

    # Convert bullet points (- item or • item) to proper formatting
    text = re.sub(r'<br/>[\s]*[-•]\s*', '<br/>&bull; ', text)
    text = re.sub(r'^[\s]*[-•]\s*', '&bull; ', text)

    # Convert numbered lists (1. item) to proper formatting
    text = re.sub(r'<br/>[\s]*(\d+)\.\s*', r'<br/>\1. ', text)

    return text


def markdown_to_elements(text: str, style, bullet_style=None) -> List:
    """
    Convert markdown text to a list of ReportLab elements.
    Handles bullet lists as separate paragraphs for better formatting.
    """
    if not text:
        return []

    elements = []

    # Split by double newlines to get paragraphs
    paragraphs = re.split(r'\n\n+', text.strip())

    for para in paragraphs:
        if not para.strip():
            continue

        # Check if this is a list (all lines start with - or number.)
        lines = para.strip().split('\n')
        is_bullet_list = all(re.match(r'^\s*[-•]\s*', line) for line in lines if line.strip())
        is_numbered_list = all(re.match(r'^\s*\d+\.\s*', line) for line in lines if line.strip())

        if is_bullet_list or is_numbered_list:
            # Process as list items
            for line in lines:
                if not line.strip():
                    continue
                # Remove the bullet/number prefix
                item_text = re.sub(r'^\s*[-•]\s*', '', line)
                item_text = re.sub(r'^\s*\d+\.\s*', '', item_text)

                # Apply markdown formatting
                item_text = item_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                item_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', item_text)
                item_text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', item_text)

                use_style = bullet_style if bullet_style else style
                elements.append(Paragraph(f"&bull; {item_text}", use_style))
        else:
            # Regular paragraph - convert markdown
            content = markdown_to_reportlab(para)
            elements.append(Paragraph(content, style))

    return elements


class PDFReportGenerator:
    """Generates PDF reports from consultation sessions."""

    def __init__(self, db: Session):
        self.db = db
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='Title1',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.HexColor('#2c5282'),
            borderPadding=5
        ))

        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor('#4a5568')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=6,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=14
        ))

        self.styles.add(ParagraphStyle(
            name='IdeaText',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceBefore=4,
            spaceAfter=4,
            bulletIndent=10
        ))

        self.styles.add(ParagraphStyle(
            name='ChatUser',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=40,
            textColor=colors.HexColor('#2b6cb0'),
            spaceBefore=8,
            spaceAfter=4
        ))

        self.styles.add(ParagraphStyle(
            name='ChatAssistant',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2d3748'),
            spaceBefore=8,
            spaceAfter=4,
            leading=14
        ))

    def generate_report(self, session_uuid: str) -> bytes:
        """
        Generate a complete PDF report for the session.

        Structure:
        - Title page
        - Executive Summary (main findings & recommendations)
        - Appendix: Input documentation (company info, ideas, prioritization, chat)

        Returns:
            PDF file as bytes
        """
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")

        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Build content
        story = []

        # Title page
        story.extend(self._build_title_page(db_session))

        # Company Profile Summary (main body)
        story.append(PageBreak())
        story.extend(self._build_company_profile_summary(db_session))

        # Main Results Section: Executive Summary with findings and recommendations
        story.append(PageBreak())
        story.extend(self._build_executive_summary(db_session))

        # Business Case Section (Step 5)
        story.append(PageBreak())
        story.extend(self._build_business_case_section(db_session))

        # Implementation Roadmap
        story.append(PageBreak())
        story.extend(self._build_recommendations_section(db_session))

        # Appendix header
        story.append(PageBreak())
        story.extend(self._build_appendix_header())

        # Appendix A: Company Overview (input)
        story.extend(self._build_company_section(db_session))

        # Appendix B: Brainstorming Ideas (input)
        story.append(PageBreak())
        story.extend(self._build_ideas_section(db_session))

        # Appendix C: Prioritization Results (input)
        story.append(PageBreak())
        story.extend(self._build_prioritization_section(db_session))

        # Appendix D: Consultation Conversation (input)
        story.append(PageBreak())
        story.extend(self._build_consultation_transcript(db_session))

        # Appendix E: Business Case Conversation (input)
        story.append(PageBreak())
        story.extend(self._build_business_case_transcript(db_session))

        # Build PDF
        doc.build(story)

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _build_title_page(self, db_session: SessionModel) -> list:
        """Build the title page."""
        elements = []

        elements.append(Spacer(1, 2*inch))

        # Title
        elements.append(Paragraph(
            "AI & Digitalization<br/>Consultation Report",
            self.styles['Title1']
        ))

        elements.append(Spacer(1, 0.5*inch))

        # Company name
        company_name = db_session.company_name or "Company"
        elements.append(Paragraph(
            f"<b>{company_name}</b>",
            ParagraphStyle(
                'CompanyName',
                parent=self.styles['Normal'],
                fontSize=18,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#4a5568')
            )
        ))

        elements.append(Spacer(1, 1*inch))

        # Date
        date_str = datetime.now().strftime("%B %d, %Y")
        elements.append(Paragraph(
            f"Generated: {date_str}",
            ParagraphStyle(
                'DateStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.gray
            )
        ))

        elements.append(Spacer(1, 0.5*inch))

        # Session ID
        elements.append(Paragraph(
            f"Session ID: {db_session.session_uuid[:8]}...",
            ParagraphStyle(
                'SessionId',
                parent=self.styles['Normal'],
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.lightgrey
            )
        ))

        return elements

    def _build_company_profile_summary(self, db_session: SessionModel) -> list:
        """Build the company profile summary section for the main body."""
        elements = []

        elements.append(Paragraph("Company Profile", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))

        # Get company profile finding
        finding = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type == 'company_profile'
        ).first()

        if finding and finding.finding_text:
            # Use the summarized company profile from the consultation findings
            content_elements = markdown_to_elements(
                finding.finding_text,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            # Fallback: Create a basic profile from available data
            elements.append(Paragraph(
                f"<b>Company:</b> {db_session.company_name or 'Not specified'}",
                self.styles['ReportBody']
            ))
            elements.append(Spacer(1, 0.1*inch))

            # Get company info for basic summary
            company_infos = self.db.query(CompanyInfo).filter(
                CompanyInfo.session_id == db_session.id
            ).all()

            if company_infos:
                elements.append(Paragraph(
                    "The following information was provided about the company:",
                    self.styles['ReportBody']
                ))
                elements.append(Spacer(1, 0.1*inch))

                for info in company_infos[:2]:  # Limit to first 2 entries
                    source_label = info.info_type.upper() if info.info_type else "TEXT"
                    # Truncate for summary view
                    content = info.content or ""
                    if len(content) > 500:
                        content = content[:500] + "..."

                    elements.append(Paragraph(
                        f"<b>Source: {source_label}</b>",
                        self.styles['SubHeader']
                    ))
                    content_elements = markdown_to_elements(
                        content,
                        self.styles['ReportBody'],
                        self.styles['IdeaText']
                    )
                    elements.extend(content_elements)
                    elements.append(Spacer(1, 0.1*inch))

                if len(company_infos) > 2:
                    elements.append(Paragraph(
                        f"<i>See Appendix A for complete company information ({len(company_infos)} sources total).</i>",
                        self.styles['ReportBody']
                    ))
            else:
                elements.append(Paragraph(
                    "No detailed company information was provided. Complete Step 1 to populate this section.",
                    self.styles['ReportBody']
                ))

        elements.append(Spacer(1, 0.3*inch))

        # Add a reference to full details
        elements.append(Paragraph(
            "<i>For complete company documentation, see Appendix A.</i>",
            ParagraphStyle(
                'AppendixRef',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=colors.gray,
                alignment=TA_CENTER
            )
        ))

        return elements

    def _build_executive_summary(self, db_session: SessionModel) -> list:
        """Build the executive summary with CRISP-DM Business Understanding findings."""
        elements = []

        elements.append(Paragraph("Executive Summary: Business Understanding", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "This section presents the key findings from the CRISP-DM Business Understanding phase of the AI consultation.",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Get findings
        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id
        ).all()

        findings_dict = {f.factor_type: f.finding_text for f in findings}

        # 1. Business Objectives
        elements.append(Paragraph("1. Business Objectives", self.styles['SubHeader']))
        if findings_dict.get('business_objectives'):
            content_elements = markdown_to_elements(
                findings_dict['business_objectives'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("No business objectives documented.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 2. Situation Assessment
        elements.append(Paragraph("2. Situation Assessment", self.styles['SubHeader']))
        if findings_dict.get('situation_assessment'):
            content_elements = markdown_to_elements(
                findings_dict['situation_assessment'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("No situation assessment documented.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 3. AI/Data Mining Goals
        elements.append(Paragraph("3. AI/Data Mining Goals", self.styles['SubHeader']))
        if findings_dict.get('ai_goals'):
            content_elements = markdown_to_elements(
                findings_dict['ai_goals'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("No AI/data mining goals documented.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 4. Project Plan
        elements.append(Paragraph("4. Project Plan", self.styles['SubHeader']))
        if findings_dict.get('project_plan'):
            content_elements = markdown_to_elements(
                findings_dict['project_plan'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("No project plan documented.", self.styles['ReportBody']))

        return elements

    def _build_business_case_section(self, db_session: SessionModel) -> list:
        """Build the business case indication section (Step 5) with graphical elements."""
        elements = []

        elements.append(Paragraph("Business Case Indication", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "This section presents the business case analysis using the 5-Level Value Framework.",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Get business case findings
        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                'business_case_classification',
                'business_case_calculation',
                'business_case_validation',
                'business_case_pitch'
            ])
        ).all()

        findings_dict = {f.factor_type: f.finding_text for f in findings}

        # Check if any business case findings exist
        if not findings_dict:
            elements.append(Paragraph(
                "No business case analysis was completed. Complete Step 5 to populate this section.",
                self.styles['ReportBody']
            ))
            return elements

        # 1. Classification with Visual Framework Ladder
        elements.append(Paragraph("Value Framework Classification", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Build the 5-level framework visualization
        classification_text = findings_dict.get('business_case_classification', '')
        elements.extend(self._build_value_framework_visual(classification_text))
        elements.append(Spacer(1, 0.2*inch))

        # Classification details in a styled box
        if classification_text:
            classification_table = Table(
                [[Paragraph(
                    f"<b>Analysis:</b><br/>{markdown_to_reportlab(classification_text)}",
                    ParagraphStyle('ClassBox', parent=self.styles['ReportBody'], fontSize=9, leading=12)
                )]],
                colWidths=[15*cm]
            )
            classification_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f8')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(classification_table)

        elements.append(Spacer(1, 0.3*inch))

        # 2. Back-of-the-envelope Calculation with styled metrics box
        elements.append(Paragraph("Financial Projection", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('business_case_calculation'):
            elements.extend(self._build_calculation_visual(findings_dict['business_case_calculation']))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.3*inch))

        # 3. Validation Questions as checklist
        elements.append(Paragraph("Validation Checklist", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('business_case_validation'):
            elements.extend(self._build_validation_checklist(findings_dict['business_case_validation']))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.3*inch))

        # 4. Management Pitch as prominent callout
        elements.append(Paragraph("Management Pitch", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('business_case_pitch'):
            elements.extend(self._build_pitch_callout(findings_dict['business_case_pitch']))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        return elements

    def _build_value_framework_visual(self, classification_text: str) -> list:
        """Build a visual representation of the 5-level value framework."""
        elements = []

        # Define the 5 levels with colors
        levels = [
            ("Level 5", "Strategic Scaling", "Expand capacity without proportional headcount", colors.HexColor('#1a365d')),
            ("Level 4", "Risk Mitigation", "Avoid Cost of Poor Quality, recalls, failures", colors.HexColor('#2c5282')),
            ("Level 3", "Project Acceleration", "Reduce time-to-market or R&D cycles", colors.HexColor('#2b6cb0')),
            ("Level 2", "Process Efficiency", "Time savings in routine tasks", colors.HexColor('#3182ce')),
            ("Level 1", "Budget Substitution", "Replace external services with AI solution", colors.HexColor('#4299e1')),
        ]

        # Detect which level(s) are mentioned in the classification
        detected_levels = set()
        text_lower = classification_text.lower()
        for i, (level_num, level_name, _, _) in enumerate(levels):
            if level_name.lower() in text_lower or f"level {5-i}" in text_lower or f"stufe {5-i}" in text_lower:
                detected_levels.add(5-i)

        # Build table rows for the framework
        table_data = []
        for i, (level_num, level_name, description, base_color) in enumerate(levels):
            level_value = 5 - i
            is_selected = level_value in detected_levels

            # Create row with level indicator
            if is_selected:
                indicator = Paragraph(
                    f"<b>&rarr;</b>",
                    ParagraphStyle('Arrow', fontSize=14, textColor=colors.HexColor('#276749'), alignment=TA_CENTER)
                )
                bg_color = colors.HexColor('#c6f6d5')  # Light green for selected
                text_color = colors.HexColor('#22543d')
            else:
                indicator = Paragraph("", ParagraphStyle('Empty', fontSize=10))
                bg_color = colors.HexColor('#edf2f7')  # Light gray
                text_color = colors.HexColor('#4a5568')

            level_cell = Paragraph(
                f"<b>{level_num}</b>",
                ParagraphStyle('Level', fontSize=9, textColor=colors.white, alignment=TA_CENTER)
            )
            name_cell = Paragraph(
                f"<b>{level_name}</b>",
                ParagraphStyle('Name', fontSize=9, textColor=text_color)
            )
            desc_cell = Paragraph(
                description,
                ParagraphStyle('Desc', fontSize=8, textColor=text_color)
            )

            table_data.append([indicator, level_cell, name_cell, desc_cell])

        # Create the table
        framework_table = Table(
            table_data,
            colWidths=[0.8*cm, 1.5*cm, 4*cm, 9*cm]
        )

        # Apply styling
        style_commands = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]

        # Add row-specific styling
        for i, (_, _, _, base_color) in enumerate(levels):
            level_value = 5 - i
            is_selected = level_value in detected_levels

            # Level cell background (always colored)
            style_commands.append(('BACKGROUND', (1, i), (1, i), base_color))

            # Row background for content cells
            if is_selected:
                style_commands.append(('BACKGROUND', (0, i), (0, i), colors.HexColor('#c6f6d5')))
                style_commands.append(('BACKGROUND', (2, i), (-1, i), colors.HexColor('#c6f6d5')))
            else:
                style_commands.append(('BACKGROUND', (2, i), (-1, i), colors.HexColor('#f7fafc')))

        framework_table.setStyle(TableStyle(style_commands))
        elements.append(framework_table)

        return elements

    def _build_calculation_visual(self, calculation_text: str) -> list:
        """Build a styled visual for the financial calculation."""
        elements = []

        # Create a styled calculation box with header
        header_style = ParagraphStyle(
            'CalcHeader',
            parent=self.styles['ReportBody'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_LEFT
        )
        content_style = ParagraphStyle(
            'CalcContent',
            parent=self.styles['ReportBody'],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#2d3748')
        )

        # Header row
        header_table = Table(
            [[Paragraph("<b>Back-of-the-Envelope Calculation</b>", header_style)]],
            colWidths=[15*cm]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c5282')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(header_table)

        # Content box
        content_para = Paragraph(markdown_to_reportlab(calculation_text), content_style)
        content_table = Table(
            [[content_para]],
            colWidths=[15*cm]
        )
        content_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ebf8ff')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#90cdf4')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(content_table)

        return elements

    def _build_validation_checklist(self, validation_text: str) -> list:
        """Build a checklist-style visualization for validation questions."""
        elements = []

        # Parse the validation text into individual questions
        lines = validation_text.strip().split('\n')
        questions = []
        for line in lines:
            line = line.strip()
            if line:
                # Remove bullet points or numbers
                cleaned = re.sub(r'^[\d\.\-\*\•]+\s*', '', line)
                if cleaned:
                    questions.append(cleaned)

        if not questions:
            # Fallback: treat the whole text as one item
            questions = [validation_text]

        # Build table rows for checklist
        table_data = []
        checkbox_style = ParagraphStyle('Checkbox', fontSize=12, alignment=TA_CENTER)
        question_style = ParagraphStyle(
            'Question',
            parent=self.styles['ReportBody'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#2d3748')
        )

        for i, question in enumerate(questions[:10]):  # Limit to 10 questions
            # Escape HTML
            question = question.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            checkbox = Paragraph("&#9744;", checkbox_style)  # Empty checkbox unicode
            q_text = Paragraph(question, question_style)
            table_data.append([checkbox, q_text])

        if table_data:
            checklist_table = Table(
                table_data,
                colWidths=[0.8*cm, 14.2*cm]
            )
            checklist_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffaf0')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ed8936')),
                ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#fbd38d')),
            ]))
            elements.append(checklist_table)
        else:
            elements.append(Paragraph(validation_text, self.styles['ReportBody']))

        return elements

    def _build_pitch_callout(self, pitch_text: str) -> list:
        """Build a prominent callout box for the management pitch."""
        elements = []

        # Create a visually prominent pitch box
        pitch_style = ParagraphStyle(
            'PitchText',
            parent=self.styles['ReportBody'],
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_LEFT
        )

        # Escape and format the pitch text
        pitch_clean = pitch_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        pitch_clean = pitch_clean.replace('\n', '<br/>')

        # Quote icon header
        quote_header = Table(
            [[Paragraph(
                "<b>&#10077; Elevator Pitch</b>",
                ParagraphStyle('QuoteHeader', fontSize=12, textColor=colors.HexColor('#2c5282'))
            )]],
            colWidths=[15*cm]
        )
        quote_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#bee3f8')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(quote_header)

        # Main pitch content with styled border
        pitch_content = Paragraph(f"<i>{pitch_clean}</i>", pitch_style)
        pitch_table = Table(
            [[pitch_content]],
            colWidths=[15*cm]
        )
        pitch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ebf8ff')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#3182ce')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ]))
        elements.append(pitch_table)

        # Closing quote
        quote_footer = Table(
            [[Paragraph(
                "<b>&#10078;</b>",
                ParagraphStyle('QuoteFooter', fontSize=14, textColor=colors.HexColor('#2c5282'), alignment=TA_RIGHT)
            )]],
            colWidths=[15*cm]
        )
        quote_footer.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#bee3f8')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(quote_footer)

        return elements

    def _build_appendix_header(self) -> list:
        """Build the appendix section header."""
        elements = []

        elements.append(Paragraph(
            "Appendix: Supporting Documentation",
            ParagraphStyle(
                'AppendixTitle',
                parent=self.styles['Heading1'],
                fontSize=20,
                spaceAfter=20,
                textColor=colors.HexColor('#1a365d'),
                alignment=TA_CENTER
            )
        ))

        elements.append(Paragraph(
            "This appendix contains the detailed input data collected during the consultation process, "
            "including company information, brainstorming results, prioritization scores, and the full consultation transcript.",
            self.styles['ReportBody']
        ))

        elements.append(Spacer(1, 0.5*inch))

        return elements

    def _build_company_section(self, db_session: SessionModel) -> list:
        """Build the company overview section."""
        elements = []

        elements.append(Paragraph("Appendix A: Company Overview", self.styles['SectionHeader']))

        # Get company info
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()

        if not company_infos:
            elements.append(Paragraph(
                "No company information was provided.",
                self.styles['ReportBody']
            ))
            return elements

        for info in company_infos:
            source_label = info.info_type.upper() if info.info_type else "TEXT"
            # Include original filename for file uploads, or source URL for web crawls
            if info.file_name:
                source_detail = f" ({info.file_name})"
            elif info.source_url:
                # Truncate long URLs
                url_display = info.source_url if len(info.source_url) <= 60 else info.source_url[:57] + "..."
                source_detail = f" ({url_display})"
            else:
                source_detail = ""

            elements.append(Paragraph(
                f"<b>Source: {source_label}{source_detail}</b>",
                self.styles['SubHeader']
            ))

            # Truncate very long content
            content = info.content or ""
            if len(content) > 2000:
                content = content[:2000] + "..."

            # Apply markdown formatting
            content_elements = markdown_to_elements(
                content,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
            elements.append(Spacer(1, 0.2*inch))

        return elements

    def _build_ideas_section(self, db_session: SessionModel) -> list:
        """Build the brainstorming ideas section."""
        elements = []

        elements.append(Paragraph("Appendix B: Brainstorming Session (6-3-5 Method)", self.styles['SectionHeader']))

        # Get participants
        participants = self.db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).all()

        if participants:
            participant_names = [p.name for p in participants]
            human_count = sum(1 for p in participants if p.connection_status != 'ai_controlled')
            ai_count = len(participants) - human_count

            elements.append(Paragraph(
                f"<b>Participants:</b> {len(participants)} total ({human_count} human, {ai_count} AI)",
                self.styles['ReportBody']
            ))
            elements.append(Spacer(1, 0.1*inch))

        # Get all ideas
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        all_ideas = []
        for sheet in sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
            for idea in ideas:
                participant = self.db.query(Participant).filter(
                    Participant.id == idea.participant_id
                ).first()
                all_ideas.append({
                    'content': idea.content,
                    'participant': participant.name if participant else 'Unknown',
                    'round': idea.round_number
                })

        if not all_ideas:
            elements.append(Paragraph(
                "No ideas were generated in the brainstorming session.",
                self.styles['ReportBody']
            ))
            return elements

        elements.append(Paragraph(
            f"<b>Total Ideas Generated:</b> {len(all_ideas)}",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.2*inch))

        # Group ideas by round
        ideas_by_round = {}
        for idea in all_ideas:
            r = idea['round']
            if r not in ideas_by_round:
                ideas_by_round[r] = []
            ideas_by_round[r].append(idea)

        for round_num in sorted(ideas_by_round.keys()):
            elements.append(Paragraph(f"Round {round_num}", self.styles['SubHeader']))

            for idea in ideas_by_round[round_num]:
                content = idea['content'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                elements.append(Paragraph(
                    f"- {content} <i>(by {idea['participant']})</i>",
                    self.styles['IdeaText']
                ))

            elements.append(Spacer(1, 0.1*inch))

        return elements

    def _build_prioritization_section(self, db_session: SessionModel) -> list:
        """Build the prioritization results section."""
        elements = []

        elements.append(Paragraph("Appendix C: Idea Prioritization Results", self.styles['SectionHeader']))

        # Get prioritization results
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        ranked_ideas = []
        for sheet in sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
            for idea in ideas:
                votes = self.db.query(Prioritization).filter(
                    Prioritization.idea_id == idea.id
                ).all()
                total_points = sum(v.score or 0 for v in votes)

                participant = self.db.query(Participant).filter(
                    Participant.id == idea.participant_id
                ).first()

                ranked_ideas.append({
                    'content': idea.content,
                    'participant': participant.name if participant else 'Unknown',
                    'points': total_points
                })

        # Sort by points
        ranked_ideas.sort(key=lambda x: x['points'], reverse=True)

        if not ranked_ideas or all(i['points'] == 0 for i in ranked_ideas):
            elements.append(Paragraph(
                "No prioritization votes were recorded.",
                self.styles['ReportBody']
            ))
            return elements

        # Create table for top ideas
        elements.append(Paragraph("Top Ranked Ideas:", self.styles['SubHeader']))

        table_data = [['Rank', 'Idea', 'Points']]
        for i, idea in enumerate(ranked_ideas[:10]):  # Top 10
            if idea['points'] == 0:
                continue
            content = idea['content'][:80] + '...' if len(idea['content']) > 80 else idea['content']
            table_data.append([str(i+1), content, str(idea['points'])])

        if len(table_data) > 1:
            table = Table(table_data, colWidths=[1*cm, 12*cm, 2*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            elements.append(table)

        return elements

    def _build_consultation_transcript(self, db_session: SessionModel) -> list:
        """Build the consultation conversation transcript for the appendix."""
        elements = []

        elements.append(Paragraph("Appendix D: Consultation Transcript", self.styles['SectionHeader']))

        # Filter for Step 4 (consultation) messages only
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role != 'system',
            (ConsultationMessage.message_type == 'consultation') | (ConsultationMessage.message_type.is_(None))
        ).order_by(ConsultationMessage.created_at).all()

        # Filter out the initial trigger message
        messages = [m for m in messages if m.content != "Please start the consultation."]

        if not messages:
            elements.append(Paragraph("No consultation conversation recorded.", self.styles['ReportBody']))
        else:
            elements.append(Paragraph(
                f"The following is the complete transcript of the AI consultation session ({len(messages)} messages).",
                self.styles['ReportBody']
            ))
            elements.append(Spacer(1, 0.2*inch))

            for msg in messages:
                content = msg.content

                if msg.role == 'user':
                    # User messages - simple formatting
                    content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    content = content.replace('\n', '<br/>')
                    elements.append(Paragraph(
                        f"<b>User:</b> {content}",
                        self.styles['ChatUser']
                    ))
                else:
                    # AI responses - apply markdown formatting
                    # Truncate very long AI responses
                    if len(content) > 1500:
                        content = content[:1500] + "..."

                    content = markdown_to_reportlab(content)
                    elements.append(Paragraph(
                        f"<b>Consultant:</b> {content}",
                        self.styles['ChatAssistant']
                    ))

        return elements

    def _build_business_case_transcript(self, db_session: SessionModel) -> list:
        """Build the business case conversation transcript for the appendix."""
        elements = []

        elements.append(Paragraph("Appendix E: Business Case Transcript", self.styles['SectionHeader']))

        # Filter for Step 5 (business_case) messages only
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role != 'system',
            ConsultationMessage.message_type == 'business_case'
        ).order_by(ConsultationMessage.created_at).all()

        # Filter out the initial trigger message
        messages = [m for m in messages if m.content != "Please start the business case analysis."]

        if not messages:
            elements.append(Paragraph("No business case conversation recorded.", self.styles['ReportBody']))
        else:
            elements.append(Paragraph(
                f"The following is the transcript of the business case analysis session ({len(messages)} messages).",
                self.styles['ReportBody']
            ))
            elements.append(Spacer(1, 0.2*inch))

            for msg in messages:
                content = msg.content

                if msg.role == 'user':
                    # User messages - simple formatting
                    content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    content = content.replace('\n', '<br/>')
                    elements.append(Paragraph(
                        f"<b>User:</b> {content}",
                        self.styles['ChatUser']
                    ))
                else:
                    # AI responses - apply markdown formatting
                    # Truncate very long AI responses
                    if len(content) > 1500:
                        content = content[:1500] + "..."

                    content = markdown_to_reportlab(content)
                    elements.append(Paragraph(
                        f"<b>Analyst:</b> {content}",
                        self.styles['ChatAssistant']
                    ))

        return elements

    def _build_recommendations_section(self, db_session: SessionModel) -> list:
        """Build the implementation recommendations section."""
        elements = []

        elements.append(Paragraph("Implementation Roadmap", self.styles['SectionHeader']))

        # Get project plan finding (CRISP-DM) or fall back to legacy implementation
        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_(['project_plan', 'implementation'])
        ).all()

        findings_dict = {f.factor_type: f.finding_text for f in findings}
        impl_content = findings_dict.get('project_plan') or findings_dict.get('implementation')

        if impl_content:
            content_elements = markdown_to_elements(
                impl_content,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph(
                "Complete the consultation and generate the summary to populate this section.",
                self.styles['ReportBody']
            ))

        elements.append(Spacer(1, 0.5*inch))

        # Next steps
        elements.append(Paragraph("Next Steps", self.styles['SubHeader']))
        next_steps = [
            "Review this report with key stakeholders",
            "Validate the identified user group and their needs",
            "Assess resources and budget for implementation",
            "Create a detailed project timeline",
            "Identify and mitigate key risks",
            "Begin with a pilot project or proof of concept"
        ]

        for step in next_steps:
            elements.append(Paragraph(f"- {step}", self.styles['IdeaText']))

        elements.append(Spacer(1, 0.5*inch))

        # Footer
        elements.append(Paragraph(
            "This report was generated by the AI & Digitalization Consultant application.",
            ParagraphStyle(
                'Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.gray,
                alignment=TA_CENTER
            )
        ))

        return elements
