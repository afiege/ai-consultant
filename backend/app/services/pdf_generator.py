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
    PageBreak, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
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
        """Build the business case indication section (Step 5)."""
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

        # 1. Classification
        elements.append(Paragraph("1. Value Framework Classification", self.styles['SubHeader']))
        if findings_dict.get('business_case_classification'):
            content_elements = markdown_to_elements(
                findings_dict['business_case_classification'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 2. Back-of-the-envelope Calculation
        elements.append(Paragraph("2. Back-of-the-envelope Calculation", self.styles['SubHeader']))
        if findings_dict.get('business_case_calculation'):
            content_elements = markdown_to_elements(
                findings_dict['business_case_calculation'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 3. Validation Questions
        elements.append(Paragraph("3. Validation Questions", self.styles['SubHeader']))
        if findings_dict.get('business_case_validation'):
            content_elements = markdown_to_elements(
                findings_dict['business_case_validation'],
                self.styles['ReportBody'],
                self.styles['IdeaText']
            )
            elements.extend(content_elements)
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

        elements.append(Spacer(1, 0.2*inch))

        # 4. Management Pitch
        elements.append(Paragraph("4. Management Pitch", self.styles['SubHeader']))
        if findings_dict.get('business_case_pitch'):
            # Use a styled box/callout for the pitch
            pitch_text = findings_dict['business_case_pitch']
            pitch_text = pitch_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            pitch_text = pitch_text.replace('\n', '<br/>')
            elements.append(Paragraph(
                f"<i>\"{pitch_text}\"</i>",
                ParagraphStyle(
                    'PitchStyle',
                    parent=self.styles['ReportBody'],
                    fontSize=11,
                    leftIndent=20,
                    rightIndent=20,
                    spaceBefore=10,
                    spaceAfter=10,
                    textColor=colors.HexColor('#2c5282'),
                    leading=16
                )
            ))
        else:
            elements.append(Paragraph("Not yet determined.", self.styles['ReportBody']))

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
            elements.append(Paragraph(
                f"<b>Source: {source_label}</b>",
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
