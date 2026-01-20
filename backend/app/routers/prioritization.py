"""
Prioritization router - Step 3: Idea Prioritization

Each participant receives 3 points to distribute among ideas.
The idea(s) with the most points will be used in the consultation phase.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict
from pydantic import BaseModel, Field

from ..database import get_db
from ..models.session import Session as SessionModel
from ..models.idea import Idea
from ..models.prioritization import Prioritization
from ..models.participant import Participant
from ..schemas.prioritization import PrioritizationResponse, IdeaWithScore


router = APIRouter()


# Request/Response schemas
class VoteSubmission(BaseModel):
    """Schema for submitting votes - participant allocates points to ideas."""
    participant_uuid: str
    votes: Dict[int, int] = Field(..., description="Map of idea_id -> points (must sum to 3)")


class VotingStatus(BaseModel):
    """Status of voting for a session."""
    total_participants: int
    voted_count: int
    participants_voted: List[str]  # participant names
    all_voted: bool


@router.post("/{session_uuid}/prioritization/vote")
def submit_votes(
    session_uuid: str,
    vote_data: VoteSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit prioritization votes for a participant.
    Each participant has 3 points total to distribute among ideas.
    """
    # Validate session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Validate participant exists
    participant = db.query(Participant).filter(
        Participant.participant_uuid == vote_data.participant_uuid,
        Participant.session_id == db_session.id
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in this session"
        )

    # Validate total points = 3
    total_points = sum(vote_data.votes.values())
    if total_points != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Must allocate exactly 3 points. You allocated {total_points} points."
        )

    # Validate all points are positive
    if any(points <= 0 for points in vote_data.votes.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All point allocations must be positive"
        )

    # Validate all idea IDs exist and belong to this session
    idea_ids = list(vote_data.votes.keys())
    ideas = db.query(Idea).join(Idea.sheet).filter(
        Idea.id.in_(idea_ids)
    ).all()

    if len(ideas) != len(idea_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more idea IDs are invalid"
        )

    # Verify ideas belong to this session
    for idea in ideas:
        if idea.sheet.session_id != db_session.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Idea {idea.id} does not belong to this session"
            )

    # Delete any existing votes from this participant
    db.query(Prioritization).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.participant_id == participant.id
    ).delete()

    # Create new votes
    for idea_id, points in vote_data.votes.items():
        vote = Prioritization(
            session_id=db_session.id,
            idea_id=idea_id,
            participant_id=participant.id,
            vote_type="points",
            score=points
        )
        db.add(vote)

    db.commit()

    return {
        "status": "success",
        "participant": participant.name,
        "votes_recorded": len(vote_data.votes),
        "total_points": total_points
    }


@router.get("/{session_uuid}/prioritization/status")
def get_voting_status(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get voting status - how many participants have voted."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all participants (excluding AI-only or manual entry)
    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).all()

    # Check which participants have voted
    voted_participant_ids = db.query(Prioritization.participant_id).filter(
        Prioritization.session_id == db_session.id
    ).distinct().all()

    voted_ids = {pid[0] for pid in voted_participant_ids}

    participants_voted = [
        p.name for p in participants if p.id in voted_ids
    ]

    return VotingStatus(
        total_participants=len(participants),
        voted_count=len(voted_ids),
        participants_voted=participants_voted,
        all_voted=len(voted_ids) == len(participants) and len(participants) > 0
    )


@router.get("/{session_uuid}/prioritization/results")
def get_prioritization_results(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get prioritization results with ranked ideas.
    Returns all ideas sorted by total points received.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all ideas with their total points
    results = db.query(
        Idea.id,
        Idea.content,
        Participant.name.label('participant_name'),
        Idea.round_number,
        func.coalesce(func.sum(Prioritization.score), 0).label('total_points'),
        func.count(Prioritization.id).label('vote_count')
    ).join(
        Idea.participant
    ).outerjoin(
        Prioritization, Prioritization.idea_id == Idea.id
    ).join(
        Idea.sheet
    ).filter(
        Idea.sheet.has(session_id=db_session.id)
    ).group_by(
        Idea.id, Idea.content, Participant.name, Idea.round_number
    ).order_by(
        func.sum(Prioritization.score).desc().nullslast(),
        Idea.id
    ).all()

    # Format results
    ranked_ideas = []
    current_rank = 1
    prev_points = None

    for idx, result in enumerate(results):
        # Update rank if points changed
        if prev_points is not None and result.total_points != prev_points:
            current_rank = idx + 1

        ranked_ideas.append({
            "idea_id": result.id,
            "idea_content": result.content,
            "participant_name": result.participant_name,
            "round_number": result.round_number,
            "total_points": result.total_points,
            "vote_count": result.vote_count,
            "rank": current_rank
        })

        prev_points = result.total_points

    # Get top ideas (those with rank 1)
    top_ideas = [idea for idea in ranked_ideas if idea["rank"] == 1]

    return {
        "ranked_ideas": ranked_ideas,
        "top_ideas": top_ideas,
        "total_ideas": len(ranked_ideas)
    }
