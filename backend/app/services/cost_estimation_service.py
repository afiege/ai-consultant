"""Service for AI-powered cost estimation in Step 5b using LiteLLM (multi-provider)."""

import re
from typing import List, Optional, Dict, Generator, Tuple
from sqlalchemy.orm import Session
import logging

from ..utils.llm import LLMCaller, strip_think_tokens, extract_content, normalize_wiki_links
from ..utils.security import validate_and_sanitize_message

logger = logging.getLogger(__name__)

from ..models import (
    Session as SessionModel,
    ConsultationMessage,
    ConsultationFinding,
    CompanyInfo,
    Idea,
    IdeaSheet,
    Prioritization
)
from .default_prompts import get_prompt
from .company_profile_service import get_profile_as_context
from ..utils.sse import format_sse_data, format_sse_error


class CostEstimationService:
    """AI cost estimation consultant service using LiteLLM for Step 5b."""

    MESSAGE_TYPE = "cost_estimation"  # Distinguishes from other message types

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

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1500):
        """Call LLM with automatic retry on transient failures."""
        if self.chat_temperature is not None:
            temperature = self.chat_temperature
        return self._llm.call(messages, temperature, max_tokens, timeout=120)

    def _call_llm_stream(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1500) -> Generator:
        """Call LLM with streaming and automatic retry on transient failures."""
        if self.chat_temperature is not None:
            temperature = self.chat_temperature
        return self._llm.call_stream(messages, temperature, max_tokens, timeout=120)

    def _call_llm_extraction(self, messages: List[Dict], temperature: float = 0.3, max_tokens: int = 2000):
        """Call LLM for extraction tasks with separate temperature control."""
        if self.extraction_temperature is not None:
            temperature = self.extraction_temperature
        return self._llm.call(messages, temperature, max_tokens, timeout=120)

    def start_cost_estimation(self, session_uuid: str) -> Dict:
        """
        Start a new cost estimation session.
        Creates the initial system message and first AI response.
        """
        db_session = self._get_session(session_uuid)

        # Check if cost estimation already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE
        ).count()

        if existing_messages > 0:
            return {"status": "already_started", "message_count": existing_messages}

        # Build context from previous steps
        context = self._build_cost_estimation_context(db_session)

        # Create system message
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(system_msg)

        # Save the initial user prompt (needed for proper role alternation)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content="Please start the cost estimation analysis.",
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(initial_user_msg)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the cost estimation analysis."}
        ]

        response = self._call_llm(messages, temperature=0.7, max_tokens=1500)

        ai_response = response.choices[0].message.content

        # Save AI response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=ai_response,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(ai_msg)
        self.db.commit()

        return {
            "status": "started",
            "initial_message": ai_response
        }

    def start_cost_estimation_stream(self, session_uuid: str) -> Generator[str, None, None]:
        """
        Start cost estimation with streaming response.
        Yields chunks of the AI response as they arrive.
        """
        db_session = self._get_session(session_uuid)

        # Check if cost estimation already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE
        ).count()

        if existing_messages > 0:
            yield "data: {\"status\": \"already_started\"}\n\n"
            return

        # Build context from previous steps
        context = self._build_cost_estimation_context(db_session)

        # Create system message
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(system_msg)

        # Save the initial user prompt (needed for proper role alternation)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content="Please start the cost estimation analysis.",
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(initial_user_msg)
        self.db.commit()

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the cost estimation analysis."}
        ]

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

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
                    content=full_response + "\n\n[Response interrupted due to connection error]",
                    message_type=self.MESSAGE_TYPE
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
            content=full_response,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def save_user_message(self, session_uuid: str, user_message: str) -> Dict:
        """
        Save a user message without generating AI response.
        """
        db_session = self._get_session(session_uuid)

        # SECURITY: Validate and sanitize user input
        sanitized_message, is_safe, warning = validate_and_sanitize_message(user_message)
        if not is_safe:
            logger.warning(f"Blocked potentially unsafe message: {warning}")
            raise ValueError(f"Invalid message content: {warning}. Please rephrase your message.")

        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message,
            message_type=self.MESSAGE_TYPE
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

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        # Generate AI response
        response = self._call_llm(messages, temperature=0.7, max_tokens=1500)

        ai_response = response.choices[0].message.content

        # Save AI response
        ai_msg = ConsultationMessage(
            session_id=db_session.id,
            role="assistant",
            content=ai_response,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(ai_msg)
        self.db.commit()

        return {
            "response": ai_response,
            "message_id": ai_msg.id
        }

    def send_message_stream(self, session_uuid: str, user_message: str) -> Generator[str, None, None]:
        """
        Send a user message and stream AI response.
        """
        db_session = self._get_session(session_uuid)

        # SECURITY: Validate and sanitize user input
        sanitized_message, is_safe, warning = validate_and_sanitize_message(user_message)
        if not is_safe:
            logger.warning(f"Blocked potentially unsafe message: {warning}")
            yield format_sse_error(f"Invalid message content: {warning}", "validation_error")
            return

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=sanitized_message,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

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
                    content=full_response + "\n\n[Response interrupted due to connection error]",
                    message_type=self.MESSAGE_TYPE
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
            content=full_response,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def request_ai_response_stream(self, session_uuid: str) -> Generator[str, None, None]:
        """
        Request AI response based on current conversation (no new user message).
        """
        # Ensure we see the latest committed data (important for test mode flow)
        self.db.expire_all()

        db_session = self._get_session(session_uuid)

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        if len(messages) < 2:
            yield "data: {\"error\": \"No conversation history\"}\n\n"
            return

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

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
                    content=full_response + "\n\n[Response interrupted due to connection error]",
                    message_type=self.MESSAGE_TYPE
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
            content=full_response,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(ai_msg)
        self.db.commit()

        yield "data: [DONE]\n\n"

    def get_messages(self, session_uuid: str) -> List[Dict]:
        """Get all cost estimation messages."""
        db_session = self._get_session(session_uuid)

        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE,
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
            if m.content != "Please start the cost estimation analysis."
        ]

    def get_findings(self, session_uuid: str) -> Dict:
        """Get extracted cost estimation findings."""
        db_session = self._get_session(session_uuid)

        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                "cost_complexity",
                "cost_initial",
                "cost_recurring",
                "cost_maintenance",
                "cost_tco",
                "cost_drivers",
                "cost_optimization",
                "cost_roi"
            ])
        ).all()

        result = {
            "complexity": None,
            "initial_investment": None,
            "recurring_costs": None,
            "maintenance": None,
            "tco": None,
            "cost_drivers": None,
            "optimization": None,
            "roi_analysis": None
        }

        type_mapping = {
            "cost_complexity": "complexity",
            "cost_initial": "initial_investment",
            "cost_recurring": "recurring_costs",
            "cost_maintenance": "maintenance",
            "cost_tco": "tco",
            "cost_drivers": "cost_drivers",
            "cost_optimization": "optimization",
            "cost_roi": "roi_analysis"
        }

        for f in findings:
            key = type_mapping.get(f.factor_type)
            if key:
                result[key] = f.finding_text

        return result

    def extract_findings_now(self, session_uuid: str) -> Dict:
        """Force extraction of cost estimation findings from current conversation."""
        db_session = self._get_session(session_uuid)
        messages = self._get_conversation_history(db_session.id)

        # Get extraction prompt from templates
        extraction_prompt = get_prompt(
            "cost_estimation_extraction",
            self.language,
            self.custom_prompts
        )

        messages.append({"role": "user", "content": extraction_prompt})

        # Use higher max_tokens for potentially lengthy cost breakdown
        response = self._call_llm_extraction(messages, max_tokens=6000)

        summary = extract_content(response)

        # Extract and save cost estimation findings
        complexity = (
            self._extract_section(summary, "COMPLEXITY ASSESSMENT") or
            self._extract_section(summary, "KOMPLEXITÄTSBEWERTUNG") or
            self._extract_section(summary, "COMPLEXITY") or
            self._extract_section(summary, "KOMPLEXITÄT") or
            self._extract_section(summary, "PROJEKTKOMPLEXITÄT")
        )
        if not complexity:
            header_lines = [
                l.strip() for l in summary.split('\n')
                if l.strip().startswith('#') or l.strip().startswith('**')
            ][:20]
            logger.warning(
                "Cost estimation COMPLEXITY section missing for session %s. "
                "Headers found: %s | First 800 chars: %s",
                session_uuid,
                header_lines,
                summary[:800] if summary else "(empty)"
            )
        self._save_finding(db_session.id, "cost_complexity", normalize_wiki_links(complexity) if complexity else complexity)

        initial = (
            self._extract_section(summary, "INITIAL INVESTMENT") or
            self._extract_section(summary, "ERSTINVESTITION")
        )
        self._save_finding(db_session.id, "cost_initial", normalize_wiki_links(initial) if initial else initial)

        recurring = (
            self._extract_section(summary, "RECURRING COSTS") or
            self._extract_section(summary, "LAUFENDE KOSTEN")
        )
        self._save_finding(db_session.id, "cost_recurring", normalize_wiki_links(recurring) if recurring else recurring)

        maintenance = (
            self._extract_section(summary, "MAINTENANCE") or
            self._extract_section(summary, "WARTUNG")
        )
        self._save_finding(db_session.id, "cost_maintenance", normalize_wiki_links(maintenance) if maintenance else maintenance)

        tco = (
            self._extract_section(summary, "3-YEAR TOTAL COST OF OWNERSHIP") or
            self._extract_section(summary, "3-YEAR TCO") or
            self._extract_section(summary, "TOTAL COST OF OWNERSHIP") or
            self._extract_section(summary, "3-JAHRES-GESAMTBETRIEBSKOSTEN") or
            self._extract_section(summary, "3-JAHRES GESAMTBETRIEBSKOSTEN") or   # space instead of hyphen
            self._extract_section(summary, "GESAMTBETRIEBSKOSTEN") or
            self._extract_section(summary, "TCO")
        )
        self._save_finding(db_session.id, "cost_tco", normalize_wiki_links(tco) if tco else tco)

        drivers = (
            self._extract_section(summary, "COST DRIVERS") or
            self._extract_section(summary, "KOSTENTREIBER")
        )
        self._save_finding(db_session.id, "cost_drivers", normalize_wiki_links(drivers) if drivers else drivers)

        optimization = (
            self._extract_section(summary, "COST OPTIMIZATION OPTIONS") or
            self._extract_section(summary, "KOSTENOPTIMIERUNGSOPTIONEN")
        )
        self._save_finding(db_session.id, "cost_optimization", normalize_wiki_links(optimization) if optimization else optimization)

        roi = (
            self._extract_section(summary, "INVESTMENT VS. RETURN") or
            self._extract_section(summary, "INVESTITION VS. RENDITE")
        )
        self._save_finding(db_session.id, "cost_roi", normalize_wiki_links(roi) if roi else roi)

        if not any([complexity, initial, recurring, tco, roi]):
            logger.warning(
                "Cost estimation extraction produced no structured sections for session %s. "
                "LLM response (first 500 chars): %s",
                session_uuid, summary[:500] if summary else "(empty)"
            )

        self.db.commit()

        # Re-extract the Step 5a annual benefit and validate ROI arithmetic.
        step5a = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type == "business_case_calculation",
        ).first()
        potentials_for_validation = {
            "calculation": step5a.finding_text if step5a else ""
        }
        annual_benefit_float, _ = self._extract_annual_benefit_from_5a(potentials_for_validation)
        self._validate_and_correct_roi(db_session.id, annual_benefit_float)

        return {
            "summary": summary,
            "findings": self.get_findings(session_uuid)
        }

    def _get_session(self, session_uuid: str) -> SessionModel:
        """Get session by UUID."""
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")

        return db_session

    def _build_cost_estimation_context(self, db_session: SessionModel) -> Dict:
        """Build context from all previous steps including Step 5a findings."""
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
                        "content": info.content[:2000]
                    })

        # Get ideas and prioritization results (Step 2 & 3)
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        all_ideas = []
        for sheet in sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
            for idea in ideas:
                votes = self.db.query(Prioritization).filter(
                    Prioritization.idea_id == idea.id
                ).all()
                total_points = sum(v.score or 0 for v in votes)

                all_ideas.append({
                    "content": idea.content,
                    "points": total_points
                })

        all_ideas.sort(key=lambda x: x["points"], reverse=True)

        # Get CRISP-DM findings from Step 4 (including company_profile with maturity)
        step4_findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                "company_profile",
                "business_objectives",
                "situation_assessment",
                "ai_goals",
                "project_plan"
            ])
        ).all()

        crisp_dm = {
            "company_profile": "",
            "business_objectives": "",
            "situation_assessment": "",
            "ai_goals": "",
            "project_plan": ""
        }
        for f in step4_findings:
            crisp_dm[f.factor_type] = f.finding_text

        # Get Business Case findings from Step 5a (potentials)
        step5a_findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                "business_case_classification",
                "business_case_calculation",
                "business_case_validation",
                "business_case_pitch"
            ])
        ).all()

        potentials = {
            "classification": "",
            "calculation": "",
            "validation_questions": "",
            "management_pitch": ""
        }
        type_mapping = {
            "business_case_classification": "classification",
            "business_case_calculation": "calculation",
            "business_case_validation": "validation_questions",
            "business_case_pitch": "management_pitch"
        }
        for f in step5a_findings:
            key = type_mapping.get(f.factor_type)
            if key:
                potentials[key] = f.finding_text

        return {
            "company_name": db_session.company_name or "the company",
            "company_info": company_context,
            "company_profile_text": company_profile_text if has_structured_profile else None,
            "ideas": all_ideas,
            "top_idea": all_ideas[0] if all_ideas else None,
            "crisp_dm": crisp_dm,
            "potentials": potentials
        }

    def _build_system_prompt(self, context: Dict) -> str:
        """Build the system prompt for the cost estimation consultant."""
        # Get CRISP-DM findings from Step 4
        crisp_dm = context.get("crisp_dm", {})

        # Use structured profile if available (most token-efficient)
        company_info_text = context.get("company_profile_text")

        if not company_info_text:
            # Fall back to company_profile from Step 4 if available
            company_profile = crisp_dm.get("company_profile", "")
            if company_profile:
                company_info_text = f"\n[COMPANY PROFILE FROM CONSULTATION]\n{company_profile}\n"
            else:
                company_info_text = ""

            # Also include raw company info from Step 1 for additional context
            for info in context.get("company_info", [])[:3]:
                company_info_text += f"\n[{info['type'].upper()}]\n{info['content']}\n"

        if not company_info_text:
            company_info_text = "No company information provided."

        # Get focus idea
        top_idea = context.get("top_idea")
        focus_idea = top_idea["content"] if top_idea else "general AI/digitalization improvements"

        # Get remaining CRISP-DM findings from Step 4
        business_objectives = crisp_dm.get("business_objectives", "Not yet defined.")
        situation_assessment = crisp_dm.get("situation_assessment", "Not yet assessed.")
        ai_goals = crisp_dm.get("ai_goals", "Not yet defined.")
        project_plan = crisp_dm.get("project_plan", "Not yet planned.")

        # Get potentials summary from Step 5a
        potentials = context.get("potentials", {})
        potentials_parts = []
        if potentials.get("classification"):
            potentials_parts.append(f"**Classification:** {potentials['classification']}")
        if potentials.get("calculation"):
            potentials_parts.append(f"**Estimated Benefits:** {potentials['calculation']}")
        if potentials.get("management_pitch"):
            potentials_parts.append(f"**Strategic Value:** {potentials['management_pitch']}")

        potentials_summary = "\n\n".join(potentials_parts) if potentials_parts else "Not yet analyzed in Step 5a."

        # Extract annual benefit figure programmatically from Step 5a so the
        # LLM has an unambiguous anchor for the ROI table.
        _benefit_float, annual_benefit_eur = self._extract_annual_benefit_from_5a(potentials)

        # Get prompt template
        template = get_prompt(
            "cost_estimation_system",
            self.language,
            self.custom_prompts
        )

        # Format with context variables
        return template.format(
            company_info_text=company_info_text,
            focus_idea=focus_idea,
            business_objectives=business_objectives,
            situation_assessment=situation_assessment,
            ai_goals=ai_goals,
            project_plan=project_plan,
            potentials_summary=potentials_summary,
            annual_benefit_eur=annual_benefit_eur,
        )

    def _get_conversation_history(self, session_id: int) -> List[Dict]:
        """Get conversation history as message list (cost estimation messages only)."""
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == session_id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE
        ).order_by(ConsultationMessage.created_at).all()

        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

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

    # ------------------------------------------------------------------
    # Benefit extraction & ROI validation helpers
    # ------------------------------------------------------------------

    def _parse_eur_value(self, text: str) -> Optional[float]:
        """Parse a euro amount string into a float.

        Handles EN (1,000.00) and DE (1.000,00) thousand-separator styles,
        bold markdown, negative signs, and k/M suffixes.
        """
        if not text:
            return None
        clean = re.sub(r'[*_€\s]', '', text)
        negative = clean.startswith('−') or clean.startswith('-')
        clean = clean.lstrip('−-')
        multiplier = 1
        if clean.lower().endswith('k'):
            multiplier = 1_000
            clean = clean[:-1]
        elif clean.lower().endswith('m'):
            multiplier = 1_000_000
            clean = clean[:-1]
        m = re.search(r'[\d][,\.\d]*', clean)
        if not m:
            return None
        num = m.group()
        # Remove thousand separators (comma/dot followed by exactly 3 digits)
        num = re.sub(r'[,\.](?=\d{3}(?:[^\d]|$))', '', num)
        num = num.replace(',', '.')  # normalise remaining decimal separator
        try:
            value = float(num) * multiplier
            return -value if negative else value
        except ValueError:
            return None

    def _extract_annual_benefit_from_5a(
        self, potentials: dict
    ) -> Tuple[Optional[float], str]:
        """Extract the moderate annual benefit figure from the Step 5a text.

        Returns (float_value, display_string).  When extraction fails the
        display string falls back to a human-readable note so the prompt
        still renders cleanly.
        """
        calculation = potentials.get("calculation", "")
        if not calculation:
            return None, "Not available — Step 5a not yet completed."

        patterns = [
            r'Total Annual Benefit[^€\n]*€\s*([\d][,\.\d]*(?:[kKmM])?)',
            r'Gesamter Jahresnutzen[^€\n]*€\s*([\d][,\.\d]*(?:[kKmM])?)',
            r'Annual Benefit[^€\n]*moderate[^€\n]*€\s*([\d][,\.\d]*(?:[kKmM])?)',
            r'Jahresnutzen[^€\n]*moderat[^€\n]*€\s*([\d][,\.\d]*(?:[kKmM])?)',
        ]
        for pattern in patterns:
            m = re.search(pattern, calculation, re.IGNORECASE)
            if m:
                value = self._parse_eur_value(m.group(1))
                if value and value > 0:
                    if value >= 1_000_000:
                        display = f"€{value / 1_000_000:.2f}M"
                    else:
                        display = f"€{value:,.0f}"
                    return value, display

        return None, "Not extracted — see calculation above."

    def _parse_roi_table_value(self, roi_text: str, keywords: list) -> Optional[float]:
        """Find a row in the ROI markdown table by keywords and return its euro value."""
        for line in roi_text.split('\n'):
            if '|' not in line:
                continue
            lower = line.lower()
            if any(kw in lower for kw in keywords):
                cols = [c.strip() for c in line.split('|')]
                for col in reversed(cols):
                    if col and col not in ('', '-', '—'):
                        val = self._parse_eur_value(col)
                        if val is not None:
                            return val
        return None

    def _parse_roi_payback(self, roi_text: str) -> Optional[float]:
        """Extract the payback period in years from the ROI table."""
        for line in roi_text.split('\n'):
            if '|' not in line:
                continue
            lower = line.lower()
            if 'payback' in lower or 'amortisation' in lower:
                m = re.search(r'(\d+\.?\d*)\s*year', line, re.IGNORECASE)
                if m:
                    return float(m.group(1))
        return None

    def _parse_roi_percent(self, roi_text: str) -> Optional[float]:
        """Extract the 3-year ROI percentage from the ROI table.

        Handles comma-formatted large values like 2,015% as well as −84%.
        """
        for line in roi_text.split('\n'):
            if '|' not in line:
                continue
            lower = line.lower()
            if ('3-year roi' in lower or '3-jahres-roi' in lower
                    or ('roi' in lower and '3' in lower)):
                m = re.search(r'(-?[\d][,\.\d]*)\s*%', line)
                if m:
                    return self._parse_eur_value(m.group(1))
        return None

    def _validate_and_correct_roi(
        self, session_id: int, annual_benefit: Optional[float]
    ) -> None:
        """Re-compute ROI arithmetic from extracted findings.

        If the LLM's payback period or 3-year ROI differ materially (>15 %)
        from the values computed here, a correction block is appended to the
        cost_roi finding so the report always shows accurate numbers.
        """
        if annual_benefit is None:
            return

        roi_finding = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == session_id,
            ConsultationFinding.factor_type == "cost_roi",
        ).first()
        if not roi_finding or not roi_finding.finding_text:
            return

        roi_text = roi_finding.finding_text

        annual_recurring = self._parse_roi_table_value(
            roi_text, ['annual recurring', 'recurring costs', 'laufende kosten']
        )
        initial_investment = self._parse_roi_table_value(
            roi_text, ['initial investment', 'erstinvestition']
        )

        if annual_recurring is None or initial_investment is None:
            logger.debug(
                "ROI validation skipped for session %s: could not parse "
                "recurring costs or initial investment from table.",
                session_id,
            )
            return

        net_annual = annual_benefit - annual_recurring

        if net_annual <= 0:
            computed_payback = None
            payback_str = "Never (net annual benefit is negative)"
        else:
            computed_payback = round(initial_investment / net_annual, 2)
            payback_str = f"{computed_payback:.2f} years"

        computed_roi = round(
            (3 * net_annual - initial_investment) / initial_investment * 100, 1
        ) if initial_investment else None

        # Determine whether correction is needed
        needs_correction = False

        if net_annual <= 0:
            text_lower = roi_text.lower()
            if not any(w in text_lower for w in ('never', 'nie', 'non-viable', 'nicht rentabel')):
                needs_correction = True
        else:
            llm_payback = self._parse_roi_payback(roi_text)
            llm_roi = self._parse_roi_percent(roi_text)
            if (llm_payback is not None and computed_payback is not None
                    and abs(llm_payback - computed_payback) / max(computed_payback, 0.01) > 0.15):
                needs_correction = True
            if (llm_roi is not None and computed_roi is not None
                    and abs(llm_roi - computed_roi) > 15):
                needs_correction = True

        if not needs_correction:
            return

        correction = (
            "\n\n---\n"
            "⚠️ **Arithmetic correction (auto-validated from extracted figures):**\n\n"
            f"| Metric | Corrected Value |\n"
            f"|--------|-----------------|\n"
            f"| Annual Benefit | €{annual_benefit:,.0f} |\n"
            f"| Annual Recurring + Maintenance | €{annual_recurring:,.0f} |\n"
            f"| Net Annual Benefit | €{net_annual:,.0f} |\n"
            f"| Initial Investment | €{initial_investment:,.0f} |\n"
            f"| **Simple Payback Period** | **{payback_str}** |\n"
        )
        if computed_roi is not None:
            correction += f"| **3-Year ROI** | **{computed_roi:.1f}%** |\n"

        roi_finding.finding_text = roi_finding.finding_text + correction
        self.db.commit()
        logger.info(
            "ROI arithmetic corrected for session %s "
            "(benefit=%.0f, recurring=%.0f, initial=%.0f, "
            "payback=%s, roi_3yr=%s)",
            session_id, annual_benefit, annual_recurring, initial_investment,
            payback_str, f"{computed_roi:.1f}%" if computed_roi else "n/a",
        )

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a section from formatted text.

        Handles multiple header styles:
        - ## SECTION_NAME  or  #### 1. SECTION_NAME  (markdown headers, up to 6 hashes)
        - **SECTION_NAME** or **1. SECTION_NAME**    (bold)
        - SECTION_NAME:    or  1. SECTION_NAME       (plain)

        Fixes applied (synced from consultation_service.py):
        - Supports up to 6 hashes (qwen3/minimax generate #### headers)
        - Level-aware end detection: subsections (deeper #) do not cut off parent section
        - Unicode dash normalization: U+2011 non-breaking hyphen → ASCII hyphen before matching
        - Wiki-link header normalization: [[id|Text]] → Text
        - Bold next_section guard uses [^a-z*\\n]* to avoid matching inline labels like **Stufe 2 – Text**
        """
        import re

        if not text or not section_name:
            return None

        # Normalize Unicode dashes (U+2010–U+2015, U+2212) to ASCII hyphen
        # Also strip wiki-link wrappers [[id|Display Text]] → Display Text
        _DASH_RE = re.compile(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]')
        _WIKI_HEADER_RE = re.compile(r'\[\[[^\]|]*\|([^\]]+)\]\]')

        def norm(s: str) -> str:
            s = _DASH_RE.sub('-', s)
            s = _WIKI_HEADER_RE.sub(r'\1', s)  # [[id|Text]] → Text
            return s

        esc = re.escape(norm(section_name))

        # Patterns: (regex, captures_hash_level)
        # First pattern captures the leading #+ as group(1) to detect header level
        header_patterns = [
            (rf'^(#{{2,6}})\s*\*{{0,2}}(?:\d+\.\s*)?{esc}\*{{0,2}}[^\n]*$', True),   # ## to ###### SECTION
            (rf'^\*\*#{{1,3}}\s*(?:\d+\.\s*)?{esc}[^\n]*$', False),                    # **## SECTION (bold wraps hash)
            (rf'^\*\*(?:\d+\.\s*)?{esc}\*\*[:\s]*$', False),                           # **SECTION**: (colon outside bold)
            (rf'^\*\*(?:\d+\.\s*)?{esc}:\*\*\s*$', False),                             # **SECTION:** (colon inside bold)
            (rf'^(?:\d+\.\s*)?{esc}[:\s]*$', False),                                   # SECTION: (plain)
        ]

        lines = text.split('\n')
        start_pos = None
        start_line_end = None
        start_level = 2  # default: treat as ## level

        for i, line in enumerate(lines):
            normed = norm(line.strip())
            for pattern, captures_level in header_patterns:
                m = re.match(pattern, normed, re.IGNORECASE)
                if m:
                    start_pos = i
                    start_line_end = i + 1
                    if captures_level:
                        start_level = len(m.group(1))
                    break
            if start_pos is not None:
                break

        if start_pos is None:
            return None

        end_pos = len(lines)
        # Level-aware end detection: only stop at headers with depth ≤ start_level
        # Bold is only a header if ALL-CAPS (no lowercase in bold text — avoids matching inline labels)
        next_section_pattern = (
            rf'^('
            rf'#{{2,{start_level}}}\s+\*{{0,2}}(?:\d+\.\s*)?[A-Z]'     # ## .. start_level headers
            rf'|\*\*#{{1,3}}\s+(?:\d+\.\s*)?[A-Z]'                     # **## SECTION (bold wraps hash)
            rf'|\*\*(?:\d+\.\s*)?[A-Z][^a-z*\n]*\*\*\s*:?\s*$'        # **ALL CAPS** (no lowercase)
            rf'|[A-Z]{{3,}}[A-Z\s\-()]*[:\s]*$'                        # PLAIN ALLCAPS
            rf')'
        )
        for i in range(start_line_end, len(lines)):
            normed = norm(lines[i].strip())
            if normed and re.match(next_section_pattern, normed):
                end_pos = i
                break

        content = '\n'.join(lines[start_line_end:end_pos]).strip()
        return content if content else None
