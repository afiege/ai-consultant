"""Service for extracting structured company profiles from raw company information."""

import json
import logging
from typing import Optional, Dict, List
from litellm import completion
from sqlalchemy.orm import Session
from ..utils.llm import apply_model_params

from ..models import Session as SessionModel, CompanyInfo
from ..schemas.company_profile import CompanyProfile, CompanyProfileResponse
from ..utils.security import sanitize_user_input, validate_api_base

logger = logging.getLogger(__name__)

# Extraction prompt - emphasizes no invention of data
EXTRACTION_SYSTEM_PROMPT = {
    "en": """You are a data extraction assistant. Your task is to extract structured company information from raw text.

CRITICAL RULES:
1. ONLY extract information that is EXPLICITLY stated or clearly implied in the source text
2. For any field where information is NOT available, you MUST return null
3. DO NOT invent, assume, guess, or estimate ANY data
4. DO NOT use placeholder values or generic descriptions
5. If uncertain about a value, return null for that field
6. Use the exact values/numbers mentioned in the text when available

For list fields (like products_services, pain_points):
- Only include items explicitly mentioned
- Maximum 5 items per list
- Return null (not empty array) if no items are mentioned

For numeric/financial fields:
- Use ranges if exact numbers aren't given (e.g., "€5-10M")
- Include currency symbols when relevant
- Return null if not mentioned at all

Return a valid JSON object matching the required schema.""",

    "de": """Du bist ein Datenextraktions-Assistent. Deine Aufgabe ist es, strukturierte Unternehmensinformationen aus Rohtexten zu extrahieren.

KRITISCHE REGELN:
1. Extrahiere NUR Informationen, die EXPLIZIT im Quelltext genannt oder klar impliziert werden
2. Für jedes Feld, wo Informationen NICHT verfügbar sind, MUSST du null zurückgeben
3. ERFINDE, SCHÄTZE oder VERMUTE KEINE Daten
4. Verwende KEINE Platzhalter oder generische Beschreibungen
5. Im Zweifelsfall gib null für das Feld zurück
6. Verwende die genauen Werte/Zahlen aus dem Text, wenn verfügbar

Für Listenfelder (wie products_services, pain_points):
- Nur explizit genannte Punkte aufnehmen
- Maximal 5 Einträge pro Liste
- null zurückgeben (kein leeres Array) wenn nichts erwähnt wird

Für numerische/finanzielle Felder:
- Bereiche verwenden wenn keine genauen Zahlen genannt werden (z.B. "€5-10M")
- Währungssymbole angeben
- null zurückgeben wenn nicht erwähnt

Gib ein gültiges JSON-Objekt zurück, das dem geforderten Schema entspricht."""
}

EXTRACTION_USER_PROMPT = {
    "en": """Extract a structured company profile from the following information.

SOURCE INFORMATION:
{raw_info}

---

Extract into this JSON structure (use null for any field not mentioned):
{{
    "name": "Company name (required - use 'Unknown Company' if not found)",
    "industry": "Primary industry or null",
    "sub_industry": "Specific sub-sector or null",
    "employee_count": "Number/range as string or null",
    "founding_year": "Year as integer or null",
    "ownership": "family-owned/founder-led/PE-backed/corporate subsidiary or null",
    "headquarters": "City, Country or null",
    "other_locations": ["list of locations"] or null,
    "markets_served": ["DACH", "EU", etc.] or null,
    "annual_revenue": "Revenue range like €5-10M or null",
    "profit_margin": "Percentage or description or null",
    "cash_flow_status": "positive/tight/etc. or null",
    "growth_rate": "Percentage or description or null",
    "production_volume": "Volume description or null",
    "capacity_utilization": "Percentage or null",
    "core_business": "1-2 sentence description or null",
    "products_services": ["max 5 items"] or null,
    "customer_segments": ["B2B", "specific industries"] or null,
    "key_processes": ["max 5 processes"] or null,
    "current_systems": ["ERP name", "tools used"] or null,
    "data_sources": ["what data they have"] or null,
    "automation_level": "manual/partially automated/etc. or null",
    "pain_points": ["max 3 challenges"] or null,
    "digitalization_goals": ["max 3 goals"] or null,
    "competitive_pressures": "Description or null"
}}

Return ONLY the JSON object, no other text.""",

    "de": """Extrahiere ein strukturiertes Unternehmensprofil aus den folgenden Informationen.

QUELLINFORMATIONEN:
{raw_info}

---

Extrahiere in diese JSON-Struktur (null für nicht genannte Felder):
{{
    "name": "Firmenname (erforderlich - 'Unbekanntes Unternehmen' wenn nicht gefunden)",
    "industry": "Hauptbranche oder null",
    "sub_industry": "Spezifischer Teilsektor oder null",
    "employee_count": "Anzahl/Bereich als String oder null",
    "founding_year": "Jahr als Integer oder null",
    "ownership": "familiengeführt/gründergeführt/PE-finanziert/Konzerntochter oder null",
    "headquarters": "Stadt, Land oder null",
    "other_locations": ["Liste der Standorte"] oder null,
    "markets_served": ["DACH", "EU", etc.] oder null,
    "annual_revenue": "Umsatzbereich wie €5-10M oder null",
    "profit_margin": "Prozentsatz oder Beschreibung oder null",
    "cash_flow_status": "positiv/angespannt/etc. oder null",
    "growth_rate": "Prozentsatz oder Beschreibung oder null",
    "production_volume": "Volumenbeschreibung oder null",
    "capacity_utilization": "Prozentsatz oder null",
    "core_business": "1-2 Sätze Beschreibung oder null",
    "products_services": ["max 5 Einträge"] oder null,
    "customer_segments": ["B2B", "spezifische Branchen"] oder null,
    "key_processes": ["max 5 Prozesse"] oder null,
    "current_systems": ["ERP-Name", "genutzte Tools"] oder null,
    "data_sources": ["verfügbare Daten"] oder null,
    "automation_level": "manuell/teilautomatisiert/etc. oder null",
    "pain_points": ["max 3 Herausforderungen"] oder null,
    "digitalization_goals": ["max 3 Ziele"] oder null,
    "competitive_pressures": "Beschreibung oder null"
}}

Gib NUR das JSON-Objekt zurück, keinen anderen Text."""
}

# Fields that indicate good profile quality
CRITICAL_FIELDS = ["name", "industry", "core_business"]
IMPORTANT_FIELDS = ["employee_count", "products_services", "key_processes", "pain_points"]


def extract_company_profile(
    db: Session,
    session_uuid: str,
    model: str = "mistral/mistral-small-latest",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    language: str = "en"
) -> CompanyProfileResponse:
    """
    Extract a structured company profile from raw company information.

    Args:
        db: Database session
        session_uuid: Session UUID
        model: LLM model to use
        api_key: Optional API key
        api_base: Optional API base URL
        language: Language for prompts ('en' or 'de')

    Returns:
        CompanyProfileResponse with extracted profile and quality indicators
    """
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise ValueError(f"Session {session_uuid} not found")

    # Get all company info entries
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()

    if not company_infos:
        raise ValueError("No company information available to extract from")

    # Combine raw info
    raw_parts = []
    for info in company_infos:
        if info.content:
            source_label = {
                "text": "User-provided text",
                "file": f"Uploaded file: {info.file_name or 'document'}",
                "web_crawl": f"Website: {info.source_url or 'company website'}"
            }.get(info.info_type, "Information")

            raw_parts.append(f"[{source_label}]\n{info.content}")

    raw_info = "\n\n---\n\n".join(raw_parts)

    # Sanitize combined raw info to remove control characters and limit whitespace
    raw_info = sanitize_user_input(raw_info, max_length=20000)

    # Limit total size to avoid token issues (keep ~8000 chars)
    if len(raw_info) > 8000:
        raw_info = raw_info[:8000] + "\n\n[... truncated for length ...]"

    # Validate api_base against allowlist to prevent SSRF
    validate_api_base(api_base)

    # Build messages
    lang = language if language in ["en", "de"] else "en"
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT[lang]},
        {"role": "user", "content": EXTRACTION_USER_PROMPT[lang].format(raw_info=raw_info)}
    ]

    # Call LLM
    completion_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,  # Low temperature for consistent extraction
        "max_tokens": 1500,
        "timeout": 60
    }
    if api_key:
        completion_kwargs["api_key"] = api_key
    if api_base:
        completion_kwargs["api_base"] = api_base
    apply_model_params(completion_kwargs)

    logger.info(f"Extracting company profile for session {session_uuid}")

    response = completion(**completion_kwargs)
    content = response.choices[0].message.content

    # Parse JSON from response
    profile_data = _parse_json_response(content)

    # Validate and create profile
    profile = CompanyProfile(**profile_data)

    # Assess extraction quality
    quality, missing = _assess_quality(profile)

    # Store in session
    db_session.company_profile = profile.model_dump_json()
    db.commit()

    logger.info(f"Company profile extracted with quality: {quality}")

    return CompanyProfileResponse(
        profile=profile,
        extraction_quality=quality,
        missing_critical_info=missing if missing else None
    )


def get_company_profile(db: Session, session_uuid: str) -> Optional[CompanyProfile]:
    """
    Get the stored company profile for a session.

    Returns None if no profile has been extracted yet.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session or not db_session.company_profile:
        return None

    try:
        data = json.loads(db_session.company_profile)
        return CompanyProfile(**data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse stored company profile: {e}")
        return None


def get_profile_as_context(db: Session, session_uuid: str, language: str = "en") -> str:
    """
    Get the company profile formatted as context text for use in prompts.

    This returns a condensed, token-efficient representation.
    """
    profile = get_company_profile(db, session_uuid)

    if not profile:
        return "No company profile available."

    parts = []

    # Basic info
    parts.append(f"Company: {profile.name}")
    if profile.industry:
        industry_str = profile.industry
        if profile.sub_industry:
            industry_str += f" ({profile.sub_industry})"
        parts.append(f"Industry: {industry_str}")

    if profile.employee_count:
        parts.append(f"Employees: {profile.employee_count}")

    if profile.ownership:
        parts.append(f"Ownership: {profile.ownership}")

    # Location
    locations = []
    if profile.headquarters:
        locations.append(f"HQ: {profile.headquarters}")
    if profile.other_locations:
        locations.append(f"Also in: {', '.join(profile.other_locations)}")
    if profile.markets_served:
        locations.append(f"Markets: {', '.join(profile.markets_served)}")
    if locations:
        parts.append(" | ".join(locations))

    # Financials
    financials = []
    if profile.annual_revenue:
        financials.append(f"Revenue: {profile.annual_revenue}")
    if profile.growth_rate:
        financials.append(f"Growth: {profile.growth_rate}")
    if profile.profit_margin:
        financials.append(f"Margin: {profile.profit_margin}")
    if financials:
        parts.append(" | ".join(financials))

    # Operations
    if profile.production_volume or profile.capacity_utilization:
        ops = []
        if profile.production_volume:
            ops.append(f"Production: {profile.production_volume}")
        if profile.capacity_utilization:
            ops.append(f"Utilization: {profile.capacity_utilization}")
        parts.append(" | ".join(ops))

    # Business
    if profile.core_business:
        parts.append(f"Core business: {profile.core_business}")

    if profile.products_services:
        parts.append(f"Products/Services: {', '.join(profile.products_services)}")

    if profile.customer_segments:
        parts.append(f"Customers: {', '.join(profile.customer_segments)}")

    # Tech & Processes
    if profile.key_processes:
        parts.append(f"Key processes: {', '.join(profile.key_processes)}")

    if profile.current_systems:
        parts.append(f"Current systems: {', '.join(profile.current_systems)}")

    if profile.data_sources:
        parts.append(f"Data sources: {', '.join(profile.data_sources)}")

    if profile.automation_level:
        parts.append(f"Automation level: {profile.automation_level}")

    # Challenges & Goals
    if profile.pain_points:
        parts.append(f"Pain points: {', '.join(profile.pain_points)}")

    if profile.digitalization_goals:
        parts.append(f"Digitalization goals: {', '.join(profile.digitalization_goals)}")

    if profile.competitive_pressures:
        parts.append(f"Competitive situation: {profile.competitive_pressures}")

    return "\n".join(parts)


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()

    # Remove markdown code blocks if present
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Content was: {content[:500]}")
        # Return minimal valid profile
        return {"name": "Unknown Company"}


def _assess_quality(profile: CompanyProfile) -> tuple[str, List[str]]:
    """Assess the quality of the extracted profile."""
    missing_critical = []
    missing_important = []

    # Check critical fields
    for field in CRITICAL_FIELDS:
        value = getattr(profile, field, None)
        if not value or value == "Unknown Company":
            missing_critical.append(field)

    # Check important fields
    for field in IMPORTANT_FIELDS:
        value = getattr(profile, field, None)
        if not value:
            missing_important.append(field)

    # Determine quality
    if not missing_critical and len(missing_important) <= 1:
        quality = "high"
    elif len(missing_critical) <= 1 and len(missing_important) <= 2:
        quality = "medium"
    else:
        quality = "low"

    all_missing = missing_critical + missing_important
    return quality, all_missing if all_missing else []
