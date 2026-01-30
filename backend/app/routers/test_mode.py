"""Test mode router for automated persona-based responses."""

import json
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from litellm import completion

from ..database import get_db
from ..models import Session as SessionModel, ConsultationMessage

router = APIRouter(prefix="/api/test-mode", tags=["test-mode"])

# Load personas from evaluation file
PERSONAS_FILE = Path(__file__).parent.parent.parent.parent / "evaluation" / "benchmark_personas.json"


def load_personas() -> List[Dict]:
    """Load personas from the benchmark file."""
    if not PERSONAS_FILE.exists():
        return []

    with open(PERSONAS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("personas", [])


@router.get("/personas")
def get_personas():
    """Get list of available test personas."""
    personas = load_personas()

    # Return simplified list for selection
    return [
        {
            "persona_id": p["persona_id"],
            "company_name": p["company"]["name"],
            "industry": p["company"]["sub_industry"],
            "employees": p["company"]["size_employees"],
            "focus_idea": p["focus_idea"]["title"],
            "language": p.get("language", "en")
        }
        for p in personas
    ]


@router.get("/personas/{persona_id}")
def get_persona_details(persona_id: str):
    """Get full details of a specific persona."""
    personas = load_personas()

    for p in personas:
        if p["persona_id"] == persona_id:
            return p

    raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")


def build_user_agent_prompt(persona: Dict, conversation_context: str, last_ai_message: str) -> str:
    """Build the system prompt for the user agent that role-plays as the persona."""

    company = persona["company"]
    focus_idea = persona["focus_idea"]

    # Format KPIs
    kpis_text = ""
    if "kpis" in company:
        kpis_text = "\n".join([
            f"- {k}: {v['value']}{v['unit']} (target: {v['target']}{v['unit']}) - {v.get('note', '')}"
            for k, v in company["kpis"].items()
        ])

    # Format challenges
    challenges_text = "\n".join([f"- {c}" for c in company.get("current_challenges", [])])

    # Format digitalization details
    digital = company.get("digitalization_maturity", {})
    digital_details = digital.get("details", {})
    digital_text = "\n".join([f"- {k}: {v}" for k, v in digital_details.items()])

    prompt = f"""You are role-playing as a client in a business consultation. You represent the following company and must answer the consultant's questions based on this profile.

## YOUR COMPANY PROFILE

**Company:** {company['name']}
**Industry:** {company['sub_industry']}
**Size:** {company['size_employees']} employees, €{company['size_revenue_eur']:,} revenue

**Business Model:**
{company['business_model']}

**Products/Services:**
{company['products_services']}

**Target Market:**
{company['target_market']}

**Team Structure:**
{company['team_structure']}

**Strategic Goals:**
{company['strategic_goals']}

## KEY PERFORMANCE INDICATORS (KPIs)
{kpis_text}

## CURRENT CHALLENGES
{challenges_text}

## DIGITALIZATION MATURITY
Level: {digital.get('level', 'N/A')} - {digital.get('level_name', 'N/A')}
{digital_text}

## PROJECT FOCUS
**Idea:** {focus_idea['title']}
**Description:** {focus_idea['description']}

## INSTRUCTIONS

1. Answer the consultant's questions naturally, as if you were the owner/manager of this company
2. Use the information above to provide realistic, specific answers
3. Include relevant numbers, KPIs, and details when appropriate
4. Be conversational but professional
5. If asked about something not in your profile, make a reasonable assumption consistent with the company profile
6. Keep responses concise but informative (2-4 sentences typically)
7. You can express uncertainty about exact numbers if realistic ("I think it's around..." or "roughly...")
8. Show genuine interest in solving the company's challenges

## CONVERSATION CONTEXT
{conversation_context}

## CONSULTANT'S LATEST QUESTION/MESSAGE
{last_ai_message}

Now respond as the client. Be natural and conversational."""

    return prompt


@router.post("/{session_uuid}/generate-response")
async def generate_persona_response(
    session_uuid: str,
    persona_id: str,
    message_type: str = "consultation",  # consultation, business_case, or cost_estimation
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Generate a user response based on the persona and current conversation."""

    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get persona
    personas = load_personas()
    persona = None
    for p in personas:
        if p["persona_id"] == persona_id:
            persona = p
            break

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    # Get conversation history
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.message_type == message_type
    ).order_by(ConsultationMessage.created_at).all()

    if not messages:
        raise HTTPException(status_code=400, detail="No conversation to respond to")

    # Build conversation context (last 10 messages for context window efficiency)
    recent_messages = messages[-10:]
    conversation_context = "\n\n".join([
        f"{'Consultant' if m.role == 'assistant' else 'You (Client)'}: {m.content}"
        for m in recent_messages
        if m.role != 'system'
    ])

    # Get last AI message to respond to
    last_ai_message = ""
    for m in reversed(messages):
        if m.role == 'assistant':
            last_ai_message = m.content
            break

    if not last_ai_message:
        raise HTTPException(status_code=400, detail="No consultant message to respond to")

    # Build prompt for user agent
    system_prompt = build_user_agent_prompt(persona, conversation_context, last_ai_message)

    # Determine model and API settings
    model = db_session.llm_model or "mistral/mistral-small-latest"
    api_base = db_session.llm_api_base
    api_key = x_api_key

    # Call LLM to generate response
    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Please respond to the consultant's message as the client."}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base

        response = completion(**completion_kwargs)
        generated_response = response.choices[0].message.content

        return {
            "response": generated_response,
            "persona_id": persona_id,
            "company_name": persona["company"]["name"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")


@router.get("/personas/{persona_id}/company-profile")
def get_persona_company_profile(persona_id: str):
    """Get company profile text for Step 1a from a persona."""
    personas = load_personas()

    persona = None
    for p in personas:
        if p["persona_id"] == persona_id:
            persona = p
            break

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    company = persona["company"]

    # Build company profile text similar to what a user would enter
    profile_parts = []

    profile_parts.append(f"**Company Name:** {company['name']}")
    profile_parts.append(f"**Industry:** {company['sub_industry']}")
    profile_parts.append(f"**Size:** {company['size_employees']} employees, €{company['size_revenue_eur']:,} annual revenue")
    profile_parts.append("")

    profile_parts.append(f"**Business Model:**\n{company['business_model']}")
    profile_parts.append("")

    profile_parts.append(f"**Products/Services:**\n{company['products_services']}")
    profile_parts.append("")

    profile_parts.append(f"**Target Market:**\n{company['target_market']}")
    profile_parts.append("")

    profile_parts.append(f"**Team Structure:**\n{company['team_structure']}")
    profile_parts.append("")

    profile_parts.append(f"**Strategic Goals:**\n{company['strategic_goals']}")
    profile_parts.append("")

    # Add KPIs
    if "kpis" in company:
        profile_parts.append("**Key Performance Indicators (KPIs):**")
        for kpi_name, kpi_data in company["kpis"].items():
            profile_parts.append(f"- {kpi_name.replace('_', ' ').title()}: {kpi_data['value']}{kpi_data['unit']} (target: {kpi_data['target']}{kpi_data['unit']}) - {kpi_data.get('note', '')}")
        profile_parts.append("")

    # Add current challenges
    if "current_challenges" in company:
        profile_parts.append("**Current Challenges:**")
        for challenge in company["current_challenges"]:
            profile_parts.append(f"- {challenge}")
        profile_parts.append("")

    # Add digitalization details
    digital = company.get("digitalization_maturity", {})
    if "details" in digital:
        profile_parts.append("**Current IT/Digitalization Systems:**")
        for system_name, system_desc in digital["details"].items():
            profile_parts.append(f"- {system_name.upper()}: {system_desc}")
        profile_parts.append("")

    # Add focus idea
    focus = persona.get("focus_idea", {})
    if focus:
        profile_parts.append("**Project Focus/Interest:**")
        profile_parts.append(f"{focus.get('title', '')}: {focus.get('description', '')}")

    return {
        "company_name": company["name"],
        "profile_text": "\n".join(profile_parts)
    }


@router.get("/personas/{persona_id}/maturity-assessment")
def get_persona_maturity_assessment(persona_id: str):
    """Get maturity assessment scores for Step 1b from a persona."""
    personas = load_personas()

    persona = None
    for p in personas:
        if p["persona_id"] == persona_id:
            persona = p
            break

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    digital = persona["company"].get("digitalization_maturity", {})
    acatech = digital.get("acatech_assessment", {})

    # Convert to Step 1b format
    scores = {
        "resources": {
            "q1": acatech.get("resources", {}).get("q1", 1),
            "q2": acatech.get("resources", {}).get("q2", 1),
            "q3": acatech.get("resources", {}).get("q3", 1),
            "q4": acatech.get("resources", {}).get("q4", 1),
        },
        "informationSystems": {
            "q1": acatech.get("information_systems", {}).get("q1", 1),
            "q2": acatech.get("information_systems", {}).get("q2", 1),
            "q3": acatech.get("information_systems", {}).get("q3", 1),
            "q4": acatech.get("information_systems", {}).get("q4", 1),
        },
        "culture": {
            "q1": acatech.get("culture", {}).get("q1", 1),
            "q2": acatech.get("culture", {}).get("q2", 1),
            "q3": acatech.get("culture", {}).get("q3", 1),
            "q4": acatech.get("culture", {}).get("q4", 1),
        },
        "organizationalStructure": {
            "q1": acatech.get("organizational_structure", {}).get("q1", 1),
            "q2": acatech.get("organizational_structure", {}).get("q2", 1),
            "q3": acatech.get("organizational_structure", {}).get("q3", 1),
            "q4": acatech.get("organizational_structure", {}).get("q4", 1),
        },
    }

    return {
        "company_name": persona["company"]["name"],
        "maturity_level": digital.get("level", 1),
        "maturity_level_name": digital.get("level_name", "Unknown"),
        "scores": scores
    }


@router.post("/{session_uuid}/generate-response/stream")
async def generate_persona_response_stream(
    session_uuid: str,
    persona_id: str,
    message_type: str = "consultation",
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Generate a user response with streaming."""

    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get persona
    personas = load_personas()
    persona = None
    for p in personas:
        if p["persona_id"] == persona_id:
            persona = p
            break

    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    # Get conversation history
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.message_type == message_type
    ).order_by(ConsultationMessage.created_at).all()

    if not messages:
        raise HTTPException(status_code=400, detail="No conversation to respond to")

    # Build conversation context
    recent_messages = messages[-10:]
    conversation_context = "\n\n".join([
        f"{'Consultant' if m.role == 'assistant' else 'You (Client)'}: {m.content}"
        for m in recent_messages
        if m.role != 'system'
    ])

    # Get last AI message
    last_ai_message = ""
    for m in reversed(messages):
        if m.role == 'assistant':
            last_ai_message = m.content
            break

    if not last_ai_message:
        raise HTTPException(status_code=400, detail="No consultant message to respond to")

    # Build prompt
    system_prompt = build_user_agent_prompt(persona, conversation_context, last_ai_message)

    model = db_session.llm_model or "mistral/mistral-small-latest"
    api_base = db_session.llm_api_base
    api_key = x_api_key

    def generate():
        try:
            completion_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Please respond to the consultant's message as the client."}
                ],
                "temperature": 0.7,
                "max_tokens": 500,
                "stream": True
            }

            if api_key:
                completion_kwargs["api_key"] = api_key
            if api_base:
                completion_kwargs["api_base"] = api_base

            stream = completion(**completion_kwargs)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield f"data: {chunk.choices[0].delta.content}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
