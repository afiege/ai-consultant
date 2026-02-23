"""PDF generation service for consultation reports (WeasyPrint backend)."""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import markdown as md
from jinja2 import Environment, FileSystemLoader

# macOS / Homebrew: ensure pango/cairo libraries are on the search path before
# cffi's dlopen() is called at weasyprint import time.
if sys.platform == 'darwin':
    _brew_lib = '/opt/homebrew/lib'
    _current = os.environ.get('DYLD_LIBRARY_PATH', '')
    if _brew_lib not in _current:
        os.environ['DYLD_LIBRARY_PATH'] = f"{_brew_lib}:{_current}" if _current else _brew_lib

from weasyprint import HTML
from sqlalchemy.orm import Session as DBSession

from ..models import (
    Session as SessionModel,
    CompanyInfo,
    Participant,
    IdeaSheet,
    Idea,
    Prioritization,
    ConsultationMessage,
    ConsultationFinding,
    MaturityAssessment,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

VALUE_LEVELS = [
    (1, "Level 1 – Operational Efficiency", "Basic automation and process optimisation"),
    (2, "Level 2 – Tactical Advantage", "Pattern recognition and predictive analytics"),
    (3, "Level 3 – Strategic Intelligence", "Decision support and market intelligence"),
    (4, "Level 4 – Business Model Innovation", "New products, services, or revenue streams"),
    (5, "Level 5 – Ecosystem Transformation", "Industry disruption and platform creation"),
]

COMPLEXITY_LEVELS = [
    ("quick_win", "Quick Win", "#16a34a", "< 3 months · < €50k"),
    ("standard", "Standard Project", "#2563eb", "3–6 months · €50k–€200k"),
    ("complex", "Complex Project", "#d97706", "6–18 months · €200k–€1M"),
    ("enterprise", "Enterprise Initiative", "#dc2626", "> 18 months · > €1M"),
]

GLOSSARY = [
    ("6-3-5 Method", "A structured brainstorming technique where 6 participants write 3 ideas in 5 minutes, then pass their sheet to build on others' ideas."),
    ("acatech Industry 4.0 Maturity Index", "A six-level framework (1–6) measuring organisational digital maturity across structure, culture, and technology dimensions."),
    ("AI/ML", "Artificial Intelligence / Machine Learning – technologies that enable systems to learn from data and make decisions."),
    ("Business Case", "A justification for a proposed project based on expected costs, benefits, and value creation."),
    ("CRISP-DM", "Cross-Industry Standard Process for Data Mining – a six-phase methodology for analytics and AI projects."),
    ("MVP", "Minimum Viable Product – the simplest version of a product that delivers value and enables learning."),
    ("POC", "Proof of Concept – a small-scale implementation to validate technical feasibility."),
    ("ROI", "Return on Investment – a measure of profitability calculated as (Gain − Cost) / Cost."),
    ("SWOT Analysis", "Strategic analysis of Strengths, Weaknesses, Opportunities, and Threats."),
    ("TCO", "Total Cost of Ownership – the complete cost of a solution over its lifecycle, including hidden costs."),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preprocess(text: str) -> str:
    """Strip wiki-links and normalise <br> before markdown conversion."""
    if not text:
        return ""
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    return text


def to_html(text: str) -> str:
    """Convert markdown to HTML (used as Jinja2 filter)."""
    if not text:
        return ""
    return md.markdown(_preprocess(text), extensions=['tables', 'sane_lists'])


def _extract_section(text: str, name: str) -> str:
    """Extract a named ## section from markdown text."""
    if not text:
        return ""
    pattern = rf'(?:^|\n)#{{1,3}}\s*{re.escape(name)}\s*\n(.*?)(?=\n#{{1,3}}\s|\Z)'
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _detect_value_level(text: str) -> Optional[int]:
    """Return 1–5 for the detected value level, or None."""
    if not text:
        return None
    t = text.lower()
    for level, pattern in [
        (5, r'level\s*5|ecosystem|transform|disrupt'),
        (4, r'level\s*4|business model|new.*product|revenue stream'),
        (3, r'level\s*3|strategic|market intelligence|decision.*support'),
        (2, r'level\s*2|tactical|predictive|pattern'),
        (1, r'level\s*1|operational|basic.*automat|process.*optim'),
    ]:
        if re.search(pattern, t):
            return level
    return None


def _detect_complexity(text: str) -> Optional[str]:
    """Return 'quick_win', 'standard', 'complex', 'enterprise', or None."""
    if not text:
        return None
    t = text.lower()
    if 'enterprise' in t:
        return 'enterprise'
    if 'complex' in t:
        return 'complex'
    if 'standard' in t:
        return 'standard'
    if 'quick win' in t or 'quick-win' in t:
        return 'quick_win'
    return None


def _is_prompt(content: str, role: str) -> bool:
    """Return True if the message is a system trigger to filter from transcripts."""
    if role != 'user' or not content:
        return False
    lower = content.lower().strip()
    triggers = [
        'please start the consultation',
        'start the consultation',
        'please begin',
        'start business case',
        'start cost estimation',
    ]
    if any(lower.startswith(t) for t in triggers):
        return True
    if len(content) > 1500 and content.count('##') >= 3:
        return True
    return False


from ..utils.recommendation import generate_management_recommendation as _generate_recommendation


def _pct(score: Optional[float]) -> float:
    """Normalise a 1–6 maturity score to a 0–100 percentage."""
    if score is None:
        return 0.0
    return round(min(max(score / 6 * 100, 0), 100), 1)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class PDFReportGenerator:
    """Generates PDF reports from consultation sessions using WeasyPrint."""

    def __init__(self, db: DBSession):
        self.db = db
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )
        self.env.filters['markdown'] = to_html

    def generate_report(self, session_uuid: str) -> bytes:
        data = self._collect_data(session_uuid)
        html_str = self.env.get_template('report.html').render(**data)
        return HTML(string=html_str).write_pdf()

    def _save_finding(self, session_id: int, factor_type: str, text: str) -> None:
        """Upsert a ConsultationFinding."""
        existing = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == session_id,
            ConsultationFinding.factor_type == factor_type,
        ).first()
        if existing:
            existing.finding_text = text
        else:
            self.db.add(ConsultationFinding(
                session_id=session_id,
                factor_type=factor_type,
                finding_text=text,
            ))
        self.db.commit()

    def _collect_data(self, session_uuid: str) -> dict:
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()
        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")
        sid = db_session.id

        # All findings indexed by factor_type
        findings = {
            f.factor_type: f.finding_text
            for f in self.db.query(ConsultationFinding)
            .filter(ConsultationFinding.session_id == sid)
            .all()
        }

        # Top idea by votes
        sheets = self.db.query(IdeaSheet).filter(IdeaSheet.session_id == sid).all()
        top_idea = None
        ranked_ideas: list = []
        if sheets:
            sheet_ids = [s.id for s in sheets]
            all_ideas = self.db.query(Idea).filter(Idea.sheet_id.in_(sheet_ids)).all()
            idea_ids = [i.id for i in all_ideas]
            prio_map: dict = {}
            for p in self.db.query(Prioritization).filter(Prioritization.idea_id.in_(idea_ids)).all():
                prio_map[p.idea_id] = prio_map.get(p.idea_id, 0) + (p.score or 0)
            scored = sorted(
                [{'content': i.content, 'score': prio_map.get(i.id, 0)} for i in all_ideas],
                key=lambda x: x['score'],
                reverse=True,
            )
            ranked_ideas = scored[:50]
            if scored:
                top_idea = scored[0]['content']

        # Company info docs
        company_infos = [
            {
                'info_type': c.info_type,
                'file_name': c.file_name,
                'source_url': c.source_url,
                'content': c.content,
            }
            for c in self.db.query(CompanyInfo).filter(CompanyInfo.session_id == sid).all()
        ]

        # Maturity assessment
        maturity_row = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == sid
        ).first()
        maturity = None
        if maturity_row:
            maturity = {
                'overall': maturity_row.overall_score,
                'overall_pct': _pct(maturity_row.overall_score),
                'level': maturity_row.maturity_level,
                'resources': maturity_row.resources_score,
                'resources_pct': _pct(maturity_row.resources_score),
                'information_systems': maturity_row.information_systems_score,
                'information_systems_pct': _pct(maturity_row.information_systems_score),
                'culture': maturity_row.culture_score,
                'culture_pct': _pct(maturity_row.culture_score),
                'org_structure': maturity_row.organizational_structure_score,
                'org_structure_pct': _pct(maturity_row.organizational_structure_score),
            }

        # Participants
        participants = [
            {'name': p.name}
            for p in self.db.query(Participant).filter(Participant.session_id == sid).all()
        ]

        # Transcripts (filtered)
        def get_messages(msg_type: str) -> list:
            rows = (
                self.db.query(ConsultationMessage)
                .filter(
                    ConsultationMessage.session_id == sid,
                    ConsultationMessage.message_type == msg_type,
                )
                .order_by(ConsultationMessage.created_at)
                .all()
            )
            return [
                {'role': m.role, 'content': m.content}
                for m in rows
                if not _is_prompt(m.content, m.role)
            ]

        # SWOT quadrants (extracted from finding_text)
        swot_raw = findings.get('swot_analysis', '')
        swot = {
            'strengths': _extract_section(swot_raw, 'Strengths'),
            'weaknesses': _extract_section(swot_raw, 'Weaknesses'),
            'opportunities': _extract_section(swot_raw, 'Opportunities'),
            'threats': _extract_section(swot_raw, 'Threats'),
            'implications': _extract_section(swot_raw, 'Strategic Implications'),
        }

        # Technical briefing subsections
        tb_raw = findings.get('technical_briefing', '')
        tech = {
            'use_case_profile': _extract_section(tb_raw, 'Use Case Profile'),
            'investigation_questions': _extract_section(tb_raw, 'Investigation Questions'),
            'enablers': _extract_section(tb_raw, 'Enablers'),
            'blockers': _extract_section(tb_raw, 'Blockers'),
            'hypotheses': _extract_section(tb_raw, 'Hypotheses'),
            'first_steps': _extract_section(tb_raw, 'First Steps'),
            'open_items': _extract_section(tb_raw, 'Open Items'),
            'raw': tb_raw,
        }

        # Compute and persist the management recommendation so it is visible in
        # the Step 6 session-data view and remains equivalent to the PDF content.
        recommendation = _generate_recommendation(findings, top_idea, db_session.company_name or '')
        self._save_finding(sid, 'management_recommendation', recommendation)
        findings['management_recommendation'] = recommendation

        return {
            'company_name': db_session.company_name or 'Company',
            'session_ref': db_session.session_uuid[:8].upper(),
            'date': datetime.now().strftime("%B %d, %Y"),
            'findings': findings,
            'top_idea': top_idea,
            'ranked_ideas': ranked_ideas,
            'company_infos': company_infos,
            'participants': participants,
            'maturity': maturity,
            'swot': swot,
            'tech': tech,
            'value_levels': VALUE_LEVELS,
            'value_level': _detect_value_level(findings.get('business_case_classification', '')),
            'complexity_levels': COMPLEXITY_LEVELS,
            'complexity_level': _detect_complexity(findings.get('cost_complexity', '')),
            'glossary': GLOSSARY,
            'consultation_messages': get_messages('consultation'),
            'business_case_messages': get_messages('business_case'),
            'cost_estimation_messages': get_messages('cost_estimation'),
        }
