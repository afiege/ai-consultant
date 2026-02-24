"""Test mode router for automated persona-based responses."""

import json
from pathlib import Path
from typing import Optional, List, Dict
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Header, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from litellm import completion

import uuid as uuid_lib
from ..database import get_db
from ..models import Session as SessionModel, ConsultationMessage
from ..models.idea import IdeaSheet, Idea
from ..models.prioritization import Prioritization
from ..models.participant import Participant
from ..utils.sse import format_sse_data
from ..utils.llm import apply_model_params, extract_content

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


# Common models available via LiteLLM for benchmarking
AVAILABLE_MODELS = [
    # OpenAI
    {"provider": "openai", "model": "gpt-4o", "display_name": "GPT-4o"},
    {"provider": "openai", "model": "gpt-4o-mini", "display_name": "GPT-4o Mini"},
    {"provider": "openai", "model": "gpt-4-turbo", "display_name": "GPT-4 Turbo"},
    # Anthropic
    {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet"},
    {"provider": "anthropic", "model": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku"},
    # Mistral
    {"provider": "mistral", "model": "mistral/mistral-small-latest", "display_name": "Mistral Small"},
    {"provider": "mistral", "model": "mistral/mistral-large-latest", "display_name": "Mistral Large"},
    {"provider": "mistral", "model": "mistral/open-mistral-nemo", "display_name": "Mistral Nemo"},
    # Ollama (local)
    {"provider": "ollama", "model": "ollama/llama3.1:8b", "display_name": "Llama 3.1 8B (local)"},
    {"provider": "ollama", "model": "ollama/llama3.1:70b", "display_name": "Llama 3.1 70B (local)"},
    {"provider": "ollama", "model": "ollama/qwen2.5:7b", "display_name": "Qwen 2.5 7B (local)"},
    {"provider": "ollama", "model": "ollama/qwen2.5:72b", "display_name": "Qwen 2.5 72B (local)"},
    {"provider": "ollama", "model": "ollama/gemma2:9b", "display_name": "Gemma 2 9B (local)"},
    # OpenRouter (access to many models)
    {"provider": "openrouter", "model": "openrouter/meta-llama/llama-3.1-70b-instruct", "display_name": "Llama 3.1 70B (OpenRouter)"},
    {"provider": "openrouter", "model": "openrouter/qwen/qwen-2.5-72b-instruct", "display_name": "Qwen 2.5 72B (OpenRouter)"},
    {"provider": "openrouter", "model": "openrouter/google/gemma-2-27b-it", "display_name": "Gemma 2 27B (OpenRouter)"},
]


@router.get("/available-models")
def get_available_models():
    """Get list of commonly available models for benchmarking.

    These are models that can be used for either the consultant LLM
    or the user agent LLM. The actual availability depends on the
    user's API keys and local setup (for Ollama models).
    """
    return {
        "models": AVAILABLE_MODELS,
        "default_user_agent": "mistral/mistral-small-latest",
        "note": "Availability depends on configured API keys. Ollama models require local installation."
    }


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


def build_user_agent_prompt(
    persona: Dict,
    conversation_context: str,
    last_ai_message: str,
    message_type: str = "consultation",
    language: str = "en"
) -> str:
    """Build the system prompt for the user agent that role-plays as the persona.

    Args:
        persona: Persona dict with company and focus_idea
        conversation_context: Formatted recent conversation history
        last_ai_message: The consultant's latest message to respond to
        message_type: Type of conversation (consultation, business_case, cost_estimation)
        language: Language code ("en" or "de")
    """

    company = persona["company"]
    focus_idea = persona["focus_idea"]

    # Format KPIs
    kpis_text = ""
    if "kpis" in company:
        if language == "de":
            kpis_text = "\n".join([
                f"- {k}: {v['value']}{v['unit']}"
                + (f" (Ziel: {v['target']}{v['unit']})" if 'target' in v else "")
                + f" - {v.get('note', '')}"
                for k, v in company["kpis"].items()
            ])
        else:
            kpis_text = "\n".join([
                f"- {k}: {v['value']}{v['unit']}"
                + (f" (target: {v['target']}{v['unit']})" if 'target' in v else "")
                + f" - {v.get('note', '')}"
                for k, v in company["kpis"].items()
            ])

    # Format challenges
    challenges_text = "\n".join([f"- {c}" for c in company.get("current_challenges", [])])

    # Format digitalization details
    digital = company.get("digitalization_maturity", {})
    digital_details = digital.get("details", {})
    digital_text = "\n".join([f"- {k}: {v}" for k, v in digital_details.items()])

    # Build step-specific response length rule
    if language == "de":
        if message_type in ("business_case", "cost_estimation"):
            length_rule = (
                "**Antworte ausführlicher bei Finanzfragen.** Bei Fragen zu Kosten, Budget, ROI oder "
                "Geschäftszahlen gib detaillierte Antworten mit konkreten Zahlen (4–6 Sätze). "
                "Bei allgemeinen Fragen bleibe bei 2–4 Sätzen."
            )
        else:
            length_rule = (
                "**Sei prägnant.** Antworte in 2–4 Sätzen, außer die Frage erfordert mehr Detail. "
                "Schweife nicht ab."
            )
    else:
        if message_type in ("business_case", "cost_estimation"):
            length_rule = (
                "**Give more detail on financial questions.** When asked about costs, budgets, ROI, "
                "or business figures, provide detailed answers with concrete numbers (4–6 sentences). "
                "For general questions, keep it to 2–4 sentences."
            )
        else:
            length_rule = (
                "**Be concise.** Answer in 2–4 sentences unless the question requires more detail. "
                "Don't digress."
            )

    if language == "de":
        prompt = f"""Du simulierst den Geschäftsführer/Inhaber eines Unternehmens in einem Beratungsgespräch zur Einführung von KI-basierten Assistenzsystemen. Ein KI-Berater stellt dir Fragen, um deinen Anwendungsfall besser zu verstehen.

---

## 1. Unternehmensprofil

**Unternehmen:** {company['name']}
**Branche:** {company['sub_industry']}
**Größe:** {company['size_employees']} Mitarbeiter, €{company['size_revenue_eur']:,} Umsatz

**Geschäftsmodell:**
{company['business_model']}

**Produkte/Dienstleistungen:**
{company['products_services']}

**Zielmarkt:**
{company['target_market']}

**Teamstruktur:**
{company['team_structure']}

**Strategische Ziele:**
{company['strategic_goals']}

---

## 2. Kennzahlen (KPIs)
{kpis_text}

---

## 3. Aktuelle Herausforderungen
{challenges_text}

---

## 4. Digitalisierungsreifegrad
Stufe: {digital.get('level', 'N/A')} - {digital.get('level_name', 'N/A')}
{digital_text}

---

## 5. Projektfokus
**Idee:** {focus_idea['title']}
**Beschreibung:** {focus_idea['description']}

---

## 6. Verhaltensregeln

1. **Antworte natürlich als Inhaber/Geschäftsführer.** Du sprichst aus der Ich-Perspektive. Du bist kein KI-Experte, sondern ein erfahrener Praktiker in deiner Branche.

2. **Keine Begrüßung.** Das Gespräch läuft bereits. Beginne deine Antwort NICHT mit "Guten Tag", "Hallo", "Guten Morgen" oder einer anderen Begrüßung. Steige direkt in die Antwort ein.

3. **Nutze konkrete Zahlen und KPIs.** Wenn der Berater nach Kennzahlen fragt, nenne die Werte aus dem KPI-Abschnitt. Beispiel: "Unsere Ausschussrate liegt aktuell bei 4,2%, wir wollen auf unter 2% kommen."

4. {length_rule}

5. **Triff plausible Annahmen bei Lücken.** Wenn der Berater etwas fragt, das nicht explizit in deinem Profil steht, aber ein Geschäftsführer typischerweise wissen würde, gib eine plausible Antwort, die zum Unternehmensprofil passt.

6. **Zeige echtes Interesse.** Du nimmst an diesem Gespräch teil, weil du wirklich wissen willst, ob KI deinem Unternehmen helfen kann. Stelle gelegentlich Rückfragen, wenn etwas unklar ist.

7. **Erfinde KEINE Fakten**, die dem Profil widersprechen. Wenn du etwas wirklich nicht weißt, sag: "Das müsste ich intern nachfragen" oder "Da habe ich keine genauen Zahlen."

8. **Kein KI-Fachjargon.** Du verwendest keine Begriffe wie "Machine Learning", "Training Data", "Inference" – außer der Berater hat sie dir erklärt.

9. **Bleib konsistent.** Widersprich nicht früheren Aussagen im Gespräch.

10. **Schrittwechsel.** Schlage nicht von dir aus vor, zum nächsten Thema überzugehen. Beantworte weiterhin die Fragen des Beraters und liefere relevante Details aus deinem Unternehmensprofil. Stimme einem Schrittwechsel zu, wenn: (a) der Berater vorschlägt weiterzugehen, oder (b) alle relevanten Informationen bereits besprochen wurden und keine offenen Fragen mehr bestehen.

11. **Rückfragen bei Wiederholungen.** Wenn der Berater etwas fragt, das bereits früher im Gespräch beantwortet wurde, weise kurz darauf hin: "Wie ich vorhin erwähnt hatte, [kurze Zusammenfassung deiner früheren Antwort]. Brauchen Sie dazu noch weitere Details?" Gib nicht nochmals die gleiche ausführliche Antwort.

12. **Kein Markdown.** Schreibe in natürlichem Fließtext. Verwende keine Markdown-Formatierung: keine Überschriften (###), keine horizontalen Linien (---), keine Aufzählungszeichen (*), keine Fettschrift (**text**), keine Codeblöcke.

---

## 7. Gesprächsverlauf
{conversation_context}

---

## 8. Letzte Nachricht des Beraters
{last_ai_message}

---

## Deine Aufgabe

Antworte auf die letzte Nachricht des Beraters. Bleibe in deiner Rolle als Geschäftsführer. Beziehe dich auf die Fakten aus deinem Unternehmensprofil."""

    else:
        prompt = f"""You are role-playing as the owner/managing director of a company in a consultation about introducing AI-based systems. An AI consultant is asking you questions to better understand your use case.

---

## 1. Company Profile

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

---

## 2. Key Performance Indicators (KPIs)
{kpis_text}

---

## 3. Current Challenges
{challenges_text}

---

## 4. Digitalization Maturity
Level: {digital.get('level', 'N/A')} - {digital.get('level_name', 'N/A')}
{digital_text}

---

## 5. Project Focus
**Idea:** {focus_idea['title']}
**Description:** {focus_idea['description']}

---

## 6. Behavioral Instructions

1. **Answer naturally as the owner/managing director.** Speak from the first person. You are not an AI expert — you are an experienced practitioner in your industry.

2. **No greeting.** The conversation is already underway. Do NOT start your response with "Good day", "Hello", "Good morning", or any other greeting. Jump straight into your answer.

3. **Use concrete numbers and KPIs.** When the consultant asks about metrics, cite the values from the KPI section. Example: "Our reject rate is currently at 4.2%, we want to get it below 2%."

4. {length_rule}

5. **Make plausible assumptions for gaps.** If the consultant asks about something not explicitly in your profile but that a managing director would typically know, give a plausible answer consistent with the company profile.

6. **Show genuine interest.** You are in this consultation because you genuinely want to know if AI can help your company. Occasionally ask follow-up questions when something is unclear.

7. **Do NOT invent facts** that contradict your profile. If you truly don't know something, say: "I'd have to check that internally" or "I don't have exact figures for that."

8. **No AI jargon.** Don't use terms like "machine learning", "training data", "inference" — unless the consultant has explained them to you.

9. **Stay consistent.** Don't contradict earlier statements in the conversation.

10. **Step transitions.** Do not suggest moving on to the next topic yourself. Keep answering the consultant's questions and provide relevant details from your company profile. Agree to move to the next step when: (a) the consultant recommends proceeding, or (b) all relevant information has already been discussed and no open questions remain.

11. **Push back on repeated questions.** If the consultant asks something already answered earlier in the conversation, point it out briefly and refer back: "As I mentioned, [short recap of your earlier answer]. Is there something more specific you need?" Do not give the same long answer again.

12. **No markdown.** Write in natural flowing prose. Do not use any markdown formatting: no headers (###), no horizontal rules (---), no bullet points (*), no bold (**text**), no code blocks.

---

## 7. Conversation Context
{conversation_context}

---

## 8. Consultant's Latest Message
{last_ai_message}

---

## Your Task

Respond to the consultant's latest message. Stay in your role as managing director. Reference the facts from your company profile."""

    return prompt


class UserAgentConfig(BaseModel):
    """Configuration for the user agent LLM (simulates company client)."""
    model: str = "mistral/mistral-small-latest"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None


class GenerateResponseRequest(BaseModel):
    user_agent_config: Optional[UserAgentConfig] = None


@router.post("/{session_uuid}/generate-response")
async def generate_persona_response(
    session_uuid: str,
    persona_id: str,
    message_type: str = "consultation",  # consultation, business_case, or cost_estimation
    body: Optional[GenerateResponseRequest] = Body(default=None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Generate a user response based on the persona and current conversation.

    Args:
        session_uuid: The session to generate response for
        persona_id: The persona to role-play as
        message_type: Type of conversation (consultation, business_case, cost_estimation)
        body.user_agent_config: Optional separate LLM config for the user agent.
                          If not provided, uses the session's consultant LLM.
                          For benchmarking, set this to a constant model (e.g., mistral-small)
                          while varying the consultant LLM.
        x_api_key: API key header (used if user_agent_config.api_key not set)
    """

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
    language = db_session.prompt_language or "en"
    system_prompt = build_user_agent_prompt(
        persona, conversation_context, last_ai_message,
        message_type=message_type, language=language
    )

    # Determine model and API settings for user agent
    # If user_agent_config is provided, use it (for benchmarking with constant user agent)
    # Otherwise fall back to session's consultant LLM
    user_agent_config = body.user_agent_config if body else None
    if user_agent_config:
        model = user_agent_config.model
        api_base = user_agent_config.api_base
        api_key = user_agent_config.api_key or x_api_key
    else:
        model = db_session.llm_model or "mistral/mistral-small-latest"
        api_base = db_session.llm_api_base
        api_key = x_api_key

    # Call LLM to generate response
    ua_temperature = user_agent_config.temperature if user_agent_config and user_agent_config.temperature is not None else 0.7
    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Please respond to the consultant's message as the client."}
            ],
            "temperature": ua_temperature,
            "max_tokens": 1000,
            "timeout": 120  # Increase timeout to 120 seconds
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        generated_response = extract_content(response)

        return {
            "response": generated_response,
            "persona_id": persona_id,
            "company_name": persona["company"]["name"],
            "user_agent_model": model,
            "step_complete": False,
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
            target_str = f" (target: {kpi_data['target']}{kpi_data['unit']})" if 'target' in kpi_data else ""
            profile_parts.append(f"- {kpi_name.replace('_', ' ').title()}: {kpi_data['value']}{kpi_data['unit']}{target_str} - {kpi_data.get('note', '')}")
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


class GenerateIdeasRequest(BaseModel):
    previous_ideas: Optional[List[str]] = None
    user_agent_config: Optional[UserAgentConfig] = None


@router.post("/{session_uuid}/generate-ideas")
async def generate_persona_ideas(
    session_uuid: str,
    persona_id: str,
    round_number: int = 1,
    body: Optional[GenerateIdeasRequest] = Body(default=None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Generate ideas for 6-3-5 brainwriting based on persona.

    In round 1 with no previous ideas, the first idea is always the persona's
    focus_idea (the idea they came to the consultation with). The remaining
    2 ideas are generated by the LLM.

    Args:
        user_agent_config (in body): Optional separate LLM for the user agent.
                                     For benchmarking, keep this constant while
                                     varying the consultant LLM.
    """
    from ..models import IdeaSheet, Idea

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

    company = persona["company"]
    focus_idea = persona["focus_idea"]

    # Build context from previous ideas if provided
    previous_ideas = body.previous_ideas if body and body.previous_ideas else []

    # Check if this is the first round with no previous ideas - use focus_idea as first idea
    is_initial_round = round_number == 1 and len(previous_ideas) == 0

    if is_initial_round:
        # First idea is the persona's focus idea
        first_idea = f"{focus_idea['title']}: {focus_idea['description']}"
        ideas_to_generate = 2  # Generate only 2 more ideas
    else:
        first_idea = None
        ideas_to_generate = 3  # Generate all 3 ideas

    previous_context = ""
    if previous_ideas and len(previous_ideas) > 0:
        previous_context = f"""
## Previous Ideas on this Sheet (build upon these):
{chr(10).join([f"- {idea}" for idea in previous_ideas])}

Your task is to ADD NEW ideas that build upon or complement these existing ideas.
"""

    # Get maturity information
    digital_maturity = company.get("digitalization_maturity", {})
    maturity_level = digital_maturity.get("level", "Unknown")
    maturity_name = digital_maturity.get("level_name", "Unknown")
    maturity_details = digital_maturity.get("details", {})
    maturity_details_text = chr(10).join([f"- {k}: {v}" for k, v in maturity_details.items()]) if maturity_details else "Not specified"

    prompt = f"""You are participating in a 6-3-5 brainwriting session for digitalization ideas.

## Company Context
**Company:** {company['name']}
**Industry:** {company['sub_industry']}
**Size:** {company['size_employees']} employees

**Digitalization Maturity Level:** {maturity_level} - {maturity_name}
{maturity_details_text}

**Current Challenges:**
{chr(10).join([f"- {c}" for c in company.get("current_challenges", [])])}

**Project Focus:** {focus_idea['title']}
{focus_idea['description']}

## Your Task
Generate exactly {ideas_to_generate} creative, practical digitalization ideas for this company.
{previous_context}

## Guidelines
1. Each idea should be 1-2 sentences, concise but specific
2. Focus on practical, implementable solutions
3. Consider the company's size, industry, challenges, AND maturity level
4. Ideas should be appropriate for a company at maturity level {maturity_level} ({maturity_name})
5. Ideas should relate to the project focus: {focus_idea['title']}
6. Be creative but realistic - don't suggest overly advanced solutions for low-maturity companies

Respond with exactly {ideas_to_generate} ideas, one per line, without numbering or bullet points."""

    # Determine model and API settings for user agent
    user_agent_config = body.user_agent_config if body else None
    if user_agent_config:
        model = user_agent_config.model
        api_base = user_agent_config.api_base
        api_key = user_agent_config.api_key or x_api_key
    else:
        model = db_session.llm_model or "mistral/mistral-small-latest"
        api_base = db_session.llm_api_base
        api_key = x_api_key

    ua_temperature = user_agent_config.temperature if user_agent_config and user_agent_config.temperature is not None else 0.8
    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Generate {ideas_to_generate} ideas now."}
            ],
            "temperature": ua_temperature,
            "max_tokens": 1000,
            "timeout": 120
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        generated_text = extract_content(response)

        # Parse ideas (split by newlines, clean up)
        generated_ideas = [line.strip() for line in generated_text.strip().split('\n') if line.strip()]
        # Remove any numbering or bullets
        generated_ideas = [idea.lstrip('0123456789.-) ').strip() for idea in generated_ideas]
        # Take only the requested number
        generated_ideas = generated_ideas[:ideas_to_generate]

        # Combine: first_idea (if initial round) + generated ideas
        if first_idea:
            ideas = [first_idea] + generated_ideas
        else:
            ideas = generated_ideas

        # Ensure we have exactly 3 ideas
        ideas = ideas[:3]

        return {
            "ideas": ideas,
            "persona_id": persona_id,
            "company_name": company["name"],
            "round_number": round_number,
            "user_agent_model": model,
            "focus_idea_included": is_initial_round  # Indicate if focus_idea was used
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate ideas: {str(e)}")


class AutoVoteRequest(BaseModel):
    user_agent_config: Optional[UserAgentConfig] = None


@router.post("/{session_uuid}/auto-vote-clusters")
async def auto_vote_clusters(
    session_uuid: str,
    persona_id: str,
    body: Optional[AutoVoteRequest] = Body(default=None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Auto-generate cluster votes based on persona's priorities.

    Args:
        user_agent_config (in body): Optional separate LLM for the user agent.
    """
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

    # Get clusters from session JSON
    if not db_session.idea_clusters:
        raise HTTPException(status_code=400, detail="No clusters to vote on. Generate clusters first.")

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        clusters = clusters_data.get("clusters", [])
    except:
        raise HTTPException(status_code=400, detail="Invalid cluster data")

    if not clusters:
        raise HTTPException(status_code=400, detail="No clusters to vote on")

    company = persona["company"]
    focus_idea = persona["focus_idea"]

    # Build cluster descriptions
    cluster_text = "\n".join([
        f"Cluster {c['id']}: {c['name']} - {c['description']}"
        for c in clusters
    ])

    prompt = f"""You are deciding how to allocate 3 voting points across idea clusters for a digitalization project.

## Company Context
**Company:** {company['name']}
**Industry:** {company['sub_industry']}
**Focus Area:** {focus_idea['title']} - {focus_idea['description']}

**Strategic Goals:**
{company['strategic_goals']}

## Available Clusters
{cluster_text}

## Task
Allocate exactly 3 points across these clusters based on which ones best align with the company's focus and strategic goals.
You can put all 3 points on one cluster, or distribute them (e.g., 2+1 or 1+1+1).

Respond in this exact format (one line per cluster that gets points):
CLUSTER_ID:POINTS

Example:
5:2
3:1

Only include clusters that receive at least 1 point."""

    # Determine model and API settings for user agent
    user_agent_config = body.user_agent_config if body else None
    if user_agent_config:
        model = user_agent_config.model
        api_base = user_agent_config.api_base
        api_key = user_agent_config.api_key or x_api_key
    else:
        model = db_session.llm_model or "mistral/mistral-small-latest"
        api_base = db_session.llm_api_base
        api_key = x_api_key

    ua_temperature = user_agent_config.temperature if user_agent_config and user_agent_config.temperature is not None else 0.3
    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Allocate your 3 points now."}
            ],
            "temperature": ua_temperature,
            "max_tokens": 100,
            "timeout": 60
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        generated_text = extract_content(response)

        # Parse votes
        votes = {}
        valid_cluster_ids = {c['id'] for c in clusters}
        for line in generated_text.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                parts = line.split(':')
                try:
                    cluster_id = int(parts[0].strip())
                    points = int(parts[1].strip())
                    if cluster_id in valid_cluster_ids:
                        votes[cluster_id] = points
                except (ValueError, IndexError):
                    continue

        # Validate total is 3
        total = sum(votes.values())
        if total != 3 and len(votes) > 0:
            # Normalize to 3 points
            factor = 3 / total
            votes = {k: max(1, round(v * factor)) for k, v in votes.items()}
            # Adjust if still not 3
            diff = 3 - sum(votes.values())
            if diff != 0:
                first_key = list(votes.keys())[0]
                votes[first_key] = max(1, votes[first_key] + diff)

        return {
            "votes": votes,
            "persona_id": persona_id,
            "company_name": company["name"],
            "user_agent_model": model
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate votes: {str(e)}")


@router.post("/{session_uuid}/auto-vote-ideas")
async def auto_vote_ideas(
    session_uuid: str,
    persona_id: str,
    body: Optional[AutoVoteRequest] = Body(default=None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Auto-generate idea votes based on persona's priorities.

    Args:
        user_agent_config (in body): Optional separate LLM for the user agent.
    """
    from ..models import Idea

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

    # Get selected cluster from session JSON
    if not db_session.selected_cluster_id or not db_session.idea_clusters:
        raise HTTPException(status_code=400, detail="No cluster selected. Complete Phase 1 first.")

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        selected_cluster = next(
            (c for c in clusters_data.get("clusters", []) if c["id"] == db_session.selected_cluster_id),
            None
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid cluster data")

    if not selected_cluster:
        raise HTTPException(status_code=400, detail="Selected cluster not found")

    # Get ideas in the cluster
    idea_ids = selected_cluster.get("idea_ids", [])
    ideas = db.query(Idea).filter(
        Idea.id.in_(idea_ids)
    ).all()

    if not ideas:
        raise HTTPException(status_code=400, detail="No ideas to vote on")

    company = persona["company"]
    focus_idea = persona["focus_idea"]

    # Build idea descriptions
    idea_text = "\n".join([
        f"Idea {i.id}: {i.content}"
        for i in ideas
    ])

    prompt = f"""You are deciding how to allocate 3 voting points across specific ideas for a digitalization project.

## Company Context
**Company:** {company['name']}
**Industry:** {company['sub_industry']}
**Focus Area:** {focus_idea['title']} - {focus_idea['description']}

**Strategic Goals:**
{company['strategic_goals']}

## Available Ideas
{idea_text}

## Task
Allocate exactly 3 points across these ideas based on which ones would be most valuable and feasible for the company.
Consider alignment with strategic goals, feasibility, and potential impact.

Respond in this exact format (one line per idea that gets points):
IDEA_ID:POINTS

Example:
12:2
8:1

Only include ideas that receive at least 1 point."""

    # Determine model and API settings for user agent
    user_agent_config = body.user_agent_config if body else None
    if user_agent_config:
        model = user_agent_config.model
        api_base = user_agent_config.api_base
        api_key = user_agent_config.api_key or x_api_key
    else:
        model = db_session.llm_model or "mistral/mistral-small-latest"
        api_base = db_session.llm_api_base
        api_key = x_api_key

    ua_temperature = user_agent_config.temperature if user_agent_config and user_agent_config.temperature is not None else 0.3
    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Allocate your 3 points now."}
            ],
            "temperature": ua_temperature,
            "max_tokens": 100,
            "timeout": 60
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

        response = completion(**completion_kwargs)
        generated_text = extract_content(response)

        # Parse votes
        votes = {}
        idea_id_set = {i.id for i in ideas}
        for line in generated_text.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                parts = line.split(':')
                try:
                    idea_id = int(parts[0].strip())
                    points = int(parts[1].strip())
                    if idea_id in idea_id_set:
                        votes[idea_id] = points
                except (ValueError, IndexError):
                    continue

        # Validate total is 3
        total = sum(votes.values())
        if total != 3 and len(votes) > 0:
            factor = 3 / total
            votes = {k: max(1, round(v * factor)) for k, v in votes.items()}
            diff = 3 - sum(votes.values())
            if diff != 0:
                first_key = list(votes.keys())[0]
                votes[first_key] = max(1, votes[first_key] + diff)

        return {
            "votes": votes,
            "persona_id": persona_id,
            "company_name": company["name"],
            "user_agent_model": model
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate votes: {str(e)}")


@router.post("/{session_uuid}/inject-focus-idea")
async def inject_focus_idea(
    session_uuid: str,
    persona_id: str,
    db: Session = Depends(get_db)
):
    """Inject the persona's focus idea directly as the top-voted idea.

    Bypasses Steps 2 (6-3-5 brainstorming) and 3 (prioritization) entirely.
    Creates the minimum required DB records so that consultation/start picks up
    the focus idea as the top idea, identical to running the full ideation flow.

    Use this when evaluating consultation quality (Steps 4–6) without spending
    API budget on ideation.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    personas = load_personas()
    persona = next((p for p in personas if p["persona_id"] == persona_id), None)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

    focus = persona.get("focus_idea", {})
    focus_content = f"{focus.get('title', '')}: {focus.get('description', '')}"

    # Create a placeholder participant
    participant = Participant(
        session_id=db_session.id,
        participant_uuid=str(uuid_lib.uuid4()),
        name=f"[eval] {persona.get('company', {}).get('name', persona_id)}",
        connection_status="connected",
    )
    db.add(participant)
    db.flush()

    # Create an idea sheet
    sheet = IdeaSheet(
        session_id=db_session.id,
        sheet_number=1,
        current_participant_id=participant.id,
        current_round=1,
    )
    db.add(sheet)
    db.flush()

    # Create the focus idea
    idea = Idea(
        sheet_id=sheet.id,
        participant_id=participant.id,
        round_number=1,
        idea_number=1,
        content=focus_content,
    )
    db.add(idea)
    db.flush()

    # Create a prioritization vote so it ranks first
    vote = Prioritization(
        session_id=db_session.id,
        idea_id=idea.id,
        participant_id=participant.id,
        vote_type="score",
        vote_phase="idea",
        score=10,
    )
    db.add(vote)
    db.commit()

    return {
        "injected": True,
        "persona_id": persona_id,
        "focus_idea": focus_content,
        "idea_id": idea.id,
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
    language = db_session.prompt_language or "en"
    system_prompt = build_user_agent_prompt(
        persona, conversation_context, last_ai_message,
        message_type=message_type, language=language
    )

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
                "max_tokens": 1000,
                "stream": True,
                "timeout": 120  # Increase timeout to 120 seconds
            }

            if api_key:
                completion_kwargs["api_key"] = api_key
            if api_base:
                completion_kwargs["api_base"] = api_base
            apply_model_params(completion_kwargs)

            stream = completion(**completion_kwargs)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield format_sse_data(chunk.choices[0].delta.content)

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
