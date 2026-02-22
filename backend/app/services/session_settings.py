"""
Session Settings Service

Centralized service for retrieving session-specific settings like LLM configuration.
This eliminates duplicated get_llm_settings() functions across routers.
"""

from typing import Optional, NamedTuple
from ..models import Session as SessionModel
from ..config import settings


class LLMConfig(NamedTuple):
    """LLM configuration from session or defaults."""
    model: str
    api_base: Optional[str]


def get_llm_settings(db_session: SessionModel) -> LLMConfig:
    """
    Get LLM settings from session, falling back to environment defaults.

    Args:
        db_session: The database session model

    Returns:
        LLMConfig with model name and optional API base URL
    """
    model = db_session.llm_model or settings.llm_model
    api_base = db_session.llm_api_base or settings.llm_api_base or None
    return LLMConfig(model=model, api_base=api_base)


def get_temperature_config(db_session: SessionModel) -> dict:
    """
    Get per-step temperature configuration from session.

    Args:
        db_session: The database session model

    Returns:
        Dictionary with temperature keys (brainstorming, consultation, business_case,
        cost_estimation, extraction, export) or empty dict if no config stored.
    """
    import json
    if db_session.temperature_config:
        try:
            return json.loads(db_session.temperature_config)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def get_prompt_language(db_session: SessionModel) -> str:
    """
    Get the prompt language from session settings.

    Args:
        db_session: The database session model

    Returns:
        Language code ('en' or 'de')
    """
    return db_session.prompt_language or 'en'


def get_custom_prompts(db_session: SessionModel) -> Optional[dict]:
    """
    Get custom prompts from session if expert mode is enabled.

    Args:
        db_session: The database session model

    Returns:
        Dictionary of custom prompts or None
    """
    import json
    if db_session.custom_prompts:
        try:
            return json.loads(db_session.custom_prompts)
        except json.JSONDecodeError:
            return None
    return None


def is_expert_mode(db_session: SessionModel) -> bool:
    """
    Check if expert mode is enabled for the session.

    Args:
        db_session: The database session model

    Returns:
        True if expert mode is enabled
    """
    return db_session.expert_mode or False
