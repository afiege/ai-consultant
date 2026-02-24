"""
Cross-Reference Extraction Service

Uses LLM to identify semantic links between findings for wiki-style cross-referencing.
"""

import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from litellm import completion

from ..models import ConsultationFinding, FindingCrossReference
from .session_settings import get_llm_settings
from ..utils.llm import apply_model_params, extract_content
from ..utils.cross_ref_registry import ALL_IDS

logger = logging.getLogger(__name__)

# All available finding types that can be linked to
FINDING_TYPES = {
    # Step 1 - Company Info
    "company_profile": "Company Profile - basic company information and context",

    # Step 1c - Maturity
    "maturity_assessment": "Maturity Assessment - digital maturity level and dimensions",

    # Step 4 - CRISP-DM
    "business_objectives": "Business Objectives - what the company wants to achieve",
    "situation_assessment": "Situation Assessment - current state and challenges",
    "ai_goals": "AI/Data Mining Goals - specific AI/ML objectives",
    "project_plan": "Project Plan - implementation roadmap and milestones",

    # Step 5a - Business Case
    "business_case_classification": "Value Classification - which value level the project targets",
    "business_case_calculation": "Financial Calculation - ROI, savings, revenue projections",
    "business_case_validation": "Validation Questions - questions to verify assumptions",
    "business_case_pitch": "Management Pitch - executive summary for stakeholders",

    # Step 5b - Cost Estimation
    "cost_complexity": "Complexity Assessment - technical difficulty and scope",
    "cost_initial": "Initial Investment - upfront costs and setup expenses",
    "cost_recurring": "Recurring Costs - ongoing operational expenses",
    "cost_maintenance": "Maintenance Costs - support and update expenses",
    "cost_tco": "Total Cost of Ownership - 3-5 year total cost projection",
    "cost_drivers": "Cost Drivers - main factors affecting costs",
    "cost_optimization": "Cost Optimization - ways to reduce costs",
    "cost_roi": "ROI Analysis - return on investment calculation",

    # Step 6 - Analysis
    "swot_analysis": "SWOT Analysis - strengths, weaknesses, opportunities, threats",
    "technical_briefing": "Technical Briefing - handover document for implementation",
}

# Relationship types
RELATIONSHIP_TYPES = [
    "references",      # General mention/reference
    "depends_on",      # This finding requires/assumes the target
    "supports",        # This finding provides evidence for the target
    "contradicts",     # This finding conflicts with the target
    "elaborates",      # This finding expands on the target
    "quantifies",      # This finding provides numbers for the target
]


def extract_cross_references(
    db: Session,
    finding: ConsultationFinding,
    all_findings: Dict[str, str],
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    language: str = "en"
) -> List[FindingCrossReference]:
    """
    Extract cross-references from a finding using LLM.

    Args:
        db: Database session
        finding: The source finding to extract references from
        all_findings: Dict of {factor_type: finding_text} for all findings in session
        model: LLM model to use
        api_key: Optional API key
        api_base: Optional API base URL
        language: Language for the prompt

    Returns:
        List of FindingCrossReference objects (not yet committed)
    """
    if not finding.finding_text or len(finding.finding_text) < 50:
        return []

    # Build list of available targets (exclude self)
    available_targets = {
        k: v for k, v in FINDING_TYPES.items()
        if k != finding.factor_type and k in all_findings
    }

    if not available_targets:
        return []

    prompt = _build_extraction_prompt(
        finding.finding_text,
        finding.factor_type,
        available_targets,
        language
    )

    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": _get_system_prompt(language)},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # Lower temperature for more consistent extraction
            "max_tokens": 1500,
            "response_format": {"type": "json_object"}
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        content = extract_content(response)

        # Parse the JSON response
        references = _parse_llm_response(content)

        # Create FindingCrossReference objects
        cross_refs = []
        for ref in references:
            target_type = ref.get("target")
            if target_type not in available_targets:
                continue

            cross_ref = FindingCrossReference(
                session_id=finding.session_id,
                source_finding_id=finding.id,
                target_finding_type=target_type,
                linked_phrase=ref.get("phrase", "")[:500],  # Limit length
                relationship_type=ref.get("relationship", "references"),
                confidence=ref.get("confidence", 80)
            )
            cross_refs.append(cross_ref)

        logger.info(f"Extracted {len(cross_refs)} cross-references from {finding.factor_type}")
        return cross_refs

    except Exception as e:
        logger.error(f"Failed to extract cross-references: {e}")
        return []


def _get_system_prompt(language: str) -> str:
    """Get the system prompt for cross-reference extraction."""
    if language == "de":
        return """Du bist ein Experte für Dokumentenanalyse. Deine Aufgabe ist es, semantische Querverweise
zwischen verschiedenen Abschnitten eines Beratungsberichts zu identifizieren.

Antworte IMMER mit gültigem JSON im folgenden Format:
{
  "references": [
    {
      "phrase": "exakte Phrase aus dem Text",
      "target": "ziel_abschnitt_id",
      "relationship": "references|depends_on|supports|contradicts|elaborates|quantifies",
      "confidence": 80
    }
  ]
}"""

    return """You are an expert at document analysis. Your task is to identify semantic cross-references
between different sections of a consultation report.

ALWAYS respond with valid JSON in this format:
{
  "references": [
    {
      "phrase": "exact phrase from the text",
      "target": "target_section_id",
      "relationship": "references|depends_on|supports|contradicts|elaborates|quantifies",
      "confidence": 80
    }
  ]
}"""


def _build_extraction_prompt(
    finding_text: str,
    finding_type: str,
    available_targets: Dict[str, str],
    language: str
) -> str:
    """Build the prompt for extracting cross-references."""

    targets_list = "\n".join([f"- {k}: {v}" for k, v in available_targets.items()])

    if language == "de":
        return f"""Analysiere den folgenden Text aus dem Abschnitt "{finding_type}" und identifiziere
Phrasen, die auf andere Abschnitte des Berichts verweisen.

TEXT:
{finding_text}

VERFÜGBARE ZIELABSCHNITTE:
{targets_list}

BEZIEHUNGSTYPEN:
- references: Allgemeine Erwähnung/Verweis
- depends_on: Setzt den Zielabschnitt voraus
- supports: Liefert Beweise für den Zielabschnitt
- contradicts: Steht im Widerspruch zum Zielabschnitt
- elaborates: Führt den Zielabschnitt weiter aus
- quantifies: Liefert Zahlen für den Zielabschnitt

Finde 0-5 relevante Querverweise. Sei präzise - verlinke nur, wenn eine echte semantische Verbindung besteht."""

    return f"""Analyze the following text from the "{finding_type}" section and identify
phrases that reference other sections of the report.

TEXT:
{finding_text}

AVAILABLE TARGET SECTIONS:
{targets_list}

RELATIONSHIP TYPES:
- references: General mention/reference
- depends_on: This requires/assumes the target section
- supports: This provides evidence for the target section
- contradicts: This conflicts with the target section
- elaborates: This expands on the target section
- quantifies: This provides numbers for the target section

Find 0-5 relevant cross-references. Be precise - only link when there's a genuine semantic connection."""


def _parse_llm_response(content: str) -> List[Dict]:
    """Parse the LLM's JSON response."""
    try:
        data = json.loads(content)
        references = data.get("references", [])

        # Validate each reference
        valid_refs = []
        for ref in references:
            if not isinstance(ref, dict):
                continue
            if not ref.get("phrase") or not ref.get("target"):
                continue
            if ref.get("relationship") not in RELATIONSHIP_TYPES:
                ref["relationship"] = "references"
            if not isinstance(ref.get("confidence"), int):
                ref["confidence"] = 80
            valid_refs.append(ref)

        return valid_refs

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return []


def extract_all_cross_references(
    db: Session,
    session_id: int,
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    language: str = "en"
) -> int:
    """
    Extract cross-references for all findings in a session.

    Args:
        db: Database session
        session_id: The consultation session ID
        model: LLM model to use
        api_key: Optional API key
        api_base: Optional API base URL
        language: Language for prompts

    Returns:
        Total number of cross-references created
    """
    # Get all findings for this session
    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == session_id
    ).all()

    if not findings:
        return 0

    # Build dict of all findings
    all_findings = {f.factor_type: f.finding_text for f in findings}

    # Clear existing cross-references for this session
    db.query(FindingCrossReference).filter(
        FindingCrossReference.session_id == session_id
    ).delete()

    total_refs = 0

    for finding in findings:
        cross_refs = extract_cross_references(
            db=db,
            finding=finding,
            all_findings=all_findings,
            model=model,
            api_key=api_key,
            api_base=api_base,
            language=language
        )

        for ref in cross_refs:
            db.add(ref)
            total_refs += 1

    db.commit()
    logger.info(f"Created {total_refs} cross-references for session {session_id}")

    return total_refs


def get_cross_references_for_session(
    db: Session,
    session_id: int
) -> Dict[str, List[Dict]]:
    """
    Get all cross-references for a session, organized by source finding type.

    Returns:
        Dict mapping source_factor_type to list of cross-reference dicts
    """
    refs = db.query(FindingCrossReference).filter(
        FindingCrossReference.session_id == session_id
    ).all()

    # Get the source finding types
    finding_ids = {r.source_finding_id for r in refs}
    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.id.in_(finding_ids)
    ).all() if finding_ids else []

    finding_type_map = {f.id: f.factor_type for f in findings}

    result = {}
    for ref in refs:
        source_type = finding_type_map.get(ref.source_finding_id, "unknown")
        if source_type not in result:
            result[source_type] = []

        result[source_type].append({
            "id": ref.id,
            "target": ref.target_finding_type,
            "phrase": ref.linked_phrase,
            "relationship": ref.relationship_type,
            "confidence": ref.confidence
        })

    return result
