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
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem, KeepTogether, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF
from sqlalchemy.orm import Session


class TOCEntry(Flowable):
    """A flowable that marks a TOC entry and notifies the document."""

    def __init__(self, text, level=0, style_name='TOCHeading'):
        Flowable.__init__(self)
        self.text = text
        self.level = level
        self.style_name = style_name

    def draw(self):
        pass  # Nothing to draw, this is just a marker

    def wrap(self, availWidth, availHeight):
        return (0, 0)  # Takes no space


class MyDocTemplate(BaseDocTemplate):
    """Custom document template that tracks TOC entries."""

    def __init__(self, filename, **kwargs):
        BaseDocTemplate.__init__(self, filename, **kwargs)
        self.toc_entries = []
        self.page_numbers = {}

    def afterFlowable(self, flowable):
        """Called after each flowable is rendered - track TOC entries."""
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            if style == 'SectionHeader':
                # Main section
                text = flowable.getPlainText()
                self.toc_entries.append((text, self.page, 0))
            elif style == 'AppendixHeader':
                # Appendix section
                text = flowable.getPlainText()
                self.toc_entries.append((text, self.page, 1))


def add_page_number(canvas, doc):
    """Add page number to the bottom center of each page (adjusted for title page offset)."""
    canvas.saveState()
    # Subtract 1 to account for title page (which has no number)
    page_num = canvas.getPageNumber() - 1
    if page_num > 0:  # Only show page number after title page
        text = f"Page {page_num}"
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.gray)
        canvas.drawCentredString(A4[0] / 2, 1.5 * cm, text)
    canvas.restoreState()


def no_page_number(canvas, doc):
    """Empty callback for pages without page numbers (title page)."""
    pass

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

    # Convert headers to bold (process longer patterns first to avoid partial matches)
    text = re.sub(r'^####\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s*(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

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

        def build_story_without_toc():
            """Build the main content story (without TOC placeholder)."""
            story = []

            # Company Profile Summary (main body)
            story.append(PageBreak())
            story.extend(self._build_company_profile_summary(db_session))

            # Main Results Section: Executive Summary
            story.append(PageBreak())
            story.extend(self._build_executive_summary(db_session))

            # Business Case Section (Step 5a)
            story.append(PageBreak())
            story.extend(self._build_business_case_section(db_session))

            # Cost Estimation Section (Step 5b)
            story.append(PageBreak())
            story.extend(self._build_cost_estimation_section(db_session))

            # Implementation Roadmap
            story.append(PageBreak())
            story.extend(self._build_recommendations_section(db_session))

            # SWOT Analysis
            story.append(PageBreak())
            story.extend(self._build_swot_section(db_session))

            # Technical Transition Briefing
            story.append(PageBreak())
            story.extend(self._build_technical_briefing_section(db_session))

            # Appendix header
            story.append(PageBreak())
            story.extend(self._build_appendix_header())

            # Appendix A: Company Overview
            story.extend(self._build_company_section(db_session))

            # Appendix B: Brainstorming Ideas
            story.append(PageBreak())
            story.extend(self._build_ideas_section(db_session))

            # Appendix C: Prioritization Results
            story.append(PageBreak())
            story.extend(self._build_prioritization_section(db_session))

            # Appendix D: Consultation Conversation
            story.append(PageBreak())
            story.extend(self._build_consultation_transcript(db_session))

            # Appendix E: Business Case Conversation
            story.append(PageBreak())
            story.extend(self._build_business_case_transcript(db_session))

            # Appendix F: Cost Estimation Conversation
            story.append(PageBreak())
            story.extend(self._build_cost_estimation_transcript(db_session))

            return story

        # PASS 1: Build document to capture page numbers
        buffer1 = io.BytesIO()
        doc1 = MyDocTemplate(
            buffer1,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Create page template with frame and page numbers
        frame = Frame(
            doc1.leftMargin, doc1.bottomMargin + 0.5*cm,  # Add space for page number
            doc1.width, doc1.height - 0.5*cm,
            id='normal'
        )
        doc1.addPageTemplates([PageTemplate(id='main', frames=frame, onPage=add_page_number)])

        # Build first pass with title + placeholder TOC + content
        story1 = []
        story1.extend(self._build_title_page(db_session))
        story1.append(PageBreak())
        story1.extend(self._build_table_of_contents({}))  # Empty TOC for first pass
        story1.extend(build_story_without_toc())

        doc1.build(story1)
        buffer1.close()

        # Extract page numbers from first pass (subtract 1 to account for unnumbered title page)
        page_numbers = {}
        for entry_text, page_num, level in doc1.toc_entries:
            page_numbers[entry_text] = page_num - 1  # Adjust for title page offset

        # PASS 2: Build final document with page numbers in TOC
        buffer2 = io.BytesIO()
        doc2 = MyDocTemplate(
            buffer2,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        doc2.addPageTemplates([PageTemplate(id='main', frames=Frame(
            doc2.leftMargin, doc2.bottomMargin + 0.5*cm,  # Add space for page number
            doc2.width, doc2.height - 0.5*cm,
            id='normal'
        ), onPage=add_page_number)])

        story2 = []
        story2.extend(self._build_title_page(db_session))
        story2.append(PageBreak())
        story2.extend(self._build_table_of_contents(page_numbers))
        story2.extend(build_story_without_toc())

        doc2.build(story2)

        # Get PDF bytes
        pdf_bytes = buffer2.getvalue()
        buffer2.close()

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

    def _build_table_of_contents(self, page_numbers: dict) -> list:
        """Build the table of contents page with page numbers."""
        elements = []

        # TOC Header
        elements.append(Paragraph("Table of Contents", self.styles['Title1']))
        elements.append(Spacer(1, 0.5*inch))

        # Define TOC entries: (number, display_title, lookup_title, section_type)
        # lookup_title must match the exact text used in SectionHeader paragraphs
        toc_entries = [
            ("1.", "Company Profile and Maturity Assessment", "1. Company Profile and Maturity Assessment", "Main Report"),
            ("2.", "Executive Summary", "2. Executive Summary", "Main Report"),
            ("3.", "Business Case Indication", "3. Business Case Indication", "Main Report"),
            ("4.", "Cost Estimation", "4. Cost Estimation", "Main Report"),
            ("5.", "Implementation Roadmap", "5. Implementation Roadmap", "Main Report"),
            ("6.", "SWOT Analysis", "6. SWOT Analysis", "Main Report"),
            ("7.", "Technical Transition Briefing", "7. Technical Transition Briefing", "Main Report"),
            ("", "", "", ""),  # Spacer
            ("A.", "Company Profile & Maturity", "Appendix A: Company Profile & Maturity Assessment", "Appendix"),
            ("B.", "Brainstorming Session", "Appendix B: Brainstorming Session (6-3-5 Method)", "Appendix"),
            ("C.", "Prioritization Results", "Appendix C: Idea Prioritization Results", "Appendix"),
            ("D.", "Consultation Transcript", "Appendix D: Consultation Transcript", "Appendix"),
            ("E.", "Business Case Transcript", "Appendix E: Business Case Transcript", "Appendix"),
            ("F.", "Cost Estimation Transcript", "Appendix F: Cost Estimation Transcript", "Appendix"),
        ]

        # Create TOC styles
        toc_section_style = ParagraphStyle(
            'TOCSection',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            spaceBefore=12,
            spaceAfter=4
        )

        toc_entry_style = ParagraphStyle(
            'TOCEntryText',
            parent=self.styles['Normal'],
            fontSize=11,
        )

        toc_page_style = ParagraphStyle(
            'TOCPageNum',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_RIGHT
        )

        current_section = None
        toc_data = []

        for number, display_title, lookup_title, section_type in toc_entries:
            if not display_title:  # Spacer entry
                if toc_data:
                    # Build table for current section
                    elements.extend(self._build_toc_table(toc_data, toc_entry_style, toc_page_style))
                    toc_data = []
                elements.append(Spacer(1, 0.15*inch))
                current_section = None
                continue

            # Add section header if changed
            if section_type != current_section:
                if toc_data:
                    elements.extend(self._build_toc_table(toc_data, toc_entry_style, toc_page_style))
                    toc_data = []
                elements.append(Paragraph(f"<b>{section_type}</b>", toc_section_style))
                current_section = section_type

            # Look up page number
            page_num = page_numbers.get(lookup_title, "")

            # Add entry
            toc_data.append((number, display_title, str(page_num) if page_num else ""))

        # Build remaining entries
        if toc_data:
            elements.extend(self._build_toc_table(toc_data, toc_entry_style, toc_page_style))

        return elements

    def _build_toc_table(self, toc_data: list, entry_style, page_style) -> list:
        """Build a table for TOC entries with dot leaders."""
        elements = []

        for number, title, page_num in toc_data:
            # Create a row with number+title on left, dots in middle, page on right
            entry_text = f"<b>{number}</b>&nbsp;&nbsp;{title}"

            # Use a table for proper alignment
            row = [
                Paragraph(entry_text, entry_style),
                Paragraph(page_num, page_style)
            ]

            # Calculate widths (total width ~16cm)
            table = Table([row], colWidths=[14*cm, 2*cm])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(table)

        return elements

        return elements

    def _build_company_profile_summary(self, db_session: SessionModel) -> list:
        """Build the company profile summary section for the main body."""
        elements = []

        elements.append(Paragraph("1. Company Profile and Maturity Assessment", self.styles['SectionHeader']))
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

                for info in company_infos:
                    source_label = info.info_type.upper() if info.info_type else "TEXT"
                    content = info.content or ""

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
        """Build the executive summary with key findings, business case, ROI, and recommendation."""
        elements = []

        elements.append(Paragraph("2. Executive Summary", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))

        # Get all findings
        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id
        ).all()

        findings_dict = {f.factor_type: f.finding_text for f in findings}

        # Get top idea for context
        from ..models import IdeaSheet, Idea, Prioritization
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        top_idea = None
        if sheets:
            all_ideas = []
            for sheet in sheets:
                ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
                for idea in ideas:
                    votes = self.db.query(Prioritization).filter(
                        Prioritization.idea_id == idea.id
                    ).all()
                    total_points = sum(v.score or 0 for v in votes)
                    all_ideas.append({'content': idea.content, 'points': total_points})
            if all_ideas:
                all_ideas.sort(key=lambda x: x['points'], reverse=True)
                top_idea = all_ideas[0]['content'] if all_ideas[0]['points'] > 0 else all_ideas[0]['content']

        # ============================================================
        # USE CASE OVERVIEW (at the very top)
        # ============================================================
        elements.append(Paragraph("Use Case Overview", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Build use case description from top idea and AI goals
        use_case_parts = []

        if top_idea:
            use_case_parts.append(f"<b>Selected Project:</b> {top_idea}")

        if findings_dict.get('ai_goals'):
            ai_goals = findings_dict['ai_goals']
            use_case_parts.append(f"<b>AI/Data Mining Objectives:</b> {ai_goals}")

        if use_case_parts:
            use_case_text = "<br/><br/>".join(use_case_parts)
        else:
            use_case_text = "No specific use case has been defined yet. Complete the brainstorming and consultation steps to define the project scope."

        use_case_style = ParagraphStyle(
            'UseCaseText',
            parent=self.styles['ReportBody'],
            fontSize=10,
            leading=14,
        )

        use_case_table = Table(
            [[Paragraph(use_case_text, use_case_style)]],
            colWidths=[15*cm]
        )
        use_case_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#16a34a')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(use_case_table)
        elements.append(Spacer(1, 0.3*inch))

        # ============================================================
        # RECOMMENDATION BOX (prominent at the top)
        # ============================================================
        elements.append(Paragraph("Recommendation", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Build recommendation based on available data
        recommendation = self._generate_recommendation(findings_dict, top_idea, db_session.company_name)

        rec_style = ParagraphStyle(
            'RecommendationText',
            parent=self.styles['ReportBody'],
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#1a365d')
        )

        rec_table = Table(
            [[Paragraph(recommendation, rec_style)]],
            colWidths=[15*cm]
        )
        rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ebf8ff')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#3182ce')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(rec_table)
        elements.append(Spacer(1, 0.3*inch))

        # ============================================================
        # BUSINESS CASE OVERVIEW (Key metrics at a glance)
        # ============================================================
        elements.append(Paragraph("Business Case Overview", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Create styled sections for each metric with proper table rendering
        has_overview_data = False

        # Focus Project
        if top_idea:
            has_overview_data = True
            elements.extend(self._build_overview_item(
                "Focus Project",
                top_idea,
                colors.HexColor('#2563eb'),  # Blue
                colors.HexColor('#eff6ff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Value Classification
        if findings_dict.get('business_case_classification'):
            has_overview_data = True
            elements.extend(self._build_overview_item(
                "Value Classification",
                findings_dict['business_case_classification'],
                colors.HexColor('#7c3aed'),  # Purple
                colors.HexColor('#f5f3ff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Estimated Benefits
        if findings_dict.get('business_case_calculation'):
            has_overview_data = True
            elements.extend(self._build_overview_item(
                "Estimated Benefits",
                findings_dict['business_case_calculation'],
                colors.HexColor('#059669'),  # Green
                colors.HexColor('#ecfdf5')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Project Complexity
        if findings_dict.get('cost_complexity'):
            has_overview_data = True
            elements.extend(self._build_overview_item(
                "Project Complexity",
                findings_dict['cost_complexity'],
                colors.HexColor('#d97706'),  # Amber
                colors.HexColor('#fffbeb')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Investment Required
        if findings_dict.get('cost_initial'):
            has_overview_data = True
            elements.extend(self._build_overview_item(
                "Initial Investment",
                findings_dict['cost_initial'],
                colors.HexColor('#dc2626'),  # Red
                colors.HexColor('#fef2f2')
            ))

        if not has_overview_data:
            elements.append(Paragraph(
                "Complete Steps 4 and 5 to generate a business case overview.",
                self.styles['ReportBody']
            ))

        elements.append(Spacer(1, 0.3*inch))

        # ============================================================
        # ROI CALCULATION SUMMARY
        # ============================================================
        elements.append(Paragraph("ROI & Investment Analysis", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        has_roi_data = (
            findings_dict.get('cost_tco') or
            findings_dict.get('cost_roi') or
            findings_dict.get('business_case_calculation')
        )

        if has_roi_data:
            roi_elements = []

            # TCO Summary
            if findings_dict.get('cost_tco'):
                roi_elements.append([
                    Paragraph("<b>3-Year TCO:</b>", self.styles['ReportBody']),
                    Paragraph(markdown_to_reportlab(findings_dict['cost_tco']), self.styles['ReportBody'])
                ])

            # ROI Analysis
            if findings_dict.get('cost_roi'):
                roi_elements.append([
                    Paragraph("<b>ROI Analysis:</b>", self.styles['ReportBody']),
                    Paragraph(markdown_to_reportlab(findings_dict['cost_roi']), self.styles['ReportBody'])
                ])

            # Benefits vs. Costs comparison
            if findings_dict.get('business_case_calculation') and findings_dict.get('cost_tco'):
                roi_elements.append([
                    Paragraph("<b>Benefits:</b>", self.styles['ReportBody']),
                    Paragraph(markdown_to_reportlab(findings_dict['business_case_calculation']), self.styles['ReportBody'])
                ])

            if roi_elements:
                roi_table = Table(roi_elements, colWidths=[4*cm, 11*cm])
                roi_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#c6f6d5')),
                    ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#f0fff4')),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#48bb78')),
                    ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#9ae6b4')),
                ]))
                elements.append(roi_table)
        else:
            elements.append(Paragraph(
                "Complete Step 5b (Cost Estimation) to generate ROI analysis.",
                self.styles['ReportBody']
            ))

        elements.append(Spacer(1, 0.3*inch))

        # ============================================================
        # KEY FINDINGS (CRISP-DM - full content)
        # ============================================================
        elements.append(Paragraph("Key Findings", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        has_findings = False

        # Business Objectives
        if findings_dict.get('business_objectives'):
            has_findings = True
            elements.extend(self._build_overview_item(
                "Business Objectives",
                findings_dict['business_objectives'],
                colors.HexColor('#0369a1'),  # Sky blue
                colors.HexColor('#f0f9ff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Situation Assessment
        if findings_dict.get('situation_assessment'):
            has_findings = True
            elements.extend(self._build_overview_item(
                "Situation Assessment",
                findings_dict['situation_assessment'],
                colors.HexColor('#4f46e5'),  # Indigo
                colors.HexColor('#eef2ff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # AI/Technical Goals
        if findings_dict.get('ai_goals'):
            has_findings = True
            elements.extend(self._build_overview_item(
                "AI/Data Mining Goals",
                findings_dict['ai_goals'],
                colors.HexColor('#7c3aed'),  # Violet
                colors.HexColor('#f5f3ff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        # Implementation Plan
        if findings_dict.get('project_plan'):
            has_findings = True
            elements.extend(self._build_overview_item(
                "Project Plan",
                findings_dict['project_plan'],
                colors.HexColor('#0891b2'),  # Cyan
                colors.HexColor('#ecfeff')
            ))
            elements.append(Spacer(1, 0.15*inch))

        if not has_findings:
            elements.append(Paragraph(
                "Complete Step 4 (Consultation) to document key findings.",
                self.styles['ReportBody']
            ))

        elements.append(Spacer(1, 0.2*inch))

        # Management Pitch (if available)
        if findings_dict.get('business_case_pitch'):
            elements.append(Paragraph("Management Pitch", self.styles['SubHeader']))
            elements.append(Spacer(1, 0.1*inch))

            pitch = findings_dict['business_case_pitch']
            pitch_clean = pitch.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            pitch_table = Table(
                [[Paragraph(f"<i>\"{pitch_clean}\"</i>",
                    ParagraphStyle('Pitch', parent=self.styles['ReportBody'],
                                   fontSize=11, textColor=colors.HexColor('#2c5282')))]],
                colWidths=[15*cm]
            )
            pitch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#bee3f8')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#3182ce')),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(pitch_table)

        return elements

    def _generate_recommendation(self, findings_dict: dict, top_idea: str, company_name: str) -> str:
        """Generate a recommendation based on available findings."""
        parts = []

        # Determine recommendation type based on data completeness
        has_business_case = findings_dict.get('business_case_classification') or findings_dict.get('business_case_calculation')
        has_costs = findings_dict.get('cost_tco') or findings_dict.get('cost_initial')
        has_roi = findings_dict.get('cost_roi')
        has_objectives = findings_dict.get('business_objectives')

        company = company_name or "the organization"

        if has_business_case and has_costs and has_roi:
            # Full data available - strong recommendation
            parts.append(f"<b>Based on the comprehensive analysis conducted, we recommend {company} proceed with the proposed AI initiative.</b>")
            parts.append("<br/><br/>")
            parts.append("The business case demonstrates clear value potential, and the cost estimation provides a realistic investment framework. ")

            if findings_dict.get('cost_complexity'):
                complexity = findings_dict['cost_complexity'].lower()
                if 'quick win' in complexity:
                    parts.append("As a <b>Quick Win</b> project, this initiative offers low risk and rapid time-to-value. ")
                elif 'standard' in complexity:
                    parts.append("As a <b>Standard</b> complexity project, this initiative balances ambition with manageable risk. ")
                elif 'complex' in complexity or 'enterprise' in complexity:
                    parts.append("Given the project's complexity, we recommend a phased approach starting with a pilot. ")

            parts.append("<br/><br/>")
            parts.append("<b>Next Steps:</b> Validate assumptions with stakeholders, secure budget approval, and initiate the pilot phase.")

        elif has_business_case and has_costs:
            # Business case and costs but no ROI
            parts.append(f"<b>The analysis indicates a viable AI opportunity for {company}.</b>")
            parts.append("<br/><br/>")
            parts.append("A clear business case has been established with cost estimates. We recommend conducting a detailed ROI analysis to strengthen the investment justification before proceeding.")

        elif has_business_case:
            # Only business case
            parts.append(f"<b>The identified AI opportunity shows promise for {company}.</b>")
            parts.append("<br/><br/>")
            parts.append("The business case indicates potential value. We recommend completing the cost estimation (Step 5b) to understand the investment requirements before making a go/no-go decision.")

        elif has_objectives and top_idea:
            # Only objectives and idea
            parts.append(f"<b>An AI opportunity has been identified for {company}.</b>")
            parts.append("<br/><br/>")
            parts.append(f"The focus project \"{top_idea}\" aligns with documented business objectives. ")
            parts.append("We recommend completing the business case analysis (Step 5a) and cost estimation (Step 5b) to evaluate feasibility.")

        else:
            # Minimal data
            parts.append(f"<b>This report documents the initial AI/digitalization exploration for {company}.</b>")
            parts.append("<br/><br/>")
            parts.append("To generate a complete recommendation, please ensure all consultation phases are completed, including business case analysis and cost estimation.")

        return "".join(parts)

    def _build_business_case_section(self, db_session: SessionModel) -> list:
        """Build the business case indication section (Step 5) with graphical elements."""
        elements = []

        elements.append(Paragraph("3. Business Case Indication", self.styles['SectionHeader']))
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
        """Build the company overview and maturity assessment section."""
        from ..models import MaturityAssessment

        elements = []

        elements.append(Paragraph("Appendix A: Company Profile & Maturity Assessment", self.styles['SectionHeader']))

        # --- Part 1: Company Information ---
        elements.append(Paragraph("<b>Company Information</b>", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Get company info
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()

        if not company_infos:
            elements.append(Paragraph(
                "No company information was provided.",
                self.styles['ReportBody']
            ))
        else:
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
                    ParagraphStyle('SourceLabel', parent=self.styles['Normal'], fontSize=10, textColor=colors.HexColor('#4a5568'))
                ))

                # Full content (no truncation in appendix)
                content = info.content or ""

                # Apply markdown formatting
                content_elements = markdown_to_elements(
                    content,
                    self.styles['ReportBody'],
                    self.styles['IdeaText']
                )
                elements.extend(content_elements)
                elements.append(Spacer(1, 0.2*inch))

        # --- Part 2: Digital Maturity Assessment ---
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<b>Digital Maturity Assessment</b>", self.styles['SubHeader']))
        elements.append(Paragraph(
            "Assessment based on the Acatech Industry 4.0 Maturity Index (scale 1-6).",
            ParagraphStyle('MaturityIntro', parent=self.styles['ReportBody'], fontSize=9, textColor=colors.gray)
        ))
        elements.append(Spacer(1, 0.15*inch))

        # Get maturity assessment
        maturity = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == db_session.id
        ).first()

        if not maturity:
            elements.append(Paragraph(
                "<i>No maturity assessment has been completed for this session.</i>",
                ParagraphStyle('MaturityPlaceholder', parent=self.styles['ReportBody'],
                              textColor=colors.gray, alignment=TA_CENTER)
            ))
        else:
            import json

            # Maturity level descriptions
            level_descriptions = {
                1: ("Computerization", "Basic IT systems, isolated digital solutions"),
                2: ("Connectivity", "Connected systems, basic data exchange"),
                3: ("Visibility", "Real-time data capture, digital shadow of operations"),
                4: ("Transparency", "Data analysis for understanding root causes"),
                5: ("Predictive Capacity", "Simulation and prediction of future scenarios"),
                6: ("Adaptability", "Automated adaptation and self-optimization"),
            }

            # Question texts for each dimension
            dimension_questions = {
                "resources": {
                    "title": "Resources",
                    "description": "Digital capability of workforce, equipment, materials, and tools",
                    "questions": {
                        "q1": "How digitally skilled is your workforce?",
                        "q2": "How connected and smart are your equipment and machines?",
                        "q3": "How well are your materials and inventory tracked digitally?",
                        "q4": "How advanced are your digital tools and software?"
                    }
                },
                "information_systems": {
                    "title": "Information Systems",
                    "description": "Integration of IT systems and data processing capabilities",
                    "questions": {
                        "q1": "How integrated are your IT systems?",
                        "q2": "How accessible is your business data?",
                        "q3": "How automated is your data collection?",
                        "q4": "How advanced is your data analysis?"
                    }
                },
                "culture": {
                    "title": "Culture",
                    "description": "Organizational readiness for digital transformation",
                    "questions": {
                        "q1": "How open is your organization to change?",
                        "q2": "How well does knowledge flow across departments?",
                        "q3": "How is failure treated?",
                        "q4": "How committed is leadership to digitalization?"
                    }
                },
                "organizational_structure": {
                    "title": "Organizational Structure",
                    "description": "Agility, collaboration, and decision-making processes",
                    "questions": {
                        "q1": "How agile are your teams?",
                        "q2": "How fast can you make decisions?",
                        "q3": "How do teams collaborate across functions?",
                        "q4": "How quickly can you adapt to market changes?"
                    }
                }
            }

            def get_score_color(score):
                if score < 2:
                    return colors.HexColor('#ef4444')
                elif score < 3:
                    return colors.HexColor('#f97316')
                elif score < 4:
                    return colors.HexColor('#eab308')
                elif score < 5:
                    return colors.HexColor('#84cc16')
                else:
                    return colors.HexColor('#22c55e')

            # Overall Score
            overall_score = maturity.overall_score or 0
            maturity_level_name = maturity.maturity_level or "Unknown"

            overall_bar_data = [
                [
                    Paragraph(f"<b>Overall: {maturity_level_name}</b>",
                             ParagraphStyle('OverallLabel', fontSize=10, alignment=TA_LEFT)),
                    self._create_maturity_bar(overall_score, width=9*cm, height=0.5*cm),
                    Paragraph(f"<b>{overall_score:.1f}</b>/6",
                             ParagraphStyle('OverallScore', fontSize=10, alignment=TA_RIGHT))
                ]
            ]
            overall_table = Table(overall_bar_data, colWidths=[4.5*cm, 9.2*cm, 1.5*cm])
            overall_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(overall_table)
            elements.append(Spacer(1, 0.2*inch))

            # Dimension details with questions
            dimension_data = [
                ("resources", maturity.resources_score, maturity.resources_details),
                ("information_systems", maturity.information_systems_score, maturity.information_systems_details),
                ("culture", maturity.culture_score, maturity.culture_details),
                ("organizational_structure", maturity.organizational_structure_score, maturity.organizational_structure_details),
            ]

            for dim_key, dim_score, dim_details_json in dimension_data:
                dim_config = dimension_questions[dim_key]
                score = dim_score or 0

                # Dimension header with bar
                dim_header_data = [
                    [
                        Paragraph(f"<b>{dim_config['title']}</b>",
                                 ParagraphStyle('DimHeader', fontSize=10, alignment=TA_LEFT)),
                        self._create_maturity_bar(score, width=8*cm, height=0.4*cm),
                        Paragraph(f"<b>{score:.1f}</b>",
                                 ParagraphStyle('DimScore', fontSize=10, alignment=TA_RIGHT))
                    ]
                ]
                dim_header_table = Table(dim_header_data, colWidths=[5*cm, 8.2*cm, 1.5*cm])
                dim_header_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(dim_header_table)

                # Description
                elements.append(Paragraph(
                    f"<i>{dim_config['description']}</i>",
                    ParagraphStyle('DimDesc', fontSize=8, textColor=colors.gray, leftIndent=5)
                ))

                # Parse details JSON
                details = {}
                if dim_details_json:
                    try:
                        details = json.loads(dim_details_json) if isinstance(dim_details_json, str) else dim_details_json
                    except:
                        pass

                # Question scores
                question_data = []
                for q_key, q_text in dim_config['questions'].items():
                    q_score = details.get(q_key, 0)
                    question_data.append([
                        Paragraph(q_text, ParagraphStyle('QText', fontSize=8, leftIndent=10)),
                        self._create_maturity_bar(q_score, width=5*cm, height=0.3*cm),
                        Paragraph(f"{q_score:.0f}", ParagraphStyle('QScore', fontSize=8, alignment=TA_RIGHT))
                    ])

                if question_data:
                    q_table = Table(question_data, colWidths=[8.5*cm, 5.2*cm, 1*cm])
                    q_table.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    elements.append(q_table)

                elements.append(Spacer(1, 0.15*inch))

            # Legend
            elements.append(Paragraph("<b>Maturity Levels:</b>", ParagraphStyle('LegendTitle', fontSize=8)))
            legend_text = " | ".join([f"<b>{lvl}</b> {name}" for lvl, (name, _) in level_descriptions.items()])
            elements.append(Paragraph(
                legend_text,
                ParagraphStyle('LegendText', fontSize=7, textColor=colors.gray)
            ))

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
        for i, idea in enumerate(ranked_ideas):
            if idea['points'] == 0:
                continue
            content = idea['content']
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

    def _is_prompt_message(self, content: str, role: str = None) -> bool:
        """Check if a message looks like a system prompt or context injection."""
        if not content:
            return False

        content_lower = content.lower().strip()

        # Only filter user messages that look like context injections
        # AI/assistant responses should not be filtered
        if role == 'assistant':
            return False

        # Exact trigger messages to filter
        trigger_messages = [
            "please start the consultation.",
            "please start the business case analysis.",
            "please start the cost estimation analysis.",
            "please begin the consultation.",
            "please begin the analysis.",
            "start the consultation",
            "start the analysis",
        ]

        for trigger in trigger_messages:
            if content_lower == trigger or content_lower.startswith(trigger):
                return True

        # Filter context injections (usually long user messages with context headers)
        context_indicators = [
            "## context",
            "## session context",
            "## company information",
            "## maturity assessment",
            "## instructions",
            "### company profile",
            "### digital maturity",
            "### brainstorming ideas",
        ]

        for indicator in context_indicators:
            if indicator in content_lower[:500]:
                return True

        # Filter very long user messages that look like context dumps
        if role == 'user' and len(content) > 1500:
            # Check if it contains multiple context sections
            section_count = content_lower.count('##')
            if section_count >= 3:
                return True

        return False

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

        # Filter out trigger messages and prompt-like content
        messages = [m for m in messages if not self._is_prompt_message(m.content, m.role)]

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
                    # AI responses - apply markdown formatting (no truncation)
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

        # Filter out trigger messages and prompt-like content
        messages = [m for m in messages if not self._is_prompt_message(m.content, m.role)]

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
                    # AI responses - apply markdown formatting (no truncation)
                    content = markdown_to_reportlab(content)
                    elements.append(Paragraph(
                        f"<b>Analyst:</b> {content}",
                        self.styles['ChatAssistant']
                    ))

        return elements

    def _build_cost_estimation_section(self, db_session: SessionModel) -> list:
        """Build the cost estimation section (Step 5b) with visual elements."""
        elements = []

        elements.append(Paragraph("4. Cost Estimation", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "This section presents the cost analysis and investment projection for the proposed AI project.",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Get cost estimation findings
        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                'cost_complexity',
                'cost_initial',
                'cost_recurring',
                'cost_maintenance',
                'cost_tco',
                'cost_drivers',
                'cost_optimization',
                'cost_roi'
            ])
        ).all()

        findings_dict = {f.factor_type: f.finding_text for f in findings}

        # Check if any cost estimation findings exist
        if not findings_dict:
            elements.append(Paragraph(
                "No cost estimation was completed. Complete Step 5b to populate this section.",
                self.styles['ReportBody']
            ))
            return elements

        # 1. Complexity Assessment with Visual Framework
        elements.append(Paragraph("Project Complexity Assessment", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('cost_complexity'):
            elements.extend(self._build_complexity_visual(findings_dict['cost_complexity']))
        else:
            elements.append(Paragraph("Not yet assessed.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.3*inch))

        # 2. Initial Investment
        elements.append(Paragraph("Initial Investment", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('cost_initial'):
            elements.extend(self._build_cost_box(
                "One-Time Investment",
                findings_dict['cost_initial'],
                colors.HexColor('#276749'),  # Green
                colors.HexColor('#c6f6d5')
            ))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 3. Recurring Costs
        elements.append(Paragraph("Recurring Costs", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('cost_recurring'):
            elements.extend(self._build_cost_box(
                "Monthly/Annual Recurring Costs",
                findings_dict['cost_recurring'],
                colors.HexColor('#2b6cb0'),  # Blue
                colors.HexColor('#bee3f8')
            ))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 4. Total Cost of Ownership (TCO)
        elements.append(Paragraph("3-Year Total Cost of Ownership (TCO)", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        if findings_dict.get('cost_tco'):
            elements.extend(self._build_tco_summary(findings_dict['cost_tco']))
        else:
            elements.append(Paragraph("Not yet calculated.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.3*inch))

        # 5. Cost Drivers
        if findings_dict.get('cost_drivers'):
            elements.append(Paragraph("Key Cost Drivers", self.styles['SubHeader']))
            elements.append(Spacer(1, 0.1*inch))
            content_elements = markdown_to_elements(
                findings_dict['cost_drivers'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
            elements.append(Spacer(1, 0.2*inch))

        # 6. Cost Optimization
        if findings_dict.get('cost_optimization'):
            elements.append(Paragraph("Cost Optimization Options", self.styles['SubHeader']))
            elements.append(Spacer(1, 0.1*inch))
            content_elements = markdown_to_elements(
                findings_dict['cost_optimization'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
            elements.append(Spacer(1, 0.2*inch))

        # 7. Investment vs. Return (ROI)
        if findings_dict.get('cost_roi'):
            elements.append(Paragraph("Investment vs. Return Analysis", self.styles['SubHeader']))
            elements.append(Spacer(1, 0.1*inch))
            elements.extend(self._build_roi_callout(findings_dict['cost_roi']))

        return elements

    def _build_complexity_visual(self, complexity_text: str) -> list:
        """Build a visual representation of the project complexity level."""
        elements = []

        # Define complexity levels
        levels = [
            ("Quick Win", "2-4 weeks", "€5k - €15k", colors.HexColor('#48bb78')),
            ("Standard", "1-3 months", "€15k - €50k", colors.HexColor('#4299e1')),
            ("Complex", "3-6 months", "€50k - €150k", colors.HexColor('#ed8936')),
            ("Enterprise", "6-12 months", "€150k+", colors.HexColor('#e53e3e')),
        ]

        # Detect which level is mentioned
        text_lower = complexity_text.lower()
        detected_level = None
        for i, (level_name, _, _, _) in enumerate(levels):
            if level_name.lower() in text_lower:
                detected_level = i
                break

        # Build table rows
        table_data = []
        for i, (level_name, duration, cost_range, base_color) in enumerate(levels):
            is_selected = (detected_level == i)

            if is_selected:
                indicator = Paragraph(
                    "<b>&rarr;</b>",
                    ParagraphStyle('Arrow', fontSize=14, textColor=colors.HexColor('#276749'), alignment=TA_CENTER)
                )
                bg_color = colors.HexColor('#c6f6d5')
                text_color = colors.HexColor('#22543d')
            else:
                indicator = Paragraph("", ParagraphStyle('Empty', fontSize=10))
                bg_color = colors.HexColor('#f7fafc')
                text_color = colors.HexColor('#718096')

            name_cell = Paragraph(
                f"<b>{level_name}</b>",
                ParagraphStyle('Name', fontSize=10, textColor=text_color)
            )
            duration_cell = Paragraph(
                duration,
                ParagraphStyle('Duration', fontSize=9, textColor=text_color, alignment=TA_CENTER)
            )
            cost_cell = Paragraph(
                cost_range,
                ParagraphStyle('Cost', fontSize=9, textColor=text_color, alignment=TA_CENTER)
            )

            table_data.append([indicator, name_cell, duration_cell, cost_cell])

        # Create table
        complexity_table = Table(
            table_data,
            colWidths=[0.8*cm, 3*cm, 3*cm, 4*cm]
        )

        # Apply styling
        style_commands = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ]

        for i, (_, _, _, base_color) in enumerate(levels):
            is_selected = (detected_level == i)
            if is_selected:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#c6f6d5')))
            else:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f7fafc')))

        complexity_table.setStyle(TableStyle(style_commands))
        elements.append(complexity_table)
        elements.append(Spacer(1, 0.2*inch))

        # Add complexity analysis text
        if complexity_text:
            analysis_table = Table(
                [[Paragraph(
                    f"<b>Analysis:</b><br/>{markdown_to_reportlab(complexity_text)}",
                    ParagraphStyle('AnalysisBox', parent=self.styles['ReportBody'], fontSize=9, leading=12)
                )]],
                colWidths=[15*cm]
            )
            analysis_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f8')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(analysis_table)

        return elements

    def _build_overview_item(self, title: str, content: str, header_color, bg_color) -> list:
        """Build a styled overview item with proper table rendering for Executive Summary."""
        elements = []

        header_style = ParagraphStyle(
            'OverviewHeader',
            parent=self.styles['ReportBody'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_LEFT
        )

        # Header row
        header_table = Table(
            [[Paragraph(f"<b>{title}</b>", header_style)]],
            colWidths=[15*cm]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), header_color),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)

        # Parse content for tables and text (reuse the cost content parser)
        content_elements = self._parse_cost_content(content, header_color, bg_color)
        elements.extend(content_elements)

        return elements

    def _build_cost_box(self, title: str, content: str, header_color, bg_color) -> list:
        """Build a styled cost box with header and content, with proper table rendering."""
        elements = []

        header_style = ParagraphStyle(
            'CostHeader',
            parent=self.styles['ReportBody'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_LEFT
        )

        # Header row
        header_table = Table(
            [[Paragraph(f"<b>{title}</b>", header_style)]],
            colWidths=[15*cm]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), header_color),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(header_table)

        # Parse content for tables and text
        content_elements = self._parse_cost_content(content, header_color, bg_color)
        elements.extend(content_elements)

        return elements

    def _parse_cost_content(self, content: str, header_color, bg_color) -> list:
        """Parse cost content and render tables properly."""
        elements = []

        content_style = ParagraphStyle(
            'CostContent',
            parent=self.styles['ReportBody'],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#2d3748')
        )

        # Split content into sections (tables vs text)
        lines = content.split('\n')
        current_text = []
        current_table = []
        in_table = False

        for line in lines:
            # Check if this is a table row (starts with |)
            if line.strip().startswith('|') and '|' in line.strip()[1:]:
                if current_text and not in_table:
                    # Flush accumulated text
                    text = '\n'.join(current_text).strip()
                    if text:
                        elements.append(self._create_text_box(text, content_style, bg_color, header_color))
                    current_text = []
                in_table = True
                # Skip separator rows (|---|---|)
                if not re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                    current_table.append(line)
            else:
                if in_table and current_table:
                    # Flush accumulated table
                    elements.append(self._create_markdown_table(current_table, header_color, bg_color))
                    current_table = []
                in_table = False
                current_text.append(line)

        # Flush remaining content
        if current_table:
            elements.append(self._create_markdown_table(current_table, header_color, bg_color))
        if current_text:
            text = '\n'.join(current_text).strip()
            if text:
                elements.append(self._create_text_box(text, content_style, bg_color, header_color))

        return elements

    def _create_text_box(self, text: str, style, bg_color, border_color) -> Table:
        """Create a styled text box."""
        content_para = Paragraph(markdown_to_reportlab(text), style)
        content_table = Table([[content_para]], colWidths=[15*cm])
        content_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        return content_table

    def _create_markdown_table(self, table_lines: list, header_color, bg_color) -> Table:
        """Convert markdown table lines to a ReportLab table."""
        # Parse table rows
        rows = []
        for line in table_lines:
            # Remove leading/trailing pipes and split by |
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            rows.append(cells)

        if not rows:
            return Spacer(1, 0)

        # Create paragraph styles for table cells
        header_cell_style = ParagraphStyle(
            'TableHeaderCell',
            parent=self.styles['ReportBody'],
            fontSize=9,
            textColor=colors.white,
            alignment=TA_LEFT
        )
        cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['ReportBody'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#2d3748')
        )

        # Convert to Paragraphs
        table_data = []
        for i, row in enumerate(rows):
            if i == 0:
                # Header row
                table_data.append([Paragraph(f"<b>{cell}</b>", header_cell_style) for cell in row])
            else:
                # Data rows - check for bold markers
                processed_cells = []
                for cell in row:
                    if cell.startswith('**') and cell.endswith('**'):
                        processed_cells.append(Paragraph(f"<b>{cell[2:-2]}</b>", cell_style))
                    else:
                        processed_cells.append(Paragraph(cell, cell_style))
                table_data.append(processed_cells)

        # Calculate column widths based on number of columns
        num_cols = len(rows[0]) if rows else 1
        if num_cols == 2:
            col_widths = [9*cm, 6*cm]
        elif num_cols == 3:
            col_widths = [6*cm, 4.5*cm, 4.5*cm]
        elif num_cols == 4:
            col_widths = [5*cm, 3.5*cm, 3.5*cm, 3*cm]
        else:
            col_widths = [15*cm / num_cols] * num_cols

        # Create table
        table = Table(table_data, colWidths=col_widths)

        # Style the table
        style_commands = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), bg_color),
            # Alternating row colors for better readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [bg_color, colors.white]),
            # Grid and borders
            ('GRID', (0, 0), (-1, -1), 0.5, header_color),
            ('BOX', (0, 0), (-1, -1), 1, header_color),
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            # Alignment
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]

        table.setStyle(TableStyle(style_commands))
        return table

    def _build_tco_summary(self, tco_text: str) -> list:
        """Build a prominent TCO summary box."""
        elements = []

        # TCO Header with icon
        header_table = Table(
            [[Paragraph(
                "<b>&#128176; Total Cost of Ownership (3 Years)</b>",
                ParagraphStyle('TCOHeader', fontSize=12, textColor=colors.HexColor('#744210'))
            )]],
            colWidths=[15*cm]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fefcbf')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(header_table)

        # TCO content
        tco_style = ParagraphStyle(
            'TCOContent',
            parent=self.styles['ReportBody'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#744210')
        )
        tco_content = Paragraph(markdown_to_reportlab(tco_text), tco_style)
        tco_table = Table(
            [[tco_content]],
            colWidths=[15*cm]
        )
        tco_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffff0')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#d69e2e')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(tco_table)

        return elements

    def _build_roi_callout(self, roi_text: str) -> list:
        """Build a ROI analysis callout box."""
        elements = []

        # ROI Header
        header_table = Table(
            [[Paragraph(
                "<b>&#128200; Investment vs. Return</b>",
                ParagraphStyle('ROIHeader', fontSize=11, textColor=colors.HexColor('#276749'))
            )]],
            colWidths=[15*cm]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#c6f6d5')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(header_table)

        # ROI content
        roi_style = ParagraphStyle(
            'ROIContent',
            parent=self.styles['ReportBody'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#22543d')
        )
        roi_content = Paragraph(markdown_to_reportlab(roi_text), roi_style)
        roi_table = Table(
            [[roi_content]],
            colWidths=[15*cm]
        )
        roi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fff4')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#48bb78')),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(roi_table)

        return elements

    def _build_cost_estimation_transcript(self, db_session: SessionModel) -> list:
        """Build the cost estimation conversation transcript for the appendix."""
        elements = []

        elements.append(Paragraph("Appendix F: Cost Estimation Transcript", self.styles['SectionHeader']))

        # Filter for cost_estimation messages only
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role != 'system',
            ConsultationMessage.message_type == 'cost_estimation'
        ).order_by(ConsultationMessage.created_at).all()

        # Filter out trigger messages and prompt-like content
        messages = [m for m in messages if not self._is_prompt_message(m.content, m.role)]

        if not messages:
            elements.append(Paragraph("No cost estimation conversation recorded.", self.styles['ReportBody']))
        else:
            elements.append(Paragraph(
                f"The following is the transcript of the cost estimation session ({len(messages)} messages).",
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
                    # AI responses - apply markdown formatting (no truncation)
                    content = markdown_to_reportlab(content)
                    elements.append(Paragraph(
                        f"<b>Cost Analyst:</b> {content}",
                        self.styles['ChatAssistant']
                    ))

        return elements

    def _build_recommendations_section(self, db_session: SessionModel) -> list:
        """Build the implementation recommendations section."""
        elements = []

        elements.append(Paragraph("5. Implementation Roadmap", self.styles['SectionHeader']))

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

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """
        Extract a section from markdown text by section header.

        Looks for patterns like:
        - ## SECTION_NAME or ### SECTION_NAME (with optional parenthetical descriptions)
        - **SECTION_NAME**
        - SECTION_NAME:

        Returns the content until the next section header or end of text.
        """
        if not text or not section_name:
            return None

        # Header patterns to find the start of this section
        # Note: {{2,3}} is escaped braces to produce {2,3} in the regex (f-string escaping)
        header_patterns = [
            rf'^#{{2,3}}\s*(\d+\.\s*)?{re.escape(section_name)}[^\n]*$',  # ### 1. USE CASE PROFILE or ### STRENGTHS (...)
            rf'^\*\*(\d+\.\s*)?{re.escape(section_name)}\*\*[:\s]*$',      # **1. USE CASE PROFILE** or **STRENGTHS**
            rf'^(\d+\.\s*)?{re.escape(section_name)}[:\s]*$',              # 1. USE CASE PROFILE: or STRENGTHS:
        ]

        # Find where this section starts
        start_pos = None
        start_line_end = None

        lines = text.split('\n')
        for i, line in enumerate(lines):
            for pattern in header_patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    start_pos = i
                    start_line_end = i + 1
                    break
            if start_pos is not None:
                break

        if start_pos is None:
            return None

        # Find where the next section starts (or end of text)
        end_pos = len(lines)
        # Match next section: ### HEADER, ### 1. HEADER, **HEADER**, or ALLCAPS:
        next_section_pattern = r'^(#{2,3}\s+(\d+\.\s*)?[A-Z]|\*\*(\d+\.\s*)?[A-Z]|[A-Z]{2,}[:\s]*$)'

        for i in range(start_line_end, len(lines)):
            line = lines[i].strip()
            if line and re.match(next_section_pattern, line):
                end_pos = i
                break

        # Extract content between header and next section
        content_lines = lines[start_line_end:end_pos]
        content = '\n'.join(content_lines).strip()

        return content if content else None

    def _build_swot_section(self, db_session: SessionModel) -> list:
        """Build the SWOT Analysis section."""
        elements = []

        # Header
        elements.append(Paragraph("6. SWOT Analysis", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "Strategic assessment of strengths, weaknesses, opportunities, and threats for the proposed AI/digitalization project.",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.2*inch))

        # Get the SWOT analysis from findings
        finding = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type == 'swot_analysis'
        ).first()

        if not finding or not finding.finding_text:
            # Show placeholder
            placeholder_style = ParagraphStyle(
                'SwotPlaceholder',
                parent=self.styles['ReportBody'],
                fontSize=10,
                textColor=colors.HexColor('#92400e'),
                alignment=TA_CENTER
            )

            content = Paragraph(
                "<b>SWOT Analysis Not Yet Generated</b><br/><br/>"
                "To generate this section, go to Step 6 (Export & Handover) in the application "
                "and click \"Generate SWOT Analysis\".",
                placeholder_style
            )

            table = Table([[content]], colWidths=[15*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef3c7')),
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#f59e0b')),
                ('TOPPADDING', (0, 0), (-1, -1), 20),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(table)
            return elements

        # Parse and render SWOT content
        swot_text = finding.finding_text

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"SWOT text (first 500 chars): {swot_text[:500] if swot_text else 'EMPTY'}")

        # Define quadrant properties: (en_name, de_name, header_color, bg_color)
        quadrant_config = {
            "strengths": ("STRENGTHS", "STÄRKEN", colors.HexColor('#166534'), colors.HexColor('#dcfce7')),
            "weaknesses": ("WEAKNESSES", "SCHWÄCHEN", colors.HexColor('#991b1b'), colors.HexColor('#fee2e2')),
            "opportunities": ("OPPORTUNITIES", "CHANCEN", colors.HexColor('#1e40af'), colors.HexColor('#dbeafe')),
            "threats": ("THREATS", "RISIKEN", colors.HexColor('#92400e'), colors.HexColor('#fef3c7')),
        }

        # Extract content for each quadrant
        quadrant_contents = {}
        for key, (en_name, de_name, header_color, bg_color) in quadrant_config.items():
            content = self._extract_section(swot_text, en_name) or self._extract_section(swot_text, de_name)
            logger.info(f"Extracted {en_name}: {content[:100] if content else 'NONE'}")
            quadrant_contents[key] = content

        # Helper function to build a SWOT cell
        def build_swot_cell(key):
            en_name, de_name, header_color, bg_color = quadrant_config[key]
            content = quadrant_contents.get(key, "")

            # Header paragraph
            header_para = Paragraph(
                f"<b>{en_name}</b>",
                ParagraphStyle('SwotHeader', fontSize=8, textColor=colors.white, alignment=TA_CENTER)
            )

            # Content paragraph (smaller font for matrix layout)
            if content:
                content_para = Paragraph(
                    markdown_to_reportlab(content),
                    ParagraphStyle('SwotContent', parent=self.styles['ReportBody'], fontSize=7, leading=9)
                )
            else:
                content_para = Paragraph(
                    "<i>Not available</i>",
                    ParagraphStyle('SwotEmpty', fontSize=7, textColor=colors.gray, alignment=TA_CENTER)
                )

            # Build cell as nested table (header + content)
            cell_table = Table(
                [[header_para], [content_para]],
                colWidths=[7.3*cm]
            )
            cell_table.setStyle(TableStyle([
                # Header row styling
                ('BACKGROUND', (0, 0), (0, 0), header_color),
                ('TOPPADDING', (0, 0), (0, 0), 6),
                ('BOTTOMPADDING', (0, 0), (0, 0), 6),
                ('LEFTPADDING', (0, 0), (0, 0), 8),
                ('RIGHTPADDING', (0, 0), (0, 0), 8),
                # Content row styling
                ('BACKGROUND', (0, 1), (0, 1), bg_color),
                ('TOPPADDING', (0, 1), (0, 1), 8),
                ('BOTTOMPADDING', (0, 1), (0, 1), 8),
                ('LEFTPADDING', (0, 1), (0, 1), 8),
                ('RIGHTPADDING', (0, 1), (0, 1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                # Border
                ('BOX', (0, 0), (-1, -1), 1, header_color),
            ]))
            return cell_table

        # Build 2x2 SWOT matrix
        # Row 1: Strengths | Weaknesses (Internal factors)
        # Row 2: Opportunities | Threats (External factors)
        swot_matrix = Table(
            [
                [build_swot_cell("strengths"), build_swot_cell("weaknesses")],
                [build_swot_cell("opportunities"), build_swot_cell("threats")],
            ],
            colWidths=[7.5*cm, 7.5*cm],
            hAlign='CENTER'
        )
        swot_matrix.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        elements.append(swot_matrix)
        elements.append(Spacer(1, 0.2*inch))

        # Strategic Implications section (below the matrix)
        # Wrapped in KeepTogether to move to new page if it doesn't fit
        implications = (
            self._extract_section(swot_text, "STRATEGIC IMPLICATIONS") or
            self._extract_section(swot_text, "STRATEGISCHE IMPLIKATIONEN")
        )
        if implications:
            impl_header = Table(
                [[Paragraph("<b>STRATEGIC IMPLICATIONS</b>", ParagraphStyle('IH', fontSize=9, textColor=colors.white))]],
                colWidths=[15*cm]
            )
            impl_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#4c1d95')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))

            impl_content = Paragraph(
                markdown_to_reportlab(implications),
                ParagraphStyle('IC', parent=self.styles['ReportBody'], fontSize=8, leading=10)
            )
            impl_box = Table([[impl_content]], colWidths=[15*cm])
            impl_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f3ff')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#4c1d95')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))

            # Keep header and content together; moves to new page if doesn't fit
            elements.append(KeepTogether([impl_header, impl_box]))

        # Fallback: if no sections were extracted, render the raw SWOT text
        # Check if we added any content (more than just header + spacer)
        if len(elements) <= 3:  # Only header elements, no quadrants
            logger.warning("No SWOT sections extracted, rendering raw text as fallback")
            # Render the full SWOT text as paragraphs (not in a table, to allow page splitting)
            fallback_content = Paragraph(
                markdown_to_reportlab(swot_text),
                ParagraphStyle('SwotFallback', parent=self.styles['ReportBody'], fontSize=9, leading=12)
            )
            elements.append(fallback_content)

        return elements

    def _build_technical_briefing_section(self, db_session: SessionModel) -> list:
        """Build the Technical Transition Briefing section (DMME Handover)."""
        elements = []

        # Header with DMME context
        elements.append(Paragraph("7. Technical Transition Briefing", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "This section bridges the Business Understanding phase to Technical Understanding & Conceptualization (DMME methodology).",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.2*inch))

        # Get the technical briefing from findings
        finding = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type == 'technical_briefing'
        ).first()

        if not finding or not finding.finding_text:
            # Show placeholder with instructions
            elements.append(self._build_briefing_placeholder())
            return elements

        # Parse and render the briefing content
        briefing_text = finding.finding_text

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Technical briefing text (first 500 chars): {briefing_text[:500] if briefing_text else 'EMPTY'}")

        # Create styled sections for the briefing
        sections = [
            ("USE CASE PROFILE", "USE CASE PROFIL"),
            ("TECHNICAL INVESTIGATION QUESTIONS", "TECHNISCHE UNTERSUCHUNGSFRAGEN"),
            ("IDENTIFIED ENABLERS AND BLOCKERS", "IDENTIFIZIERTE ENABLER UND BLOCKER"),
            ("HYPOTHESES FOR TECHNICAL IMPLEMENTATION", "HYPOTHESEN FÜR DIE TECHNISCHE UMSETZUNG"),
            ("RECOMMENDED FIRST STEPS", "EMPFOHLENE ERSTE SCHRITTE"),
            ("OPEN ITEMS", "OFFENE PUNKTE")
        ]

        # Try to extract and format each section
        for en_name, de_name in sections:
            section_content = self._extract_section(briefing_text, en_name) or self._extract_section(briefing_text, de_name)
            logger.info(f"Extracted {en_name}: {section_content[:100] if section_content else 'NONE'}")
            if section_content:
                elements.extend(self._build_briefing_subsection(en_name, section_content))
                elements.append(Spacer(1, 0.15*inch))

        # If no sections were extracted, render the whole content
        if not any(self._extract_section(briefing_text, name[0]) or self._extract_section(briefing_text, name[1]) for name in sections):
            content_elements = markdown_to_elements(
                briefing_text,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)

        return elements

    def _build_briefing_placeholder(self) -> Table:
        """Build a placeholder box for missing briefing."""
        placeholder_style = ParagraphStyle(
            'BriefingPlaceholder',
            parent=self.styles['ReportBody'],
            fontSize=10,
            textColor=colors.HexColor('#744210'),
            alignment=TA_CENTER
        )

        content = Paragraph(
            "<b>Technical Transition Briefing Not Yet Generated</b><br/><br/>"
            "To generate this section, go to Step 6 (Export & Handover) in the application "
            "and click \"Generate Technical Briefing\".<br/><br/>"
            "This document prepares the handover from Business Understanding to "
            "Technical Understanding & Conceptualization phase.",
            placeholder_style
        )

        table = Table([[content]], colWidths=[15*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fefcbf')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#d69e2e')),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))

        return table

    def _build_briefing_subsection(self, title: str, content: str) -> list:
        """Build a styled subsection for the technical briefing."""
        elements = []

        # Format title
        display_title = title.replace("_", " ").title()

        # Header
        header_style = ParagraphStyle(
            'BriefingSubheader',
            parent=self.styles['SubHeader'],
            fontSize=11,
            textColor=colors.HexColor('#2c5282'),
            spaceBefore=10,
            spaceAfter=6
        )
        elements.append(Paragraph(f"<b>{display_title}</b>", header_style))

        # Content with styling based on section type
        if "HYPOTHESIS" in title.upper() or "HYPOTHES" in title.upper():
            # Special formatting for hypotheses
            elements.extend(self._format_hypotheses(content))
        elif "ENABLER" in title.upper() or "BLOCKER" in title.upper():
            # Special formatting for enablers/blockers
            elements.extend(self._format_enablers_blockers(content))
        elif "INVESTIGATION" in title.upper() or "UNTERSUCHUNG" in title.upper():
            # Special formatting for investigation questions
            elements.extend(self._format_investigation_questions(content))
        else:
            # Standard content formatting
            content_elements = markdown_to_elements(
                content,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)

        return elements

    def _format_hypotheses(self, content: str) -> list:
        """Format hypotheses with styled boxes."""
        elements = []

        # Parse hypotheses
        import re
        hypothesis_pattern = r'\*\*Hypothesis\s*\d*[:\.]?\*\*\s*(.*?)(?=\*\*Hypothesis|\*\*To be validated|$)'
        validation_pattern = r'\*\*To be validated[:\.]?\*\*\s*(.*?)(?=\*\*Hypothesis|$)'

        # Simple approach: render as formatted content with box
        content_clean = content.replace('>', '').strip()

        hyp_style = ParagraphStyle(
            'HypothesisText',
            parent=self.styles['ReportBody'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#2d3748'),
            leftIndent=10
        )

        # Create a styled box
        hyp_para = Paragraph(markdown_to_reportlab(content_clean), hyp_style)
        hyp_table = Table([[hyp_para]], colWidths=[14.5*cm])
        hyp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ebf8ff')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#90cdf4')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(hyp_table)

        return elements

    def _format_enablers_blockers(self, content: str) -> list:
        """Format enablers and blockers with visual distinction."""
        elements = []

        # Try to split into enablers and blockers
        content_lower = content.lower()
        enabler_idx = max(content_lower.find('enabler'), 0)
        blocker_idx = content_lower.find('blocker')

        if blocker_idx > enabler_idx:
            enablers_text = content[enabler_idx:blocker_idx].strip()
            blockers_text = content[blocker_idx:].strip()
        else:
            enablers_text = content
            blockers_text = ""

        # Enablers box (green)
        if enablers_text:
            enabler_header = Table(
                [[Paragraph("<b>Enablers</b>", ParagraphStyle('EH', fontSize=10, textColor=colors.white))]],
                colWidths=[14.5*cm]
            )
            enabler_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#276749')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(enabler_header)

            enabler_content = Paragraph(
                markdown_to_reportlab(enablers_text.replace('**Enablers**', '').replace('**Enabler**', '').strip()),
                ParagraphStyle('EC', parent=self.styles['ReportBody'], fontSize=9)
            )
            enabler_box = Table([[enabler_content]], colWidths=[14.5*cm])
            enabler_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#c6f6d5')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#276749')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(enabler_box)
            elements.append(Spacer(1, 0.1*inch))

        # Blockers box (orange/red)
        if blockers_text:
            blocker_header = Table(
                [[Paragraph("<b>Blockers</b>", ParagraphStyle('BH', fontSize=10, textColor=colors.white))]],
                colWidths=[14.5*cm]
            )
            blocker_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#c53030')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(blocker_header)

            blocker_content = Paragraph(
                markdown_to_reportlab(blockers_text.replace('**Blockers**', '').replace('**Blocker**', '').strip()),
                ParagraphStyle('BC', parent=self.styles['ReportBody'], fontSize=9)
            )
            blocker_box = Table([[blocker_content]], colWidths=[14.5*cm])
            blocker_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fed7d7')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#c53030')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(blocker_box)

        # Fallback if parsing didn't work
        if not enablers_text and not blockers_text:
            content_elements = markdown_to_elements(
                content,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)

        return elements

    def _format_investigation_questions(self, content: str) -> list:
        """Format investigation questions organized by infrastructure layer."""
        elements = []

        # Try to identify the three layers
        layers = [
            ("Physical Infrastructure", "Physische Infrastruktur", colors.HexColor('#2c5282')),
            ("Virtual Infrastructure", "Virtuelle Infrastruktur", colors.HexColor('#2b6cb0')),
            ("Governance", "Governance", colors.HexColor('#553c9a'))
        ]

        content_used = False
        remaining_content = content

        for en_name, de_name, color in layers:
            # Try to extract this layer
            layer_content = None
            for name in [en_name, de_name]:
                if name.lower() in content.lower():
                    # Find the section
                    import re
                    pattern = rf'\*\*{name}\*\*\s*(.*?)(?=\*\*(?:Physical|Virtual|Governance|Physische|Virtuelle)|$)'
                    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                    if match:
                        layer_content = match.group(1).strip()
                        break

            if layer_content:
                content_used = True
                # Layer header
                layer_header = Table(
                    [[Paragraph(f"<b>{en_name}</b>", ParagraphStyle('LH', fontSize=9, textColor=colors.white))]],
                    colWidths=[14.5*cm]
                )
                layer_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), color),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ]))
                elements.append(layer_header)

                # Layer content
                layer_para = Paragraph(
                    markdown_to_reportlab(layer_content),
                    ParagraphStyle('LC', parent=self.styles['ReportBody'], fontSize=9, leading=12)
                )
                layer_box = Table([[layer_para]], colWidths=[14.5*cm])
                layer_box.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
                    ('BOX', (0, 0), (-1, -1), 1, color),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ]))
                elements.append(layer_box)
                elements.append(Spacer(1, 0.08*inch))

        # Fallback if no layers found
        if not content_used:
            content_elements = markdown_to_elements(
                content,
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)

        return elements

    def _build_maturity_appendix(self, db_session: SessionModel) -> list:
        """Build the Digital Maturity Assessment appendix with bar charts."""
        from ..models import MaturityAssessment

        elements = []

        # Header
        elements.append(Paragraph("Appendix G: Digital Maturity Assessment", self.styles['SectionHeader']))
        elements.append(Paragraph(
            "This section presents the digital maturity assessment based on the Acatech Industry 4.0 Maturity Index. "
            "The assessment evaluates the company across four structural dimensions on a scale of 1-6.",
            self.styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.2*inch))

        # Get maturity assessment
        maturity = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == db_session.id
        ).first()

        if not maturity:
            # Placeholder if no assessment
            placeholder = Paragraph(
                "<i>No maturity assessment has been completed for this session.</i>",
                ParagraphStyle('MaturityPlaceholder', parent=self.styles['ReportBody'],
                              textColor=colors.gray, alignment=TA_CENTER)
            )
            elements.append(placeholder)
            return elements

        # Maturity level descriptions
        level_descriptions = {
            1: ("Computerization", "Basic IT systems, isolated digital solutions"),
            2: ("Connectivity", "Connected systems, basic data exchange"),
            3: ("Visibility", "Real-time data capture, digital shadow of operations"),
            4: ("Transparency", "Data analysis for understanding root causes"),
            5: ("Predictive Capacity", "Simulation and prediction of future scenarios"),
            6: ("Adaptability", "Automated adaptation and self-optimization"),
        }

        # Color gradient from red (1) to green (6)
        def get_score_color(score):
            if score < 2:
                return colors.HexColor('#ef4444')  # Red
            elif score < 3:
                return colors.HexColor('#f97316')  # Orange
            elif score < 4:
                return colors.HexColor('#eab308')  # Yellow
            elif score < 5:
                return colors.HexColor('#84cc16')  # Lime
            else:
                return colors.HexColor('#22c55e')  # Green

        # Overall Score Section
        elements.append(Paragraph("<b>Overall Maturity Level</b>", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        overall_score = maturity.overall_score or 0
        maturity_level_name = maturity.maturity_level or "Unknown"

        # Create overall score bar
        overall_bar_data = [
            [
                Paragraph(f"<b>{maturity_level_name}</b>",
                         ParagraphStyle('OverallLabel', fontSize=11, alignment=TA_LEFT)),
                self._create_maturity_bar(overall_score, width=10*cm, height=0.6*cm),
                Paragraph(f"<b>{overall_score:.1f}</b>/6",
                         ParagraphStyle('OverallScore', fontSize=11, alignment=TA_RIGHT))
            ]
        ]
        overall_table = Table(overall_bar_data, colWidths=[4*cm, 10.2*cm, 1.5*cm])
        overall_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(overall_table)
        elements.append(Spacer(1, 0.3*inch))

        # Dimension Scores Section
        elements.append(Paragraph("<b>Dimension Scores</b>", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.15*inch))

        # Dimension data
        dimensions = [
            ("Resources", maturity.resources_score or 0,
             "Digital capability of employees, equipment, and materials"),
            ("Information Systems", maturity.information_systems_score or 0,
             "Integration of IT systems and data processing capabilities"),
            ("Culture", maturity.culture_score or 0,
             "Willingness to change, knowledge sharing, and openness"),
            ("Organizational Structure", maturity.organizational_structure_score or 0,
             "Agility, collaboration, and decision-making processes"),
        ]

        # Build dimension bars
        for dim_name, score, description in dimensions:
            # Dimension row with bar
            dim_data = [
                [
                    Paragraph(f"<b>{dim_name}</b>",
                             ParagraphStyle('DimLabel', fontSize=9, alignment=TA_LEFT)),
                    self._create_maturity_bar(score, width=9*cm, height=0.45*cm),
                    Paragraph(f"<b>{score:.1f}</b>",
                             ParagraphStyle('DimScore', fontSize=9, alignment=TA_RIGHT))
                ]
            ]
            dim_table = Table(dim_data, colWidths=[4.5*cm, 9.2*cm, 1*cm])
            dim_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(dim_table)

            # Description
            elements.append(Paragraph(
                f"<i>{description}</i>",
                ParagraphStyle('DimDesc', fontSize=7, textColor=colors.gray, leftIndent=10)
            ))
            elements.append(Spacer(1, 0.12*inch))

        elements.append(Spacer(1, 0.2*inch))

        # Maturity Level Scale Legend
        elements.append(Paragraph("<b>Maturity Level Scale</b>", self.styles['SubHeader']))
        elements.append(Spacer(1, 0.1*inch))

        # Create legend table
        legend_data = []
        for level in range(1, 7):
            name, desc = level_descriptions[level]
            level_color = get_score_color(level)

            # Color box as a small table cell
            color_cell = Table([[""]], colWidths=[0.4*cm], rowHeights=[0.4*cm])
            color_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), level_color),
                ('BOX', (0, 0), (0, 0), 0.5, colors.gray),
            ]))

            legend_data.append([
                Paragraph(f"<b>{level}</b>", ParagraphStyle('LegendNum', fontSize=8, alignment=TA_CENTER)),
                color_cell,
                Paragraph(f"<b>{name}</b>", ParagraphStyle('LegendName', fontSize=8)),
                Paragraph(desc, ParagraphStyle('LegendDesc', fontSize=7, textColor=colors.gray)),
            ])

        legend_table = Table(legend_data, colWidths=[0.6*cm, 0.6*cm, 3*cm, 10.5*cm])
        legend_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(legend_table)

        return elements

    def _create_maturity_bar(self, score: float, width: float = 10*cm, height: float = 0.5*cm) -> Drawing:
        """Create a horizontal bar chart for maturity score (1-6 scale)."""
        from reportlab.graphics.shapes import Drawing, Rect, String, Line

        # Normalize score to 0-1 range (score is 1-6)
        normalized = max(0, min(1, (score - 1) / 5)) if score > 0 else 0

        # Create drawing
        d = Drawing(width, height)

        # Background bar (gray)
        d.add(Rect(0, 0, width, height, fillColor=colors.HexColor('#e5e7eb'), strokeColor=None))

        # Filled bar (colored based on score)
        if score > 0:
            # Color gradient
            if score < 2:
                bar_color = colors.HexColor('#ef4444')  # Red
            elif score < 3:
                bar_color = colors.HexColor('#f97316')  # Orange
            elif score < 4:
                bar_color = colors.HexColor('#eab308')  # Yellow
            elif score < 5:
                bar_color = colors.HexColor('#84cc16')  # Lime
            else:
                bar_color = colors.HexColor('#22c55e')  # Green

            fill_width = normalized * width
            d.add(Rect(0, 0, fill_width, height, fillColor=bar_color, strokeColor=None))

        # Border
        d.add(Rect(0, 0, width, height, fillColor=None, strokeColor=colors.HexColor('#9ca3af'), strokeWidth=0.5))

        # Scale markers (at 1, 2, 3, 4, 5, 6)
        for i in range(1, 7):
            x_pos = ((i - 1) / 5) * width
            d.add(Line(x_pos, 0, x_pos, height, strokeColor=colors.HexColor('#9ca3af'), strokeWidth=0.3))

        return d
