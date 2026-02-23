"""Service for AI-powered consultation in Step 4 using LiteLLM (multi-provider)."""

from typing import List, Optional, Dict, Generator
from sqlalchemy.orm import Session
import logging

from ..utils.llm import LLMCaller, strip_think_tokens, extract_content
from ..utils.security import validate_and_sanitize_message

logger = logging.getLogger(__name__)

from ..models import (
    Session as SessionModel,
    ConsultationMessage,
    ConsultationFinding,
    CompanyInfo,
    Idea,
    IdeaSheet,
    Prioritization,
    MaturityAssessment
)
from .default_prompts import get_prompt
from .company_profile_service import get_profile_as_context
from ..utils.sse import format_sse_data, format_sse_error

# Maturity level guidance for dynamic injection (only relevant levels shown to reduce prompt size)
MATURITY_GUIDANCE = {
    "en": {
        1: ("Computerization", "Company has basic digital tools but they're isolated. Focus on: digitizing manual processes, introducing basic software (ERP, CRM basics), standardizing data formats. Avoid any AI/ML talk. Use very simple language, explain every technical term. Recommend: spreadsheet automation, basic databases, document management."),
        2: ("Connectivity", "Systems exist but aren't connected. Focus on: integrating existing systems, establishing data flows between departments, APIs and interfaces. Still too early for AI. Use simple language with some technical terms. Recommend: system integration, central databases, automated data exchange, basic reporting."),
        3: ("Visibility", "Real-time data is captured - they can see what's happening. Focus on: dashboards, KPI monitoring, basic analytics, data quality improvement. Ready for simple rule-based automation and basic ML (e.g., anomaly detection). Balance explanation with technical detail. Recommend: BI tools, real-time dashboards, simple predictive models, data warehousing."),
        4: ("Transparency", "They understand WHY things happen through analytics. Focus on: root cause analysis, process mining, advanced analytics, ML for pattern recognition. Ready for supervised ML models. Use technical terms more freely. Recommend: predictive maintenance, demand forecasting, quality prediction, recommendation systems."),
        5: ("Predictive Capacity", "Can forecast what WILL happen. Focus on: predictive models, simulation, scenario planning, proactive optimization. Ready for advanced ML/AI, deep learning where appropriate. Discuss architecture and trade-offs openly. Recommend: digital twins, advanced forecasting, prescriptive analytics, intelligent automation."),
        6: ("Adaptability", "Systems can autonomously adapt and optimize. Focus on: self-optimizing systems, autonomous decision-making, continuous learning, AI-driven transformation. Full technical discussions appropriate. Recommend: autonomous systems, reinforcement learning, adaptive processes, AI-native architectures."),
    },
    "de": {
        1: ("Computerisierung", "Unternehmen hat digitale Grundwerkzeuge, aber isoliert. Fokus auf: manuelle Prozesse digitalisieren, Basissoftware einführen (ERP, CRM Grundlagen), Datenformate standardisieren. Keine KI/ML-Themen. Sehr einfache Sprache, jeden Fachbegriff erklären. Empfehlungen: Tabellenautomatisierung, einfache Datenbanken, Dokumentenmanagement."),
        2: ("Konnektivität", "Systeme existieren, sind aber nicht verbunden. Fokus auf: bestehende Systeme integrieren, Datenflüsse zwischen Abteilungen etablieren, APIs und Schnittstellen. Noch zu früh für KI. Einfache Sprache mit einigen Fachbegriffen. Empfehlungen: Systemintegration, zentrale Datenbanken, automatisierter Datenaustausch, Basis-Reporting."),
        3: ("Sichtbarkeit", "Echtzeitdaten werden erfasst - sie können sehen, was passiert. Fokus auf: Dashboards, KPI-Monitoring, einfache Analysen, Datenqualität verbessern. Bereit für einfache regelbasierte Automatisierung und Basis-ML (z.B. Anomalieerkennung). Balance zwischen Erklärung und technischen Details. Empfehlungen: BI-Tools, Echtzeit-Dashboards, einfache Vorhersagemodelle, Data Warehousing."),
        4: ("Transparenz", "Sie verstehen WARUM Dinge passieren durch Analysen. Fokus auf: Ursachenanalyse, Process Mining, erweiterte Analysen, ML für Mustererkennung. Bereit für überwachte ML-Modelle. Fachbegriffe freier verwenden. Empfehlungen: Predictive Maintenance, Bedarfsprognosen, Qualitätsvorhersage, Empfehlungssysteme."),
        5: ("Prognosefähigkeit", "Kann vorhersagen, was passieren WIRD. Fokus auf: Vorhersagemodelle, Simulation, Szenarioplanung, proaktive Optimierung. Bereit für fortgeschrittenes ML/KI, Deep Learning wo sinnvoll. Architektur und Abwägungen offen diskutieren. Empfehlungen: Digitale Zwillinge, fortgeschrittene Prognosen, präskriptive Analysen, intelligente Automatisierung."),
        6: ("Adaptierbarkeit", "Systeme können autonom anpassen und optimieren. Fokus auf: selbstoptimierende Systeme, autonome Entscheidungsfindung, kontinuierliches Lernen, KI-getriebene Transformation. Volle technische Diskussionen angemessen. Empfehlungen: Autonome Systeme, Reinforcement Learning, adaptive Prozesse, KI-native Architekturen."),
    }
}


class ConsultationService:
    """AI consultant service using LiteLLM for guided interviews."""

    def __init__(
        self,
        db: Session,
        model: str = "mistral/mistral-small-latest",
        custom_prompts: Optional[Dict[str, str]] = None,
        language: str = "en",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        chat_temperature: Optional[float] = None,
        extraction_temperature: Optional[float] = None
    ):
        self.db = db
        self.model = model
        self.custom_prompts = custom_prompts or {}
        self.language = language
        self.api_key = api_key
        self.api_base = api_base
        self.chat_temperature = chat_temperature
        self.extraction_temperature = extraction_temperature
        # LLM caller with automatic retry logic for transient failures
        self._llm = LLMCaller(
            model=model,
            api_key=api_key,
            api_base=api_base,
            max_retries=3
        )

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000):
        """Call LLM with automatic retry on transient failures."""
        if self.chat_temperature is not None:
            temperature = self.chat_temperature
        return self._llm.call(messages, temperature, max_tokens, timeout=120)

    def _call_llm_stream(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000) -> Generator:
        """Call LLM with streaming and automatic retry on transient failures."""
        if self.chat_temperature is not None:
            temperature = self.chat_temperature
        return self._llm.call_stream(messages, temperature, max_tokens, timeout=120)

    def _call_llm_extraction(self, messages: List[Dict], temperature: float = 0.3, max_tokens: int = 2000):
        """Call LLM for extraction tasks with separate temperature control."""
        if self.extraction_temperature is not None:
            temperature = self.extraction_temperature
        return self._llm.call(messages, temperature, max_tokens, timeout=120)

    def start_consultation(self, session_uuid: str) -> Dict:
        """
        Start a new consultation session.
        Creates the initial system message and first AI response.
        """
        db_session = self._get_session(session_uuid)

        # Check if consultation already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id
        ).count()

        if existing_messages > 0:
            return {"status": "already_started", "message_count": existing_messages}

        # Build context from previous steps
        context = self._build_consultation_context(db_session)

        # Create system message (behavioral rules only)
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content
        )
        self.db.add(system_msg)

        # Build context for the initial user message
        context_content = self._build_context_message(context)

        # For the LLM call, include instruction to start
        initial_prompt_for_llm = f"{context_content}\n\n---\nPlease start the consultation with your first message."

        # For storage in history, just save the context (without "please start" instruction)
        context_for_storage = f"[SESSION CONTEXT]\n{context_content}\n[END CONTEXT - The consultant has already introduced themselves above. Continue the conversation.]"

        # Save the context message (without the start instruction)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=context_for_storage
        )
        self.db.add(initial_user_msg)

        # Messages for initial LLM call: system rules, then user message with start instruction
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": initial_prompt_for_llm}
        ]

        response = self._call_llm(messages, temperature=0.7, max_tokens=1000)

        ai_response = response.choices[0].message.content

        # Save AI response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=ai_response
        )
        self.db.add(ai_msg)
        self.db.commit()

        return {
            "status": "started",
            "initial_message": ai_response
        }

    def start_consultation_stream(self, session_uuid: str) -> Generator[str, None, None]:
        """
        Start consultation with streaming response.
        Yields chunks of the AI response as they arrive.
        """
        db_session = self._get_session(session_uuid)

        # Check if consultation already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id
        ).count()

        if existing_messages > 0:
            yield "data: {\"status\": \"already_started\"}\n\n"
            return

        # Build context from previous steps
        context = self._build_consultation_context(db_session)

        # Create system message (behavioral rules only)
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content
        )
        self.db.add(system_msg)

        # Build context for the initial user message
        context_content = self._build_context_message(context)

        # For the LLM call, include instruction to start
        initial_prompt_for_llm = f"{context_content}\n\n---\nPlease start the consultation with your first message."

        # For storage in history, just save the context (without "please start" instruction)
        # This prevents confusion in subsequent calls where the model might re-read this
        context_for_storage = f"[SESSION CONTEXT]\n{context_content}\n[END CONTEXT - The consultant has already introduced themselves above. Continue the conversation.]"

        # Save the context message (without the start instruction)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=context_for_storage
        )
        self.db.add(initial_user_msg)
        self.db.commit()

        # Messages for initial LLM call: system rules, then user message with start instruction
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": initial_prompt_for_llm}
        ]

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = strip_think_tokens(chunk.choices[0].delta.content)
                    full_response += content
                    yield format_sse_data(content)

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Stream connection error (recoverable): {e}")
            yield format_sse_error(f"Connection interrupted: {str(e)}", "connection_error")
            # Save partial response if any
            if full_response:
                ai_msg = ConsultationMessage(
                    session_id=db_session.id,
                    role="assistant",
                    content=full_response + "\n\n[Response interrupted due to connection error]"
                )
                self.db.add(ai_msg)
                self.db.commit()
            return

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield format_sse_error(f"Stream error: {str(e)}", "error")
            return

        # Save the complete response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=full_response
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def save_user_message(self, session_uuid: str, user_message: str) -> Dict:
        """
        Save a user message without generating AI response.
        Used when the user is answering questions (no auto-reply needed).
        """
        db_session = self._get_session(session_uuid)

        # SECURITY: Validate and sanitize user input
        sanitized_message, is_safe, warning = validate_and_sanitize_message(user_message)
        if not is_safe:
            logger.warning(f"Blocked potentially unsafe message: {warning}")
            raise ValueError(f"Invalid message content: {warning}. Please rephrase your message.")

        # Check for duplicate - don't save if the last USER message has the same content
        last_user_msg = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role == "user"
        ).order_by(ConsultationMessage.created_at.desc()).first()

        if last_user_msg and last_user_msg.content == sanitized_message:
            logger.warning(f"Skipping duplicate user message: {sanitized_message[:50]}...")
            return {
                "message_id": last_user_msg.id,
                "content": sanitized_message,
                "role": "user",
                "duplicate": True
            }

        # Save user message
        logger.info(f"Saving user message: {sanitized_message[:50]}...")
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message
        )
        self.db.add(user_msg)
        self.db.commit()

        return {
            "message_id": user_msg.id,
            "content": sanitized_message,
            "role": "user"
        }

    def send_message(self, session_uuid: str, user_message: str) -> Dict:
        """
        Send a user message and get AI response.
        """
        db_session = self._get_session(session_uuid)

        # SECURITY: Validate and sanitize user input
        sanitized_message, is_safe, warning = validate_and_sanitize_message(user_message)
        if not is_safe:
            logger.warning(f"Blocked potentially unsafe message: {warning}")
            raise ValueError(f"Invalid message content: {warning}. Please rephrase your message.")

        # Check for context updates before processing (saves to DB if changes detected)
        self._inject_context_update_if_needed(db_session)

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history (includes any context updates from DB)
        messages = self._get_conversation_history(db_session.id)

        # Generate AI response
        response = self._call_llm(messages, temperature=0.7, max_tokens=1000)

        ai_response = response.choices[0].message.content

        # Save AI response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=ai_response
        )
        self.db.add(ai_msg)
        self.db.commit()

        # Check if we should extract findings
        self._try_extract_findings(db_session, messages, ai_response)

        return {
            "response": ai_response,
            "message_id": ai_msg.id
        }

    def send_message_stream(self, session_uuid: str, user_message: str) -> Generator[str, None, None]:
        """
        Send a user message and stream AI response.
        Yields chunks as they arrive.
        """
        db_session = self._get_session(session_uuid)

        # SECURITY: Validate and sanitize user input
        sanitized_message, is_safe, warning = validate_and_sanitize_message(user_message)
        if not is_safe:
            logger.warning(f"Blocked potentially unsafe message: {warning}")
            yield format_sse_error(f"Invalid message content: {warning}", "validation_error")
            return

        # Check for context updates before processing (saves to DB if changes detected)
        self._inject_context_update_if_needed(db_session)

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history (includes any context updates from DB)
        messages = self._get_conversation_history(db_session.id)

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = strip_think_tokens(chunk.choices[0].delta.content)
                    full_response += content
                    yield format_sse_data(content)

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Stream connection error (recoverable): {e}")
            yield format_sse_error(f"Connection interrupted: {str(e)}", "connection_error")
            if full_response:
                ai_msg = ConsultationMessage(
                    session_id=db_session.id,
                    role="assistant",
                    content=full_response + "\n\n[Response interrupted due to connection error]"
                )
                self.db.add(ai_msg)
                self.db.commit()
            return

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield format_sse_error(f"Stream error: {str(e)}", "error")
            return

        # Save the complete response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=full_response
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def request_ai_response_stream(self, session_uuid: str) -> Generator[str, None, None]:
        """
        Request AI response based on current conversation (no new user message).
        Used when user wants AI feedback after answering questions.
        """
        # Ensure we see the latest committed data (important for test mode flow)
        self.db.expire_all()

        db_session = self._get_session(session_uuid)

        # Check for context updates before processing (saves to DB if changes detected)
        self._inject_context_update_if_needed(db_session)

        # Get conversation history (includes any context updates from DB)
        messages = self._get_conversation_history(db_session.id)

        # Log the conversation being sent (debug level)
        logger.debug(f"Sending {len(messages)} messages to LLM")

        if len(messages) < 2:
            yield "data: {\"error\": \"No conversation history\"}\n\n"
            return

        # Check that the last message is from user - don't generate consecutive assistant messages
        # (This prevents issues when duplicate user messages are skipped)
        last_msg = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id
        ).order_by(ConsultationMessage.created_at.desc()).first()

        if last_msg and last_msg.role == "assistant":
            logger.warning("Last message is already from assistant - skipping AI response to prevent consecutive assistant messages")
            yield "data: [DONE]\n\n"
            return

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = strip_think_tokens(chunk.choices[0].delta.content)
                    full_response += content
                    yield format_sse_data(content)

        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Stream connection error (recoverable): {e}")
            yield format_sse_error(f"Connection interrupted: {str(e)}", "connection_error")
            if full_response:
                ai_msg = ConsultationMessage(
                    session_id=db_session.id,
                    role="assistant",
                    content=full_response + "\n\n[Response interrupted due to connection error]"
                )
                self.db.add(ai_msg)
                self.db.commit()
            return

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield format_sse_error(f"Stream error: {str(e)}", "error")
            return

        # Save the complete response
        logger.info(f"Saving AI response: {full_response[:50]}...")
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=full_response
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def get_messages(self, session_uuid: str) -> List[Dict]:
        """Get all consultation messages."""
        db_session = self._get_session(session_uuid)

        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role != "system"  # Exclude system messages
        ).order_by(ConsultationMessage.created_at).all()

        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
            # Filter out the initial trigger message (not user-visible)
            if "Please start the consultation" not in m.content
        ]

    def get_findings(self, session_uuid: str) -> Dict:
        """Get extracted consultation findings (CRISP-DM Business Understanding)."""
        db_session = self._get_session(session_uuid)

        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id
        ).all()

        # CRISP-DM Business Understanding categories
        result = {
            "company_profile": None,
            "business_objectives": None,
            "situation_assessment": None,
            "ai_goals": None,
            "project_plan": None,
            # Legacy fields for backward compatibility
            "project": None,
            "risks": None,
            "end_user": None,
            "business_case": None,
            "implementation": None
        }

        for f in findings:
            result[f.factor_type] = f.finding_text

        return result

    def extract_findings_now(self, session_uuid: str) -> Dict:
        """Force extraction of findings from current conversation (CRISP-DM format)."""
        db_session = self._get_session(session_uuid)
        messages = self._get_conversation_history(db_session.id)

        # Get extraction prompt from templates
        extraction_prompt = get_prompt(
            "extraction_summary",
            self.language,
            self.custom_prompts
        )

        # Prepend verified structured data so the LLM uses real facts for the COMPANY PROFILE section
        extraction_prompt = self._build_verified_data_block(db_session, session_uuid) + extraction_prompt

        messages.append({"role": "user", "content": extraction_prompt})

        response = self._call_llm_extraction(messages, max_tokens=2000)

        summary = extract_content(response)

        # Save CRISP-DM Business Understanding findings
        # Extract company profile summary
        company_profile = (
            self._extract_section(summary, "COMPANY PROFILE") or
            self._extract_section(summary, "UNTERNEHMENSPROFIL")
        )
        self._save_finding(db_session.id, "company_profile", company_profile)

        # Try new format first, fall back to old format for compatibility
        business_obj = (
            self._extract_section(summary, "BUSINESS OBJECTIVES") or
            self._extract_section(summary, "GESCHÄFTSZIELE") or
            self._extract_section(summary, "PROJECT RECOMMENDATION")
        )
        self._save_finding(db_session.id, "business_objectives", business_obj)

        situation = (
            self._extract_section(summary, "SITUATION ASSESSMENT") or
            self._extract_section(summary, "SITUATIONSBEWERTUNG")
        )
        self._save_finding(db_session.id, "situation_assessment", situation)

        ai_goals = (
            self._extract_section(summary, "AI/DATA MINING GOALS") or
            self._extract_section(summary, "KI/DATA-MINING-ZIELE") or
            self._extract_section(summary, "AI/DATA-MINING GOALS") or
            self._extract_section(summary, "BUSINESS CASE")
        )
        self._save_finding(db_session.id, "ai_goals", ai_goals)

        project_plan = (
            self._extract_section(summary, "PROJECT PLAN") or
            self._extract_section(summary, "PROJEKTPLAN") or
            self._extract_section(summary, "IMPLEMENTATION STEPS")
        )
        self._save_finding(db_session.id, "project_plan", project_plan)

        if not any([company_profile, business_obj, situation, ai_goals, project_plan]):
            logger.warning(
                "Consultation extraction produced no structured sections for session %s. "
                "LLM response (first 500 chars): %s",
                session_uuid, summary[:500] if summary else "(empty)"
            )

        self.db.commit()

        return {
            "summary": summary,
            "findings": self.get_findings(session_uuid)
        }

    def extract_findings_incremental(self, session_uuid: str) -> Dict:
        """
        Extract findings incrementally from recent conversation.
        Uses a lighter prompt for faster, more frequent updates.
        """
        db_session = self._get_session(session_uuid)
        messages = self._get_conversation_history(db_session.id)

        # Only process if we have enough conversation
        non_system_messages = [m for m in messages if m["role"] != "system"]
        if len(non_system_messages) < 4:
            return {"findings": self.get_findings(session_uuid), "updated": False}

        # Use a lighter extraction prompt
        if self.language == "de":
            extraction_prompt = """Basierend auf dem bisherigen Gespräch, extrahiere kurz die wichtigsten Punkte für jede Kategorie (nur wenn im Gespräch erwähnt, sonst "noch nicht besprochen"):

GESCHÄFTSZIELE: [1-2 Sätze zu Zielen/Erfolgsmetriken]
SITUATION: [1-2 Sätze zu Ressourcen/Einschränkungen/Daten]
KI-ZIELE: [1-2 Sätze zu technischen Anforderungen]
PROJEKTPLAN: [1-2 Sätze zu Zeitrahmen/Meilensteinen]

Antworte nur mit diesen 4 Kategorien, kurz und prägnant."""
        else:
            extraction_prompt = """Based on the conversation so far, briefly extract key points for each category (only if discussed, otherwise say "not yet discussed"):

BUSINESS_OBJECTIVES: [1-2 sentences about goals/success metrics]
SITUATION: [1-2 sentences about resources/constraints/data]
AI_GOALS: [1-2 sentences about technical requirements]
PROJECT_PLAN: [1-2 sentences about timeline/milestones]

Respond only with these 4 categories, brief and concise."""

        extraction_messages = messages + [{"role": "user", "content": extraction_prompt}]

        try:
            response = self._call_llm_extraction(extraction_messages, max_tokens=500)
            content = response.choices[0].message.content

            # Parse the response
            def extract_value(text, key):
                import re
                # Normalize bold section headers to plain form before parsing:
                #   **SECTION:** → SECTION:   and   **SECTION**: → SECTION:
                text = re.sub(r'\*\*(\w[\w_/\- ]+):\*\*', r'\1:', text, flags=re.UNICODE)
                text = re.sub(r'\*\*(\w[\w_/\- ]+)\*\*\s*:', r'\1:', text, flags=re.UNICODE)
                # Stop at next plain SECTION: boundary (word chars + colon)
                patterns = [
                    rf"{key}:\s*(.+?)(?=\n\w[\w_/\- ]+:|$)",
                    rf"{key}:\s*(.+?)(?=\n|$)"
                ]
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.UNICODE)
                    if match:
                        value = re.sub(r'^\*+\s*', '', match.group(1).strip())  # strip stray ** markers
                        if value.lower() not in ["not yet discussed", "noch nicht besprochen", ""]:
                            return value
                return None

            # Extract and save each finding
            business_obj = extract_value(content, "BUSINESS_OBJECTIVES") or extract_value(content, "GESCHÄFTSZIELE")
            if business_obj:
                self._save_finding(db_session.id, "business_objectives", business_obj)

            situation = extract_value(content, "SITUATION")
            if situation:
                self._save_finding(db_session.id, "situation_assessment", situation)

            ai_goals = extract_value(content, "AI_GOALS") or extract_value(content, "KI-ZIELE")
            if ai_goals:
                self._save_finding(db_session.id, "ai_goals", ai_goals)

            project_plan = extract_value(content, "PROJECT_PLAN") or extract_value(content, "PROJEKTPLAN")
            if project_plan:
                self._save_finding(db_session.id, "project_plan", project_plan)

            self.db.commit()

            return {"findings": self.get_findings(session_uuid), "updated": True}
        except Exception as e:
            logger.error(f"Error extracting findings incrementally: {e}")
            return {"findings": self.get_findings(session_uuid), "updated": False}

    def _get_session(self, session_uuid: str) -> SessionModel:
        """Get session by UUID."""
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")

        return db_session

    def _build_consultation_context(self, db_session: SessionModel) -> Dict:
        """Build context from all previous steps."""
        # Try to get structured company profile first (more token-efficient)
        company_profile_text = get_profile_as_context(
            self.db, db_session.session_uuid, self.language
        )
        has_structured_profile = company_profile_text and company_profile_text != "No company profile available."

        # Fall back to raw company info if no structured profile
        company_context = []
        if not has_structured_profile:
            company_infos = self.db.query(CompanyInfo).filter(
                CompanyInfo.session_id == db_session.id
            ).all()

            for info in company_infos:
                if info.content:
                    company_context.append({
                        "type": info.info_type,
                        "content": info.content[:2000]  # Limit each entry
                    })

        # Get maturity assessment (Step 1b)
        maturity = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == db_session.id
        ).first()

        maturity_data = None
        if maturity:
            maturity_data = {
                "overall_score": maturity.overall_score,
                "maturity_level": maturity.maturity_level,
                "resources_score": maturity.resources_score,
                "information_systems_score": maturity.information_systems_score,
                "culture_score": maturity.culture_score,
                "organizational_structure_score": maturity.organizational_structure_score,
            }

        # Get ideas and prioritization results
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        all_ideas = []
        for sheet in sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
            for idea in ideas:
                # Get prioritization score if exists
                votes = self.db.query(Prioritization).filter(
                    Prioritization.idea_id == idea.id
                ).all()
                total_points = sum(v.score or 0 for v in votes)

                all_ideas.append({
                    "content": idea.content,
                    "points": total_points
                })

        # Sort by points
        all_ideas.sort(key=lambda x: x["points"], reverse=True)

        return {
            "company_name": db_session.company_name or "the company",
            "company_info": company_context,
            "company_profile_text": company_profile_text if has_structured_profile else None,
            "maturity": maturity_data,
            "ideas": all_ideas,
            "top_idea": all_ideas[0] if all_ideas else None,
            "collaborative_mode": db_session.collaborative_consultation or False
        }

    def _build_system_prompt(self, context: Dict) -> str:
        """Build the system prompt with behavioral rules only."""
        # Build multi-participant section based on mode and language
        collaborative_mode = context.get("collaborative_mode", False)
        if self.language == "de":
            if collaborative_mode:
                multi_participant_section = """## MEHRERE TEILNEHMER
Diese Beratung umfasst mehrere Teilnehmer aus dem Unternehmen. Nachrichten von verschiedenen Personen werden mit ihren Namen in Klammern markiert, z.B. "[Maria]: Unser Budget beträgt etwa 50.000 €".

Wenn mehrere Personen beitragen:
- Sprechen Sie Teilnehmer mit Namen an, wenn Sie auf ihre spezifischen Beiträge antworten
- Fassen Sie Informationen aus verschiedenen Perspektiven zusammen
- Wenn Teilnehmer widersprüchliche Informationen geben, erkennen Sie beide Ansichten an und bitten Sie um Klärung
"""
            else:
                multi_participant_section = ""
        else:
            if collaborative_mode:
                multi_participant_section = """## MULTI-PARTICIPANT MODE
This consultation involves multiple participants from the company. Messages from different people will be marked with their names in brackets, e.g., "[Maria]: Our budget is around €50,000".

When multiple people contribute:
- Address participants by name when responding to their specific input
- Synthesize information from different perspectives
- If participants give conflicting information, acknowledge both views and ask for clarification
"""
            else:
                multi_participant_section = ""

        # Get prompt template (behavioral rules only)
        template = get_prompt(
            "consultation_system",
            self.language,
            self.custom_prompts
        )

        return template.format(multi_participant_section=multi_participant_section)

    def _build_context_message(self, context: Dict) -> str:
        """Build the context message with session-specific data."""
        # Use structured profile if available (more token-efficient)
        company_info_text = context.get("company_profile_text")

        # Fall back to raw company info if no structured profile
        if not company_info_text:
            company_info_text = ""
            for info in context.get("company_info", [])[:3]:
                company_info_text += f"\n[{info['type'].upper()}]\n{info['content']}\n"

        if not company_info_text:
            company_info_text = "No company information provided yet."

        # Format maturity assessment section
        maturity = context.get("maturity")
        if maturity and maturity.get("overall_score"):
            if self.language == "de":
                maturity_section = f"""**Gesamtreifegrad: {maturity['overall_score']:.1f}/6 ({maturity.get('maturity_level', 'Unbekannt')})**
- Ressourcen: {maturity.get('resources_score', 'N/A')}/6
- Informationssysteme: {maturity.get('information_systems_score', 'N/A')}/6
- Kultur: {maturity.get('culture_score', 'N/A')}/6
- Organisationsstruktur: {maturity.get('organizational_structure_score', 'N/A')}/6"""
            else:
                maturity_section = f"""**Overall: {maturity['overall_score']:.1f}/6 ({maturity.get('maturity_level', 'Unknown')})**
- Resources: {maturity.get('resources_score', 'N/A')}/6
- Information Systems: {maturity.get('information_systems_score', 'N/A')}/6
- Culture: {maturity.get('culture_score', 'N/A')}/6
- Organizational Structure: {maturity.get('organizational_structure_score', 'N/A')}/6"""
        else:
            if self.language == "de":
                maturity_section = "Keine Bewertung vorhanden."
            else:
                maturity_section = "No assessment available."

        # Format top ideas - only include ideas with at least 1 vote
        all_ideas = context.get("ideas", [])
        prioritized_ideas = [idea for idea in all_ideas if idea['points'] > 0]

        # If no ideas were prioritized, fall back to top 3 ideas (less context)
        if not prioritized_ideas and all_ideas:
            ideas_to_show = all_ideas[:3]
        else:
            ideas_to_show = prioritized_ideas[:5]

        top_ideas_text = ""
        for i, idea in enumerate(ideas_to_show):
            points_str = f" ({idea['points']} votes)" if idea['points'] > 0 else ""
            top_ideas_text += f"{i+1}. {idea['content']}{points_str}\n"

        if not top_ideas_text:
            if self.language == "de":
                top_ideas_text = "Keine Ideen aus Brainstorming."
            else:
                top_ideas_text = "No ideas from brainstorming."

        # Get focus idea
        top_idea = context.get("top_idea")
        if self.language == "de":
            focus_idea = top_idea["content"] if top_idea else "Allgemeine KI-/Digitalisierungsverbesserungen"
        else:
            focus_idea = top_idea["content"] if top_idea else "General AI/digitalization improvements"

        # Get context template
        template = get_prompt(
            "consultation_context",
            self.language,
            self.custom_prompts
        )

        return template.format(
            company_name=context.get('company_name', 'Unknown'),
            company_info_text=company_info_text,
            maturity_section=maturity_section,
            focus_idea=focus_idea,
            top_ideas_text=top_ideas_text
        )

    def _build_initial_greeting(self, context: Dict) -> str:
        """Build the initial greeting context."""
        top_idea = context.get("top_idea")
        if top_idea:
            return f"Focus on: {top_idea['content']}"
        return "General AI/digitalization consultation"

    def _get_conversation_history(self, session_id: int, summarize_old: bool = True) -> List[Dict]:
        """
        Get conversation history as message list.
        For long conversations (15+ messages), summarizes older messages to preserve context.
        """
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == session_id
        ).order_by(ConsultationMessage.created_at).all()

        message_list = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        # Debug: Log conversation history
        logger.info(f"=== CONVERSATION HISTORY for session {session_id} ===")
        logger.info(f"Total messages: {len(message_list)}")
        for i, m in enumerate(message_list):
            content_preview = m['content'][:100].replace('\n', ' ') if len(m['content']) > 100 else m['content'].replace('\n', ' ')
            logger.info(f"  [{i}] {m['role']}: {content_preview}...")
        logger.info(f"=== END HISTORY ===")

        # If conversation is long, summarize older messages
        if summarize_old and len(message_list) > 15:
            # Keep the system message (first), summarize middle, keep recent messages
            system_msgs = [m for m in message_list if m["role"] == "system"]
            non_system = [m for m in message_list if m["role"] != "system"]

            if len(non_system) > 10:
                # We need to keep enough recent messages, but ensure they START with a user message
                # (Mistral requires user/assistant alternation after system)
                recent_count = 8
                recent_messages = non_system[-recent_count:]

                # If recent_messages starts with assistant, include one more message to get the user
                while recent_messages and recent_messages[0]["role"] == "assistant" and recent_count < len(non_system):
                    recent_count += 1
                    recent_messages = non_system[-recent_count:]

                old_messages = non_system[:-recent_count] if recent_count < len(non_system) else []

                # Create a summary of older messages
                summary_text = self._summarize_old_messages(old_messages)

                if summary_text:
                    summary_msg = {
                        "role": "system",
                        "content": f"[CONVERSATION SUMMARY - Earlier discussion covered:]\n{summary_text}\n[END SUMMARY - Recent messages follow:]"
                    }
                    return system_msgs + [summary_msg] + recent_messages

        return message_list

    def _summarize_old_messages(self, messages: List[Dict]) -> str:
        """Create a brief summary of older messages to preserve context."""
        if not messages:
            return ""

        # Extract key facts mentioned in older messages
        key_points = []
        for msg in messages:
            content = msg.get("content", "")
            # Look for important information patterns
            if msg["role"] == "user":
                # User provided information
                if len(content) > 20:
                    # Truncate long messages but keep the essence
                    key_points.append(f"Client mentioned: {content[:200]}...")
            elif msg["role"] == "assistant":
                # AI asked about or discussed
                if "?" in content:
                    # Was asking a question - the answer should be in subsequent user message
                    pass
                elif len(content) > 50:
                    # AI shared insights
                    key_points.append(f"Discussed: {content[:150]}...")

        # Limit to most important points
        if len(key_points) > 5:
            key_points = key_points[:5]

        return "\n".join(key_points) if key_points else ""

    def _try_extract_findings(self, db_session: SessionModel, messages: List[Dict], last_response: str):
        """Try to extract findings if conversation seems complete."""
        # Simple heuristic: if conversation has 10+ messages and AI mentions summary/conclusion
        message_count = len([m for m in messages if m["role"] != "system"])

        keywords = ["summary", "summarize", "conclude", "in conclusion", "to wrap up", "final recommendation"]
        should_extract = message_count >= 10 and any(kw in last_response.lower() for kw in keywords)

        if should_extract:
            # Auto-extract findings
            pass  # Let user trigger this manually for now

    def _build_verified_data_block(self, db_session: SessionModel, session_uuid: str) -> str:
        """Build a verified facts block to prepend to the extraction prompt.

        This prevents the LLM from hallucinating company KPIs or maturity scores
        by providing the actual structured data as a grounding block.
        """
        lines = []

        # Structured company profile (from company_profile_service)
        profile_context = get_profile_as_context(self.db, session_uuid, self.language)
        if profile_context and profile_context.strip() != "No company profile available.":
            lines.append(profile_context.strip())

        # Maturity assessment scores (direct from DB — no LLM involved)
        maturity = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == db_session.id
        ).first()
        if maturity:
            maturity_lines = [
                f"Digital Maturity (acatech Industry 4.0 Index):",
                f"  Overall: {maturity.overall_score:.1f}/6 ({maturity.maturity_level})",
                f"  Resources: {maturity.resources_score}/6",
                f"  Information Systems: {maturity.information_systems_score}/6",
                f"  Culture: {maturity.culture_score}/6",
                f"  Organizational Structure: {maturity.organizational_structure_score}/6",
            ]
            lines.append("\n".join(maturity_lines))

        if not lines:
            return ""

        if self.language == "de":
            header = (
                "## VERIFIZIERTE UNTERNEHMENSDATEN\n"
                "Die folgenden Fakten sind maschinell verifiziert. "
                "Verwende sie WÖRTLICH im Abschnitt UNTERNEHMENSPROFIL. "
                "Verändere, schätze oder erfinde KEINE Zahlen oder KPIs.\n\n"
            )
        else:
            header = (
                "## VERIFIED COMPANY DATA\n"
                "The following facts are machine-verified. "
                "Use them VERBATIM in the COMPANY PROFILE section. "
                "Do NOT alter, estimate, or invent any numbers or KPIs.\n\n"
            )

        return header + "\n\n".join(lines) + "\n\n---\n\n"

    def _save_finding(self, session_id: int, factor_type: str, text: str):
        """Save or update a finding."""
        if not text:
            return
        stripped = text.strip()
        if not stripped or stripped.upper() in ("NULL", "N/A", "NONE", ""):
            return
        text = stripped

        existing = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == session_id,
            ConsultationFinding.factor_type == factor_type
        ).first()

        if existing:
            existing.finding_text = text.strip()
        else:
            self.db.add(ConsultationFinding(
                session_id=session_id,
                factor_type=factor_type,
                finding_text=text.strip()
            ))

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a section from formatted text.

        Handles multiple header styles:
        - ## SECTION_NAME  or  ### 1. SECTION_NAME  (markdown headers)
        - **SECTION_NAME** or **1. SECTION_NAME**   (bold)
        - SECTION_NAME:    or  1. SECTION_NAME      (plain)
        """
        import re

        if not text or not section_name:
            return None

        header_patterns = [
            rf'^#{{2,3}}\s*\*{{0,2}}(\d+\.\s*)?{re.escape(section_name)}\*{{0,2}}[^\n]*$',  # ## SECTION or ## **SECTION**
            rf'^\*\*(\d+\.\s*)?{re.escape(section_name)}\*\*[:\s]*$',                         # **SECTION**: (colon outside bold)
            rf'^\*\*(\d+\.\s*)?{re.escape(section_name)}:\*\*\s*$',                           # **SECTION:** (colon inside bold)
            rf'^(\d+\.\s*)?{re.escape(section_name)}[:\s]*$',                                 # SECTION: (plain)
        ]

        lines = text.split('\n')
        start_pos = None
        start_line_end = None

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

        end_pos = len(lines)
        next_section_pattern = r'^(#{2,3}\s+(\d+\.\s*)?[A-Z]|\*\*(\d+\.\s*)?[A-Z]|[A-Z]{2,}[:\s]*$)'
        for i in range(start_line_end, len(lines)):
            line = lines[i].strip()
            if line and re.match(next_section_pattern, line):
                end_pos = i
                break

        content = '\n'.join(lines[start_line_end:end_pos]).strip()
        return content if content else None

    def _get_consultation_start_time(self, session_id: int):
        """Get the timestamp when the consultation was started."""
        first_msg = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == session_id,
            ConsultationMessage.role == "system"
        ).order_by(ConsultationMessage.created_at).first()

        return first_msg.created_at if first_msg else None

    def _detect_context_changes(self, db_session: SessionModel) -> Dict:
        """
        Detect if context data (company info, maturity, ideas) has changed
        since the consultation was started.

        Returns a dict with changed sections and their new content.
        """
        consultation_start = self._get_consultation_start_time(db_session.id)
        if not consultation_start:
            return {}

        changes = {}

        # Check maturity assessment updates
        maturity = self.db.query(MaturityAssessment).filter(
            MaturityAssessment.session_id == db_session.id
        ).first()

        if maturity and maturity.updated_at and maturity.updated_at > consultation_start:
            changes["maturity"] = {
                "overall_score": maturity.overall_score,
                "maturity_level": maturity.maturity_level,
                "resources_score": maturity.resources_score,
                "information_systems_score": maturity.information_systems_score,
                "culture_score": maturity.culture_score,
                "organizational_structure_score": maturity.organizational_structure_score,
            }

        # Check company info additions/updates (uses created_at since it doesn't have updated_at)
        new_company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id,
            CompanyInfo.created_at > consultation_start
        ).all()

        if new_company_infos:
            changes["company_info"] = [
                {"type": info.info_type, "content": info.content[:500]}
                for info in new_company_infos
            ]

        # Check for new ideas or prioritization changes
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        new_ideas = []
        for sheet in sheets:
            ideas = self.db.query(Idea).filter(
                Idea.sheet_id == sheet.id,
                Idea.created_at > consultation_start
            ).all()
            for idea in ideas:
                new_ideas.append(idea.content)

        if new_ideas:
            changes["new_ideas"] = new_ideas

        # Check for new prioritization votes
        new_votes = self.db.query(Prioritization).filter(
            Prioritization.session_id == db_session.id,
            Prioritization.created_at > consultation_start
        ).count()

        if new_votes > 0:
            # Recalculate top ideas with current votes
            all_ideas = []
            for sheet in sheets:
                ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
                for idea in ideas:
                    votes = self.db.query(Prioritization).filter(
                        Prioritization.idea_id == idea.id
                    ).all()
                    total_points = sum(v.score or 0 for v in votes)
                    all_ideas.append({"content": idea.content, "points": total_points})

            all_ideas.sort(key=lambda x: x["points"], reverse=True)
            if all_ideas:
                changes["prioritization_updated"] = all_ideas[:5]

        return changes

    def _build_context_update_message(self, changes: Dict) -> str:
        """Build a notification message about context changes."""
        if not changes:
            return ""

        if self.language == "de":
            parts = ["[WICHTIGE AKTUALISIERUNG: Der Kunde hat seit Beginn unseres Gesprächs Informationen in vorherigen Schritten aktualisiert]\n"]

            if "maturity" in changes:
                m = changes["maturity"]
                parts.append(f"**Reifegrad-Bewertung aktualisiert:**")
                parts.append(f"- Neuer Gesamtreifegrad: {m['overall_score']:.1f}/6 ({m['maturity_level']})")
                parts.append(f"- Ressourcen: {m['resources_score']}/6, IT-Systeme: {m['information_systems_score']}/6")
                parts.append(f"- Kultur: {m['culture_score']}/6, Organisation: {m['organizational_structure_score']}/6\n")

            if "company_info" in changes:
                parts.append("**Neue Unternehmensinformationen hinzugefügt:**")
                for info in changes["company_info"]:
                    parts.append(f"- [{info['type'].upper()}]: {info['content'][:200]}...")
                parts.append("")

            if "new_ideas" in changes:
                parts.append("**Neue Ideen wurden hinzugefügt:**")
                for idea in changes["new_ideas"][:3]:
                    parts.append(f"- {idea[:100]}...")
                parts.append("")

            if "prioritization_updated" in changes:
                parts.append("**Priorisierung wurde aktualisiert. Aktuelle Top-Ideen:**")
                for i, idea in enumerate(changes["prioritization_updated"][:3]):
                    parts.append(f"{i+1}. {idea['content'][:80]}... ({idea['points']} Punkte)")
                parts.append("")

            parts.append("Bitte berücksichtigen Sie diese Aktualisierungen in Ihren weiteren Empfehlungen.")
        else:
            parts = ["[IMPORTANT UPDATE: The client has updated information in previous steps since our conversation began]\n"]

            if "maturity" in changes:
                m = changes["maturity"]
                parts.append(f"**Maturity Assessment Updated:**")
                parts.append(f"- New Overall Maturity: {m['overall_score']:.1f}/6 ({m['maturity_level']})")
                parts.append(f"- Resources: {m['resources_score']}/6, IT Systems: {m['information_systems_score']}/6")
                parts.append(f"- Culture: {m['culture_score']}/6, Organization: {m['organizational_structure_score']}/6\n")

            if "company_info" in changes:
                parts.append("**New Company Information Added:**")
                for info in changes["company_info"]:
                    parts.append(f"- [{info['type'].upper()}]: {info['content'][:200]}...")
                parts.append("")

            if "new_ideas" in changes:
                parts.append("**New Ideas Have Been Added:**")
                for idea in changes["new_ideas"][:3]:
                    parts.append(f"- {idea[:100]}...")
                parts.append("")

            if "prioritization_updated" in changes:
                parts.append("**Prioritization Has Been Updated. Current Top Ideas:**")
                for i, idea in enumerate(changes["prioritization_updated"][:3]):
                    parts.append(f"{i+1}. {idea['content'][:80]}... ({idea['points']} points)")
                parts.append("")

            parts.append("Please take these updates into account in your further recommendations.")

        return "\n".join(parts)

    def _inject_context_update_if_needed(self, db_session: SessionModel) -> Optional[str]:
        """
        Check for context changes and return an update message if needed.
        Saves the update as a system message so it's only injected once.
        """
        changes = self._detect_context_changes(db_session)
        if not changes:
            return None

        # Check if we've already notified about recent changes
        # Look for a context update message after the original system prompt
        consultation_start = self._get_consultation_start_time(db_session.id)
        if not consultation_start:
            return None

        # Check for existing context update messages
        existing_update = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.role == "system",
            ConsultationMessage.content.like("%IMPORTANT UPDATE%") | ConsultationMessage.content.like("%WICHTIGE AKTUALISIERUNG%"),
            ConsultationMessage.created_at > consultation_start
        ).first()

        if existing_update:
            # Already notified about changes - but check if there are newer changes
            # by comparing timestamps
            latest_change_time = None

            # Get latest maturity update
            maturity = self.db.query(MaturityAssessment).filter(
                MaturityAssessment.session_id == db_session.id
            ).first()
            if maturity and maturity.updated_at:
                latest_change_time = maturity.updated_at

            # Get latest company info
            latest_info = self.db.query(CompanyInfo).filter(
                CompanyInfo.session_id == db_session.id
            ).order_by(CompanyInfo.created_at.desc()).first()
            if latest_info and latest_info.created_at:
                if not latest_change_time or latest_info.created_at > latest_change_time:
                    latest_change_time = latest_info.created_at

            # If the existing update is after the latest change, skip
            if latest_change_time and existing_update.created_at >= latest_change_time:
                return None

        # Build and save the context update message
        update_message = self._build_context_update_message(changes)

        # Save the update as a system message so it appears in conversation history
        update_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=update_message
        )
        self.db.add(update_msg)
        self.db.commit()

        return update_message
