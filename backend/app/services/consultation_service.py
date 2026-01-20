"""Service for AI-powered consultation in Step 4 using LiteLLM (multi-provider)."""

from typing import List, Optional, Dict, Generator
from litellm import completion
from sqlalchemy.orm import Session
import logging

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


class ConsultationService:
    """AI consultant service using LiteLLM for guided interviews."""

    def __init__(
        self,
        db: Session,
        model: str = "mistral/mistral-small-latest",
        custom_prompts: Optional[Dict[str, str]] = None,
        language: str = "en",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        self.db = db
        self.model = model
        self.custom_prompts = custom_prompts or {}
        self.language = language
        self.api_key = api_key
        self.api_base = api_base

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000):
        """Call LLM via LiteLLM with optional API key and base URL."""
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if self.api_key:
            completion_kwargs["api_key"] = self.api_key
        if self.api_base:
            completion_kwargs["api_base"] = self.api_base

        return completion(**completion_kwargs)

    def _call_llm_stream(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000) -> Generator:
        """Call LLM via LiteLLM with streaming enabled."""
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        if self.api_key:
            completion_kwargs["api_key"] = self.api_key
        if self.api_base:
            completion_kwargs["api_base"] = self.api_base

        return completion(**completion_kwargs)

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

        # Create system message
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content
        )
        self.db.add(system_msg)

        # Save the initial user prompt (needed for proper role alternation)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content="Please start the consultation."
        )
        self.db.add(initial_user_msg)

        # Generate initial AI greeting
        initial_prompt = self._build_initial_greeting(context)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the consultation."}
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

        # Create system message
        system_content = self._build_system_prompt(context)
        system_msg = ConsultationMessage(
            session_id=db_session.id,
            role="system",
            content=system_content
        )
        self.db.add(system_msg)

        # Save the initial user prompt (needed for proper role alternation)
        initial_user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content="Please start the consultation."
        )
        self.db.add(initial_user_msg)
        self.db.commit()

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Please start the consultation."}
        ]

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

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

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=user_message
        )
        self.db.add(user_msg)
        self.db.commit()

        return {
            "message_id": user_msg.id,
            "content": user_message,
            "role": "user"
        }

    def send_message(self, session_uuid: str, user_message: str) -> Dict:
        """
        Send a user message and get AI response.
        """
        db_session = self._get_session(session_uuid)

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=user_message
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history
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

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=user_message
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

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
        db_session = self._get_session(session_uuid)

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        # Log the conversation being sent (debug level)
        logger.debug(f"Sending {len(messages)} messages to LLM")

        if len(messages) < 2:
            yield "data: {\"error\": \"No conversation history\"}\n\n"
            return

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1000)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

        # Save the complete response
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
            if m.content != "Please start the consultation."
        ]

    def get_findings(self, session_uuid: str) -> Dict:
        """Get extracted consultation findings (CRISP-DM Business Understanding)."""
        db_session = self._get_session(session_uuid)

        findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id
        ).all()

        # CRISP-DM Business Understanding categories
        result = {
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

        messages.append({"role": "user", "content": extraction_prompt})

        response = self._call_llm(messages, temperature=0.3, max_tokens=2000)

        summary = response.choices[0].message.content

        # Save CRISP-DM Business Understanding findings
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

    def _build_consultation_context(self, db_session: SessionModel) -> Dict:
        """Build context from all previous steps."""
        # Get company info
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()

        company_context = []
        for info in company_infos:
            if info.content:
                company_context.append({
                    "type": info.info_type,
                    "content": info.content[:2000]  # Limit each entry
                })

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
            "ideas": all_ideas,
            "top_idea": all_ideas[0] if all_ideas else None
        }

    def _build_system_prompt(self, context: Dict) -> str:
        """Build the system prompt for the AI consultant."""
        # Format company info
        company_info_text = ""
        for info in context.get("company_info", [])[:3]:
            company_info_text += f"\n[{info['type'].upper()}]\n{info['content']}\n"

        # Format top ideas
        top_ideas_text = ""
        for i, idea in enumerate(context.get("ideas", [])[:5]):
            points_str = f" ({idea['points']} votes)" if idea['points'] > 0 else ""
            top_ideas_text += f"{i+1}. {idea['content']}{points_str}\n"

        # Get focus idea
        top_idea = context.get("top_idea")
        focus_idea = top_idea["content"] if top_idea else "general AI/digitalization improvements"

        # Get prompt template
        template = get_prompt(
            "consultation_system",
            self.language,
            self.custom_prompts
        )

        # Format with context variables
        return template.format(
            company_name=context.get('company_name', 'Unknown'),
            company_info_text=company_info_text,
            top_ideas_text=top_ideas_text,
            focus_idea=focus_idea
        )

    def _build_initial_greeting(self, context: Dict) -> str:
        """Build the initial greeting context."""
        top_idea = context.get("top_idea")
        if top_idea:
            return f"Focus on: {top_idea['content']}"
        return "General AI/digitalization consultation"

    def _get_conversation_history(self, session_id: int) -> List[Dict]:
        """Get conversation history as message list."""
        messages = self.db.query(ConsultationMessage).filter(
            ConsultationMessage.session_id == session_id
        ).order_by(ConsultationMessage.created_at).all()

        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

    def _try_extract_findings(self, db_session: SessionModel, messages: List[Dict], last_response: str):
        """Try to extract findings if conversation seems complete."""
        # Simple heuristic: if conversation has 10+ messages and AI mentions summary/conclusion
        message_count = len([m for m in messages if m["role"] != "system"])

        keywords = ["summary", "summarize", "conclude", "in conclusion", "to wrap up", "final recommendation"]
        should_extract = message_count >= 10 and any(kw in last_response.lower() for kw in keywords)

        if should_extract:
            # Auto-extract findings
            pass  # Let user trigger this manually for now

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
        pattern = rf"##\s*{section_name}\s*\n(.*?)(?=##|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

        if match:
            return match.group(1).strip()

        return None
