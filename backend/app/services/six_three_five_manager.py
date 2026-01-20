"""Service for managing 6-3-5 brainstorming sessions with AI participant support."""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import logging

logger = logging.getLogger(__name__)

from ..models import (
    Session as SessionModel,
    Participant,
    IdeaSheet,
    Idea,
    CompanyInfo
)
from .ai_participant import AIParticipant, get_company_context_summary


class SixThreeFiveSession:
    """Manages 6-3-5 brainstorming session logic."""

    MAX_PARTICIPANTS = 6
    MIN_PARTICIPANTS = 1
    IDEAS_PER_ROUND = 3
    MAX_ROUNDS = 6
    ROUND_DURATION_SECONDS = 300  # 5 minutes

    def __init__(
        self,
        db: Session,
        custom_prompts: Optional[Dict[str, str]] = None,
        language: str = "en"
    ):
        """
        Initialize session manager.

        Args:
            db: Database session
            custom_prompts: Optional dict of custom prompt overrides
            language: Language code ("en" or "de")
        """
        self.db = db
        self.custom_prompts = custom_prompts or {}
        self.language = language

    def start_session(
        self,
        session_uuid: str,
        model: str = "mistral/mistral-small-latest",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        generate_ai_ideas: bool = True
    ) -> Dict:
        """
        Start a 6-3-5 session.

        Args:
            session_uuid: Session UUID
            model: LiteLLM model string (e.g., "mistral/mistral-small-latest")
            api_key: Optional API key (uses env var if not provided)
            api_base: Optional custom API base URL for OpenAI-compatible endpoints
            generate_ai_ideas: Whether to generate AI ideas immediately (set False for background generation)

        Returns:
            Session info dictionary
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")

        # Get human participants
        human_participants = self.db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).all()

        num_human = len(human_participants)

        if num_human < self.MIN_PARTICIPANTS:
            raise ValueError(f"Need at least {self.MIN_PARTICIPANTS} participant to start")

        # Calculate how many AI participants we need
        num_ai_needed = min(self.MAX_PARTICIPANTS - num_human, self.MAX_PARTICIPANTS - num_human)

        # Create AI participants if needed
        if num_ai_needed > 0:
            self._create_ai_participants(db_session.id, num_ai_needed)

        # Get all participants (human + AI)
        all_participants = self.db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).order_by(Participant.id).all()

        # Create idea sheets (one per participant)
        for i, participant in enumerate(all_participants):
            sheet = IdeaSheet(
                session_id=db_session.id,
                sheet_number=i + 1,
                current_participant_id=participant.id,
                current_round=1
            )
            self.db.add(sheet)

        self.db.commit()

        # Generate AI ideas for round 1 (unless deferred for background processing)
        if num_ai_needed > 0 and generate_ai_ideas:
            self._generate_ai_ideas_for_round(session_uuid)

        return {
            "total_participants": len(all_participants),
            "human_participants": num_human,
            "ai_participants": num_ai_needed,
            "current_round": 1,
            "status": "in_progress"
        }

    def _create_ai_participants(self, session_id: int, count: int):
        """Create AI participants for the session."""
        ai_names = [
            "AI Assistant Alpha 🤖",
            "AI Assistant Beta 🤖",
            "AI Assistant Gamma 🤖",
            "AI Assistant Delta 🤖",
            "AI Assistant Epsilon 🤖",
            "AI Assistant Zeta 🤖"
        ]

        for i in range(count):
            ai_participant = Participant(
                session_id=session_id,
                participant_uuid=str(uuid.uuid4()),
                name=ai_names[i] if i < len(ai_names) else f"AI Assistant {i+1} 🤖",
                connection_status="ai_controlled"
            )
            self.db.add(ai_participant)

        self.db.commit()

    def _generate_single_ai_ideas(
        self,
        company_context: str,
        previous_idea_texts: List[str],
        all_session_ideas: List[str],
        current_round: int,
        sheet_number: int,
        participant_name: str
    ) -> tuple[str, List[str]]:
        """
        Generate ideas for a single AI participant (runs in thread).

        Returns:
            Tuple of (participant_name, list of generated ideas)
        """
        try:
            ai_participant = AIParticipant(
                model=self.model,
                custom_prompts=self.custom_prompts,
                language=self.language,
                api_key=self.api_key,
                api_base=self.api_base
            )
            generated_ideas = ai_participant.generate_ideas(
                company_context=company_context,
                previous_ideas=previous_idea_texts,
                round_number=current_round,
                participant_number=sheet_number,
                all_session_ideas=all_session_ideas
            )
            logger.debug(f"Generated {len(generated_ideas)} ideas for {participant_name} in round {current_round}")
            return (participant_name, generated_ideas)
        except Exception as e:
            logger.error(f"Error generating AI ideas for {participant_name}: {e}")
            return (participant_name, [])

    def _generate_ai_ideas_for_round(self, session_uuid: str):
        """
        Generate ideas for all AI participants in the current round IN PARALLEL.

        Args:
            session_uuid: Session UUID
        """
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            return

        # Get all sheets
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        current_round = sheets[0].current_round if sheets else 1

        # Collect ALL existing ideas in this session (to avoid duplicates across AI participants)
        all_session_ideas = []
        for s in sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == s.id).all()
            all_session_ideas.extend([idea.content for idea in ideas])

        # Get company context once (shared across all AI participants)
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()
        company_context = get_company_context_summary(company_infos)

        # Collect AI participant tasks to run in parallel
        ai_tasks = []
        for sheet in sheets:
            # Get the participant assigned to this sheet
            participant = self.db.query(Participant).filter(
                Participant.id == sheet.current_participant_id
            ).first()

            # Only generate for AI participants
            if not participant or participant.connection_status != 'ai_controlled':
                continue

            # Check if AI has already submitted for current round
            existing_ideas = self.db.query(Idea).filter(
                Idea.sheet_id == sheet.id,
                Idea.participant_id == participant.id,
                Idea.round_number == current_round
            ).count()

            if existing_ideas >= 3:
                continue  # Already submitted

            # Get previous ideas on this sheet
            previous_ideas = self.db.query(Idea).filter(
                Idea.sheet_id == sheet.id,
                Idea.round_number < current_round
            ).order_by(Idea.round_number, Idea.idea_number).all()
            previous_idea_texts = [idea.content for idea in previous_ideas]

            ai_tasks.append({
                'sheet': sheet,
                'participant': participant,
                'previous_idea_texts': previous_idea_texts
            })

        if not ai_tasks:
            return

        logger.info(f"Generating ideas for {len(ai_tasks)} AI participants in parallel...")

        # Generate ideas in parallel using ThreadPoolExecutor
        results = []
        with ThreadPoolExecutor(max_workers=min(len(ai_tasks), 6)) as executor:
            futures = {
                executor.submit(
                    self._generate_single_ai_ideas,
                    company_context,
                    task['previous_idea_texts'],
                    all_session_ideas.copy(),  # Each thread gets a copy
                    current_round,
                    task['sheet'].sheet_number,
                    task['participant'].name
                ): task for task in ai_tasks
            }

            for future in as_completed(futures):
                task = futures[future]
                try:
                    participant_name, generated_ideas = future.result()
                    results.append({
                        'task': task,
                        'ideas': generated_ideas
                    })
                except Exception as e:
                    logger.error(f"Error in parallel generation for {task['participant'].name}: {e}")

        # Save all generated ideas to database (must be done in main thread)
        for result in results:
            task = result['task']
            generated_ideas = result['ideas']

            if not generated_ideas:
                continue

            for i, idea_content in enumerate(generated_ideas):
                idea = Idea(
                    sheet_id=task['sheet'].id,
                    participant_id=task['participant'].id,
                    round_number=current_round,
                    idea_number=i + 1,
                    content=idea_content
                )
                self.db.add(idea)

        self.db.commit()
        logger.info(f"All {len(results)} AI participants completed for round {current_round}")

    def submit_ideas(
        self,
        session_uuid: str,
        participant_uuid: str,
        sheet_id: int,
        ideas: List[str]
    ) -> Dict:
        """
        Submit ideas for the current round.

        Args:
            session_uuid: Session UUID
            participant_uuid: Participant UUID
            sheet_id: Sheet ID
            ideas: List of 3 ideas

        Returns:
            Submission result
        """
        if len(ideas) != self.IDEAS_PER_ROUND:
            raise ValueError(f"Must submit exactly {self.IDEAS_PER_ROUND} ideas")

        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        # Get participant
        participant = self.db.query(Participant).filter(
            Participant.participant_uuid == participant_uuid
        ).first()

        # Get sheet
        sheet = self.db.query(IdeaSheet).filter(
            IdeaSheet.id == sheet_id
        ).first()

        if not all([db_session, participant, sheet]):
            raise ValueError("Invalid session, participant, or sheet")

        # Save ideas
        for i, idea_content in enumerate(ideas):
            idea = Idea(
                sheet_id=sheet.id,
                participant_id=participant.id,
                round_number=sheet.current_round,
                idea_number=i + 1,
                content=idea_content
            )
            self.db.add(idea)

        self.db.commit()

        return {"success": True, "ideas_submitted": len(ideas)}

    async def generate_ai_ideas(
        self,
        session_uuid: str,
        sheet_id: int
    ) -> List[str]:
        """
        Generate ideas for an AI participant.

        Args:
            session_uuid: Session UUID
            sheet_id: Sheet ID

        Returns:
            List of 3 generated ideas
        """
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        # Get sheet
        sheet = self.db.query(IdeaSheet).filter(
            IdeaSheet.id == sheet_id
        ).first()

        # Collect all existing ideas in this session
        all_sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()
        all_session_ideas = []
        for s in all_sheets:
            ideas = self.db.query(Idea).filter(Idea.sheet_id == s.id).all()
            all_session_ideas.extend([idea.content for idea in ideas])

        # Get company context
        company_infos = self.db.query(CompanyInfo).filter(
            CompanyInfo.session_id == db_session.id
        ).all()
        company_context = get_company_context_summary(company_infos)

        # Get previous ideas on this sheet
        previous_ideas = self.db.query(Idea).filter(
            Idea.sheet_id == sheet.id,
            Idea.round_number < sheet.current_round
        ).order_by(Idea.round_number, Idea.idea_number).all()

        previous_idea_texts = [idea.content for idea in previous_ideas]

        # Generate ideas using AI (with all session ideas to avoid duplicates)
        ai_participant = AIParticipant(
            model=self.model,
            custom_prompts=self.custom_prompts,
            language=self.language,
            api_key=self.api_key,
            api_base=self.api_base
        )
        generated_ideas = ai_participant.generate_ideas(
            company_context=company_context,
            previous_ideas=previous_idea_texts,
            round_number=sheet.current_round,
            participant_number=sheet.sheet_number,
            all_session_ideas=all_session_ideas
        )

        return generated_ideas

    def rotate_sheets(self, session_uuid: str, generate_ai_ideas: bool = True) -> Dict:
        """
        Rotate sheets to next participants for next round.

        Args:
            session_uuid: Session UUID
            generate_ai_ideas: Whether to generate AI ideas immediately (set False for background generation)

        Returns:
            Rotation result
        """
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        # Get all participants
        participants = self.db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).order_by(Participant.id).all()

        # Get all sheets
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).order_by(IdeaSheet.sheet_number).all()

        if not sheets:
            raise ValueError("No sheets found")

        # Check if session is complete
        current_round = sheets[0].current_round
        if current_round >= self.MAX_ROUNDS:
            return {"status": "complete", "total_rounds": current_round}

        # Rotate sheets (shift right)
        new_round = current_round + 1
        participant_assignments = []

        for i, sheet in enumerate(sheets):
            # Next participant index (rotate right)
            next_participant_idx = (i + 1) % len(participants)
            sheet.current_participant_id = participants[next_participant_idx].id
            sheet.current_round = new_round
            participant_assignments.append({
                "sheet_id": sheet.id,
                "participant_id": participants[next_participant_idx].id
            })

        self.db.commit()

        # Generate AI ideas for the new round (unless deferred for background processing)
        if generate_ai_ideas:
            self._generate_ai_ideas_for_round(session_uuid)

        return {
            "status": "rotated",
            "current_round": new_round,
            "assignments": participant_assignments
        }

    def get_session_status(self, session_uuid: str) -> Dict:
        """
        Get current session status.

        Args:
            session_uuid: Session UUID

        Returns:
            Session status
        """
        # Get session
        db_session = self.db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        if not db_session:
            raise ValueError(f"Session {session_uuid} not found")

        # Get participants
        participants = self.db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).all()

        # Get sheets
        sheets = self.db.query(IdeaSheet).filter(
            IdeaSheet.session_id == db_session.id
        ).all()

        if not sheets:
            return {
                "status": "not_started",
                "participants": len(participants)
            }

        current_round = sheets[0].current_round if sheets else 0

        # Count submitted ideas for current round
        submitted_count = 0
        for sheet in sheets:
            ideas_count = self.db.query(Idea).filter(
                Idea.sheet_id == sheet.id,
                Idea.round_number == current_round
            ).count()
            if ideas_count >= self.IDEAS_PER_ROUND:
                submitted_count += 1

        is_complete = current_round >= self.MAX_ROUNDS or (
            submitted_count == len(sheets) and current_round == self.MAX_ROUNDS
        )

        return {
            "status": "complete" if is_complete else "in_progress",
            "current_round": current_round,
            "total_participants": len(participants),
            "human_participants": sum(1 for p in participants if p.connection_status != "ai_controlled"),
            "ai_participants": sum(1 for p in participants if p.connection_status == "ai_controlled"),
            "sheets_submitted": submitted_count,
            "total_sheets": len(sheets)
        }
