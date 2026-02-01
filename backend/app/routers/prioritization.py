"""
Prioritization router - Step 3: Idea Prioritization (Two-Phase)

Phase 1 (Cluster Prioritization):
- LLM clusters ideas by technology/concept
- Participants vote on which cluster to focus on

Phase 2 (Idea Prioritization):
- Participants vote on specific ideas within the selected cluster
- Top idea(s) proceed to consultation phase
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from ..database import get_db
from ..models.session import Session as SessionModel
from ..models.idea import Idea
from ..models.prioritization import Prioritization
from ..models.participant import Participant
from ..models.maturity_assessment import MaturityAssessment
from ..models.company_info import CompanyInfo
from ..schemas.prioritization import PrioritizationResponse, IdeaWithScore, ClusteringResult, ClusterWithScore
from ..services.ai_participant import cluster_ideas, assess_ideas, get_company_context_summary, _create_fallback_clusters
from ..config import settings


router = APIRouter()


# Request/Response schemas
class VoteSubmission(BaseModel):
    """Schema for submitting votes - participant allocates points to ideas."""
    participant_uuid: str
    votes: Dict[int, int] = Field(..., description="Map of idea_id -> points (must sum to 3)")


class ClusterVoteSubmission(BaseModel):
    """Schema for submitting cluster votes."""
    participant_uuid: str
    votes: Dict[int, int] = Field(..., description="Map of cluster_id -> points (must sum to 3)")


class ClusterRequest(BaseModel):
    """Schema for requesting idea clustering."""
    api_key: Optional[str] = None


class SelectClusterRequest(BaseModel):
    """Schema for selecting a cluster."""
    cluster_id: int


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


# ============================================
# PHASE 1: CLUSTER PRIORITIZATION ENDPOINTS
# ============================================

@router.post("/{session_uuid}/prioritization/cluster")
def generate_clusters(
    session_uuid: str,
    request: ClusterRequest,
    db: Session = Depends(get_db)
):
    """
    Generate idea clusters using LLM.
    Clusters ideas by technology/concept for two-phase prioritization.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all ideas for this session
    ideas = db.query(Idea).join(Idea.sheet).filter(
        Idea.sheet.has(session_id=db_session.id)
    ).all()

    if not ideas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ideas found to cluster"
        )

    # Prepare ideas for clustering
    ideas_list = [{"id": idea.id, "content": idea.content} for idea in ideas]

    # Get LLM config from session or use defaults
    model = db_session.llm_model or settings.DEFAULT_LLM_MODEL
    api_base = db_session.llm_api_base or settings.DEFAULT_LLM_API_BASE
    api_key = request.api_key
    language = db_session.prompt_language or "en"

    # Get custom prompts if any
    custom_prompts = None
    if db_session.custom_prompts:
        try:
            custom_prompts = json.loads(db_session.custom_prompts)
        except:
            pass

    # Get maturity assessment for the session
    maturity = db.query(MaturityAssessment).filter(
        MaturityAssessment.session_id == db_session.id
    ).first()

    maturity_level = None
    maturity_level_name = None
    if maturity:
        maturity_level = maturity.overall_score
        # Map score to maturity level name
        maturity_names = {
            1: "Computerization" if language == "en" else "Computerisierung",
            2: "Connectivity" if language == "en" else "Konnektivität",
            3: "Visibility" if language == "en" else "Sichtbarkeit",
            4: "Transparency" if language == "en" else "Transparenz",
            5: "Predictive Capacity" if language == "en" else "Prognosefähigkeit",
            6: "Adaptability" if language == "en" else "Adaptierbarkeit"
        }
        maturity_level_name = maturity_names.get(int(maturity_level) if maturity_level else 1, "Unknown")

    # Get company context for clustering
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()
    company_context = get_company_context_summary(company_infos) if company_infos else None

    # Generate clusters with fallback
    try:
        result = cluster_ideas(
            ideas=ideas_list,
            model=model,
            language=language,
            api_key=api_key,
            api_base=api_base,
            custom_prompts=custom_prompts,
            maturity_level=int(maturity_level) if maturity_level else None,
            maturity_level_name=maturity_level_name,
            company_context=company_context
        )

        # Validate result has clusters
        if not result.get("clusters") or len(result["clusters"]) == 0:
            raise ValueError("Empty clusters returned")

    except Exception as e:
        # Fallback: Create simple clusters using helper function
        import logging
        logging.error(f"LLM clustering failed, using fallback: {e}")
        result = _create_fallback_clusters(ideas_list, language)

    # Store clusters in session
    db_session.idea_clusters = json.dumps(result)
    db_session.selected_cluster_id = None  # Reset selection
    db.commit()

    # Clear any existing cluster votes
    db.query(Prioritization).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.vote_phase == "cluster"
    ).delete()
    db.commit()

    return result


@router.get("/{session_uuid}/prioritization/clusters")
def get_clusters(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get the existing clusters for a session."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.idea_clusters:
        return {"clusters": [], "selected_cluster_id": None}

    try:
        clusters = json.loads(db_session.idea_clusters)
    except:
        clusters = {"clusters": []}

    # Get ideas to include full content in response
    ideas = db.query(Idea).join(Idea.sheet).filter(
        Idea.sheet.has(session_id=db_session.id)
    ).all()
    ideas_dict = {idea.id: {"id": idea.id, "content": idea.content} for idea in ideas}

    # Enrich clusters with idea content
    for cluster in clusters.get("clusters", []):
        cluster["ideas"] = [
            ideas_dict.get(idea_id, {"id": idea_id, "content": "Unknown"})
            for idea_id in cluster.get("idea_ids", [])
        ]

    return {
        "clusters": clusters.get("clusters", []),
        "selected_cluster_id": db_session.selected_cluster_id
    }


@router.post("/{session_uuid}/prioritization/cluster-vote")
def submit_cluster_votes(
    session_uuid: str,
    vote_data: ClusterVoteSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit cluster votes (Phase 1).
    Each participant has 3 points to distribute among clusters.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Validate clusters exist
    if not db_session.idea_clusters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No clusters found. Generate clusters first."
        )

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        valid_cluster_ids = {c["id"] for c in clusters_data.get("clusters", [])}
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cluster data"
        )

    # Validate participant
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

    # Validate cluster IDs
    for cluster_id in vote_data.votes.keys():
        if cluster_id not in valid_cluster_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cluster ID: {cluster_id}"
            )

    # Delete existing cluster votes from this participant
    db.query(Prioritization).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.participant_id == participant.id,
        Prioritization.vote_phase == "cluster"
    ).delete()

    # Create new cluster votes
    for cluster_id, points in vote_data.votes.items():
        vote = Prioritization(
            session_id=db_session.id,
            cluster_id=cluster_id,
            participant_id=participant.id,
            vote_type="points",
            vote_phase="cluster",
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


@router.get("/{session_uuid}/prioritization/cluster-results")
def get_cluster_results(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get cluster voting results (Phase 1)."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.idea_clusters:
        return {"ranked_clusters": [], "top_clusters": [], "selected_cluster_id": None}

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        clusters = clusters_data.get("clusters", [])
    except:
        return {"ranked_clusters": [], "top_clusters": [], "selected_cluster_id": None}

    # Get votes for each cluster
    cluster_votes = db.query(
        Prioritization.cluster_id,
        func.coalesce(func.sum(Prioritization.score), 0).label('total_points'),
        func.count(Prioritization.id).label('vote_count')
    ).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.vote_phase == "cluster"
    ).group_by(
        Prioritization.cluster_id
    ).all()

    votes_dict = {v.cluster_id: {"total_points": v.total_points, "vote_count": v.vote_count} for v in cluster_votes}

    # Build ranked clusters list
    ranked_clusters = []
    for cluster in clusters:
        vote_info = votes_dict.get(cluster["id"], {"total_points": 0, "vote_count": 0})
        ranked_clusters.append({
            "cluster_id": cluster["id"],
            "cluster_name": cluster["name"],
            "cluster_description": cluster["description"],
            "idea_count": len(cluster.get("idea_ids", [])),
            "total_points": vote_info["total_points"],
            "vote_count": vote_info["vote_count"]
        })

    # Sort by total points descending
    ranked_clusters.sort(key=lambda x: x["total_points"], reverse=True)

    # Assign ranks
    current_rank = 1
    prev_points = None
    for idx, cluster in enumerate(ranked_clusters):
        if prev_points is not None and cluster["total_points"] != prev_points:
            current_rank = idx + 1
        cluster["rank"] = current_rank
        prev_points = cluster["total_points"]

    # Get top clusters (rank 1)
    top_clusters = [c for c in ranked_clusters if c["rank"] == 1]

    return {
        "ranked_clusters": ranked_clusters,
        "top_clusters": top_clusters,
        "selected_cluster_id": db_session.selected_cluster_id
    }


@router.post("/{session_uuid}/prioritization/select-cluster")
def select_cluster(
    session_uuid: str,
    request: SelectClusterRequest,
    db: Session = Depends(get_db)
):
    """
    Select the winning cluster for Phase 2.
    This finalizes Phase 1 and enables voting on individual ideas within the cluster.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.idea_clusters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No clusters found"
        )

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        valid_cluster_ids = {c["id"] for c in clusters_data.get("clusters", [])}
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cluster data"
        )

    if request.cluster_id not in valid_cluster_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cluster ID: {request.cluster_id}"
        )

    # Update session with selected cluster
    db_session.selected_cluster_id = request.cluster_id
    db.commit()

    # Get the selected cluster info
    selected_cluster = next(
        (c for c in clusters_data["clusters"] if c["id"] == request.cluster_id),
        None
    )

    return {
        "status": "success",
        "selected_cluster_id": request.cluster_id,
        "selected_cluster": selected_cluster
    }


@router.get("/{session_uuid}/prioritization/cluster-status")
def get_cluster_voting_status(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get cluster voting status (Phase 1) - how many participants have voted."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all participants
    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).all()

    # Check which participants have voted on clusters
    voted_participant_ids = db.query(Prioritization.participant_id).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.vote_phase == "cluster"
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


# ============================================
# PHASE 2: IDEA PRIORITIZATION (WITHIN CLUSTER)
# ============================================

@router.get("/{session_uuid}/prioritization/cluster-ideas")
def get_cluster_ideas(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get the ideas from the selected cluster for Phase 2 voting."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.selected_cluster_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cluster selected. Complete Phase 1 first."
        )

    if not db_session.idea_clusters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No clusters found"
        )

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        selected_cluster = next(
            (c for c in clusters_data["clusters"] if c["id"] == db_session.selected_cluster_id),
            None
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cluster data"
        )

    if not selected_cluster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected cluster not found"
        )

    # Get the ideas in this cluster
    idea_ids = selected_cluster.get("idea_ids", [])
    ideas = db.query(Idea).join(Idea.participant).filter(
        Idea.id.in_(idea_ids)
    ).all()

    return {
        "cluster": selected_cluster,
        "ideas": [
            {
                "id": idea.id,
                "content": idea.content,
                "participant_name": idea.participant.name,
                "round_number": idea.round_number
            }
            for idea in ideas
        ]
    }


class AssessIdeasRequest(BaseModel):
    """Schema for requesting idea assessment."""
    api_key: Optional[str] = None


@router.post("/{session_uuid}/prioritization/assess-cluster-ideas")
def assess_cluster_ideas(
    session_uuid: str,
    request: AssessIdeasRequest,
    db: Session = Depends(get_db)
):
    """
    Assess ideas in the selected cluster for effort and impact.
    Returns ideas with implementation_effort and business_impact ratings.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.selected_cluster_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cluster selected. Complete Phase 1 first."
        )

    if not db_session.idea_clusters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No clusters found"
        )

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        selected_cluster = next(
            (c for c in clusters_data["clusters"] if c["id"] == db_session.selected_cluster_id),
            None
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cluster data"
        )

    if not selected_cluster:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected cluster not found"
        )

    # Get the ideas in this cluster
    idea_ids = selected_cluster.get("idea_ids", [])
    ideas = db.query(Idea).join(Idea.participant).filter(
        Idea.id.in_(idea_ids)
    ).all()

    # Prepare ideas for assessment
    ideas_list = [
        {
            "id": idea.id,
            "content": idea.content,
            "participant_name": idea.participant.name,
            "round_number": idea.round_number
        }
        for idea in ideas
    ]

    # Get LLM config
    model = db_session.llm_model or settings.DEFAULT_LLM_MODEL
    api_base = db_session.llm_api_base or settings.DEFAULT_LLM_API_BASE
    api_key = request.api_key
    language = db_session.prompt_language or "en"

    # Get company context
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()
    company_context = get_company_context_summary(company_infos) if company_infos else None

    # Assess ideas
    result = assess_ideas(
        ideas=ideas_list,
        cluster_info={
            "name": selected_cluster.get("name", ""),
            "description": selected_cluster.get("description", "")
        },
        model=model,
        language=language,
        api_key=api_key,
        api_base=api_base,
        company_context=company_context
    )

    return {
        "cluster": selected_cluster,
        "ideas": result.get("ideas", [])
    }


@router.post("/{session_uuid}/prioritization/idea-vote")
def submit_idea_votes(
    session_uuid: str,
    vote_data: VoteSubmission,
    db: Session = Depends(get_db)
):
    """
    Submit idea votes within the selected cluster (Phase 2).
    Each participant has 3 points to distribute among ideas.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.selected_cluster_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cluster selected. Complete Phase 1 first."
        )

    # Get valid idea IDs from selected cluster
    try:
        clusters_data = json.loads(db_session.idea_clusters)
        selected_cluster = next(
            (c for c in clusters_data["clusters"] if c["id"] == db_session.selected_cluster_id),
            None
        )
        valid_idea_ids = set(selected_cluster.get("idea_ids", [])) if selected_cluster else set()
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cluster data"
        )

    # Validate participant
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

    # Validate idea IDs belong to selected cluster
    for idea_id in vote_data.votes.keys():
        if idea_id not in valid_idea_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Idea {idea_id} is not in the selected cluster"
            )

    # Delete existing idea votes from this participant (Phase 2)
    db.query(Prioritization).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.participant_id == participant.id,
        Prioritization.vote_phase == "idea"
    ).delete()

    # Create new idea votes
    for idea_id, points in vote_data.votes.items():
        vote = Prioritization(
            session_id=db_session.id,
            idea_id=idea_id,
            participant_id=participant.id,
            vote_type="points",
            vote_phase="idea",
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


@router.get("/{session_uuid}/prioritization/idea-results")
def get_idea_results(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get idea voting results within the selected cluster (Phase 2)."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    if not db_session.selected_cluster_id or not db_session.idea_clusters:
        return {"ranked_ideas": [], "top_ideas": [], "cluster": None}

    try:
        clusters_data = json.loads(db_session.idea_clusters)
        selected_cluster = next(
            (c for c in clusters_data["clusters"] if c["id"] == db_session.selected_cluster_id),
            None
        )
        idea_ids = selected_cluster.get("idea_ids", []) if selected_cluster else []
    except:
        return {"ranked_ideas": [], "top_ideas": [], "cluster": None}

    if not idea_ids:
        return {"ranked_ideas": [], "top_ideas": [], "cluster": selected_cluster}

    # Get ideas with their total points (only Phase 2 votes)
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
        Prioritization,
        (Prioritization.idea_id == Idea.id) & (Prioritization.vote_phase == "idea")
    ).filter(
        Idea.id.in_(idea_ids)
    ).group_by(
        Idea.id, Idea.content, Participant.name, Idea.round_number
    ).order_by(
        func.sum(Prioritization.score).desc().nullslast(),
        Idea.id
    ).all()

    # Format results with ranking
    ranked_ideas = []
    current_rank = 1
    prev_points = None

    for idx, result in enumerate(results):
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

    top_ideas = [idea for idea in ranked_ideas if idea["rank"] == 1]

    return {
        "ranked_ideas": ranked_ideas,
        "top_ideas": top_ideas,
        "cluster": selected_cluster
    }


@router.get("/{session_uuid}/prioritization/idea-status")
def get_idea_voting_status(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get idea voting status (Phase 2) - how many participants have voted."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all participants
    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).all()

    # Check which participants have voted on ideas (Phase 2)
    voted_participant_ids = db.query(Prioritization.participant_id).filter(
        Prioritization.session_id == db_session.id,
        Prioritization.vote_phase == "idea"
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
