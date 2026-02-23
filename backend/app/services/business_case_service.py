"""Service for AI-powered business case calculation in Step 5 using LiteLLM (multi-provider)."""

from typing import List, Optional, Dict, Generator
from sqlalchemy.orm import Session

from ..utils.llm import LLMCaller
from ..utils.security import validate_and_sanitize_message

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
import logging

logger = logging.getLogger(__name__)


class BusinessCaseService:
    """AI business case consultant service using LiteLLM for Step 5."""

    MESSAGE_TYPE = "business_case"  # Distinguishes from consultation messages

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

    def start_business_case(self, session_uuid: str) -> Dict:
        """
        Start a new business case session.
        Creates the initial system message and first AI response.
        """
        db_session = self._get_session(session_uuid)

        # Check if business case already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE
        ).count()

        if existing_messages > 0:
            return {"status": "already_started", "message_count": existing_messages}

        # Build context from previous steps
        context = self._build_business_case_context(db_session)

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
            content="Please start the business case analysis.",
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(initial_user_msg)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the business case analysis."}
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

    def start_business_case_stream(self, session_uuid: str) -> Generator[str, None, None]:
        """
        Start business case with streaming response.
        Yields chunks of the AI response as they arrive.
        """
        db_session = self._get_session(session_uuid)

        # Check if business case already started
        existing_messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == db_session.id,
            ConsultationMessage.message_type == self.MESSAGE_TYPE
        ).count()

        if existing_messages > 0:
            yield "data: {\"status\": \"already_started\"}\n\n"
            return

        # Build context from previous steps
        context = self._build_business_case_context(db_session)

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
            content="Please start the business case analysis.",
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(initial_user_msg)
        self.db.commit()

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the business case analysis."}
        ]

        # Stream the response with error handling
        full_response = ""
        try:
            stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
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
                    content = chunk.choices[0].delta.content
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
                    content = chunk.choices[0].delta.content
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
        """Get all business case messages."""
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
            if m.content != "Please start the business case analysis."
        ]

    def get_findings(self, session_uuid: str) -> Dict:
        """Get extracted business case findings."""
        db_session = self._get_session(session_uuid)

        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                "business_case_classification",
                "business_case_calculation",
                "business_case_validation",
                "business_case_pitch"
            ])
        ).all()

        result = {
            "classification": None,
            "calculation": None,
            "validation_questions": None,
            "management_pitch": None
        }

        type_mapping = {
            "business_case_classification": "classification",
            "business_case_calculation": "calculation",
            "business_case_validation": "validation_questions",
            "business_case_pitch": "management_pitch"
        }

        for f in findings:
            key = type_mapping.get(f.factor_type)
            if key:
                result[key] = f.finding_text

        return result

    def extract_findings_now(self, session_uuid: str) -> Dict:
        """Force extraction of business case findings from current conversation."""
        db_session = self._get_session(session_uuid)
        messages = self._get_conversation_history(db_session.id)

        # Get extraction prompt from templates
        extraction_prompt = get_prompt(
            "business_case_extraction",
            self.language,
            self.custom_prompts
        )

        messages.append({"role": "user", "content": extraction_prompt})

        # Use higher max_tokens for potentially lengthy business case
        response = self._call_llm_extraction(messages, max_tokens=2500)

        summary = response.choices[0].message.content

        # Extract and save business case findings
        classification = (
            self._extract_section(summary, "CLASSIFICATION") or
            self._extract_section(summary, "KLASSIFIZIERUNG")
        )
        self._save_finding(db_session.id, "business_case_classification", classification)

        calculation = (
            self._extract_section(summary, "BACK-OF-THE-ENVELOPE CALCULATION") or
            self._extract_section(summary, "ÜBERSCHLAGSRECHNUNG")
        )
        self._save_finding(db_session.id, "business_case_calculation", calculation)

        validation = (
            self._extract_section(summary, "VALIDATION QUESTIONS") or
            self._extract_section(summary, "VALIDIERUNGSFRAGEN")
        )
        self._save_finding(db_session.id, "business_case_validation", validation)

        pitch = (
            self._extract_section(summary, "MANAGEMENT PITCH") or
            self._extract_section(summary, "MANAGEMENT-PITCH")
        )
        self._save_finding(db_session.id, "business_case_pitch", pitch)

        self.db.commit()

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

    def _build_business_case_context(self, db_session: SessionModel) -> Dict:
        """Build context from all previous steps including Step 4 findings."""
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

        return {
            "company_name": db_session.company_name or "the company",
            "company_info": company_context,
            "company_profile_text": company_profile_text if has_structured_profile else None,
            "ideas": all_ideas,
            "top_idea": all_ideas[0] if all_ideas else None,
            "crisp_dm": crisp_dm
        }

    def _build_system_prompt(self, context: Dict) -> str:
        """Build the system prompt for the business case consultant."""
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

        # Get prompt template
        template = get_prompt(
            "business_case_system",
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
            project_plan=project_plan
        )

    def _get_conversation_history(self, session_id: int) -> List[Dict]:
        """Get conversation history as message list (business case messages only)."""
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
        if not text or text.strip() == "":
            return

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
        """Extract a section from formatted text."""
        import re

        # Try to find section with ## header
        pattern = rf"##\s*{section_name}[^\n]*\n(.*?)(?=##|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

        if match:
            return match.group(1).strip()

        return None
