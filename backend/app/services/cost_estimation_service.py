"""Service for AI-powered cost estimation in Step 5b using LiteLLM (multi-provider)."""

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
        api_base: Optional[str] = None
    ):
        self.db = db
        self.model = model
        self.custom_prompts = custom_prompts or {}
        self.language = language
        self.api_key = api_key
        self.api_base = api_base

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1500):
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

    def _call_llm_stream(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1500) -> Generator:
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

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

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

        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=user_message,
            message_type=self.MESSAGE_TYPE
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
            content=user_message,
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

        # Save user message
        user_msg = ConsultationMessage(
            session_id=db_session.id,
            role="user",
            content=user_message,
            message_type=self.MESSAGE_TYPE
        )
        self.db.add(user_msg)
        self.db.commit()

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

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
        db_session = self._get_session(session_uuid)

        # Get conversation history
        messages = self._get_conversation_history(db_session.id)

        if len(messages) < 2:
            yield "data: {\"error\": \"No conversation history\"}\n\n"
            return

        # Stream the response
        full_response = ""
        stream = self._call_llm_stream(messages, temperature=0.7, max_tokens=1500)

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield f"data: {content}\n\n"

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
        response = self._call_llm(messages, temperature=0.3, max_tokens=2500)

        summary = response.choices[0].message.content

        # Extract and save cost estimation findings
        complexity = (
            self._extract_section(summary, "COMPLEXITY ASSESSMENT") or
            self._extract_section(summary, "KOMPLEXITÄTSBEWERTUNG")
        )
        self._save_finding(db_session.id, "cost_complexity", complexity)

        initial = (
            self._extract_section(summary, "INITIAL INVESTMENT") or
            self._extract_section(summary, "ERSTINVESTITION")
        )
        self._save_finding(db_session.id, "cost_initial", initial)

        recurring = (
            self._extract_section(summary, "RECURRING COSTS") or
            self._extract_section(summary, "LAUFENDE KOSTEN")
        )
        self._save_finding(db_session.id, "cost_recurring", recurring)

        maintenance = (
            self._extract_section(summary, "MAINTENANCE") or
            self._extract_section(summary, "WARTUNG")
        )
        self._save_finding(db_session.id, "cost_maintenance", maintenance)

        tco = (
            self._extract_section(summary, "3-YEAR TOTAL COST OF OWNERSHIP") or
            self._extract_section(summary, "3-JAHRES-GESAMTBETRIEBSKOSTEN")
        )
        self._save_finding(db_session.id, "cost_tco", tco)

        drivers = (
            self._extract_section(summary, "COST DRIVERS") or
            self._extract_section(summary, "KOSTENTREIBER")
        )
        self._save_finding(db_session.id, "cost_drivers", drivers)

        optimization = (
            self._extract_section(summary, "COST OPTIMIZATION OPTIONS") or
            self._extract_section(summary, "KOSTENOPTIMIERUNGSOPTIONEN")
        )
        self._save_finding(db_session.id, "cost_optimization", optimization)

        roi = (
            self._extract_section(summary, "INVESTMENT VS. RETURN") or
            self._extract_section(summary, "INVESTITION VS. RENDITE")
        )
        self._save_finding(db_session.id, "cost_roi", roi)

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

    def _build_cost_estimation_context(self, db_session: SessionModel) -> Dict:
        """Build context from all previous steps including Step 5a findings."""
        # Get company info (Step 1)
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()

        company_context = []
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

        # Get CRISP-DM findings from Step 4
        step4_findings = self.db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_([
                "business_objectives",
                "situation_assessment",
                "ai_goals",
                "project_plan"
            ])
        ).all()

        crisp_dm = {
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
            "ideas": all_ideas,
            "top_idea": all_ideas[0] if all_ideas else None,
            "crisp_dm": crisp_dm,
            "potentials": potentials
        }

    def _build_system_prompt(self, context: Dict) -> str:
        """Build the system prompt for the cost estimation consultant."""
        # Format company info
        company_info_text = ""
        for info in context.get("company_info", [])[:3]:
            company_info_text += f"\n[{info['type'].upper()}]\n{info['content']}\n"

        if not company_info_text:
            company_info_text = "No company information provided."

        # Get focus idea
        top_idea = context.get("top_idea")
        focus_idea = top_idea["content"] if top_idea else "general AI/digitalization improvements"

        # Get CRISP-DM findings from Step 4
        crisp_dm = context.get("crisp_dm", {})
        business_objectives = crisp_dm.get("business_objectives", "Not yet defined.")
        situation_assessment = crisp_dm.get("situation_assessment", "Not yet assessed.")
        ai_goals = crisp_dm.get("ai_goals", "Not yet defined.")
        project_plan = crisp_dm.get("project_plan", "Not yet planned.")

        # Get potentials summary from Step 5a
        potentials = context.get("potentials", {})
        potentials_parts = []
        if potentials.get("classification"):
            potentials_parts.append(f"**Classification:** {potentials['classification'][:500]}")
        if potentials.get("calculation"):
            potentials_parts.append(f"**Estimated Benefits:** {potentials['calculation'][:500]}")
        if potentials.get("management_pitch"):
            potentials_parts.append(f"**Strategic Value:** {potentials['management_pitch']}")

        potentials_summary = "\n\n".join(potentials_parts) if potentials_parts else "Not yet analyzed in Step 5a."

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
            potentials_summary=potentials_summary
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
