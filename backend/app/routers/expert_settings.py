"""Router for expert mode settings."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
from typing import Optional, List
from cryptography.fernet import Fernet
from litellm import completion

from ..database import get_db
from ..models import Session as SessionModel
from ..schemas import (
    ExpertSettingsUpdate,
    ExpertSettingsResponse,
    DefaultPromptsResponse,
    CustomPrompts,
    PromptMetadataResponse,
    PROMPT_METADATA,
    LLMConfig,
    LLMProviderInfo,
    LLM_PROVIDERS,
)
from ..services.default_prompts import get_all_defaults
from ..config import settings


class LLMTestRequest(BaseModel):
    """Request model for testing LLM connection."""
    model: str
    api_key: str
    api_base: Optional[str] = None


class LLMTestResponse(BaseModel):
    """Response model for LLM connection test."""
    success: bool
    message: str
    response_preview: Optional[str] = None

router = APIRouter()


def _encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    cipher = Fernet(settings.get_encryption_key.encode())
    return cipher.encrypt(api_key.encode()).decode()


def _decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from storage."""
    cipher = Fernet(settings.get_encryption_key.encode())
    return cipher.decrypt(encrypted_key.encode()).decode()


def _mask_api_key(api_key: str) -> str:
    """Mask an API key for display (show first 4 and last 4 chars)."""
    if not api_key or len(api_key) < 12:
        return "****" if api_key else None
    return f"{api_key[:4]}...{api_key[-4:]}"


def _get_session(db: Session, session_uuid: str) -> SessionModel:
    """Helper to get session or raise 404."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    return db_session


def _parse_custom_prompts(json_str: Optional[str]) -> Optional[CustomPrompts]:
    """Parse custom prompts JSON string to CustomPrompts object."""
    if not json_str:
        return None
    try:
        data = json.loads(json_str)
        return CustomPrompts(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def _serialize_custom_prompts(prompts: Optional[CustomPrompts]) -> Optional[str]:
    """Serialize CustomPrompts object to JSON string."""
    if not prompts:
        return None
    # Filter out None values
    data = {k: v for k, v in prompts.model_dump().items() if v is not None}
    if not data:
        return None
    return json.dumps(data)


@router.get("/expert-settings/defaults", response_model=DefaultPromptsResponse)
def get_default_prompts():
    """Get all default prompts in both languages."""
    defaults = get_all_defaults()
    return DefaultPromptsResponse(
        en=CustomPrompts(**defaults["en"]),
        de=CustomPrompts(**defaults["de"])
    )


@router.get("/expert-settings/metadata", response_model=PromptMetadataResponse)
def get_prompt_metadata():
    """Get metadata about all available prompts (labels, descriptions, variables)."""
    return PromptMetadataResponse(prompts=PROMPT_METADATA)


@router.get("/expert-settings/llm-providers", response_model=List[LLMProviderInfo])
def get_llm_providers():
    """Get available LLM provider presets."""
    return LLM_PROVIDERS


@router.post("/expert-settings/test-llm", response_model=LLMTestResponse)
def test_llm_connection(request: LLMTestRequest):
    """
    Test LLM connection with the provided configuration.

    Makes a simple API call to verify the model and API key work.
    """
    if not request.model:
        return LLMTestResponse(
            success=False,
            message="Model is required"
        )

    if not request.api_key:
        return LLMTestResponse(
            success=False,
            message="API key is required"
        )

    try:
        # Build completion kwargs
        completion_kwargs = {
            "model": request.model,
            "messages": [
                {"role": "user", "content": "Say 'Connection successful!' in exactly those words."}
            ],
            "temperature": 0.1,
            "max_tokens": 50,
            "api_key": request.api_key
        }

        if request.api_base:
            completion_kwargs["api_base"] = request.api_base

        # Make test call
        response = completion(**completion_kwargs)

        # Extract response content
        content = response.choices[0].message.content

        return LLMTestResponse(
            success=True,
            message="Connection successful! The API key and model are working.",
            response_preview=content[:100] if content else None
        )

    except Exception as e:
        error_message = str(e)

        # Provide more helpful error messages
        if "401" in error_message or "Unauthorized" in error_message.lower() or "invalid" in error_message.lower():
            return LLMTestResponse(
                success=False,
                message="Authentication failed. Please check your API key."
            )
        elif "404" in error_message or "not found" in error_message.lower():
            return LLMTestResponse(
                success=False,
                message=f"Model '{request.model}' not found. Please check the model name."
            )
        elif "timeout" in error_message.lower() or "connect" in error_message.lower():
            return LLMTestResponse(
                success=False,
                message="Connection timeout. Please check the API base URL and your network."
            )
        else:
            return LLMTestResponse(
                success=False,
                message=f"Connection failed: {error_message[:200]}"
            )


@router.get("/{session_uuid}/expert-settings", response_model=ExpertSettingsResponse)
def get_expert_settings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get expert mode settings for a session."""
    db_session = _get_session(db, session_uuid)

    # Build LLM config with masked API key
    llm_config = None
    if db_session.llm_model or db_session.llm_api_base or db_session.llm_api_key_encrypted:
        masked_key = None
        if db_session.llm_api_key_encrypted:
            try:
                decrypted = _decrypt_api_key(db_session.llm_api_key_encrypted)
                masked_key = _mask_api_key(decrypted)
            except Exception:
                masked_key = "****"

        llm_config = LLMConfig(
            model=db_session.llm_model,
            api_key=masked_key,
            api_base=db_session.llm_api_base
        )

    return ExpertSettingsResponse(
        expert_mode=db_session.expert_mode or False,
        prompt_language=db_session.prompt_language or "en",
        custom_prompts=_parse_custom_prompts(db_session.custom_prompts),
        llm_config=llm_config
    )


@router.put("/{session_uuid}/expert-settings", response_model=ExpertSettingsResponse)
def update_expert_settings(
    session_uuid: str,
    update_settings: ExpertSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update expert mode settings for a session."""
    db_session = _get_session(db, session_uuid)

    # Update expert_mode if provided
    if update_settings.expert_mode is not None:
        db_session.expert_mode = update_settings.expert_mode

    # Update prompt_language if provided
    if update_settings.prompt_language is not None:
        db_session.prompt_language = update_settings.prompt_language.value

    # Update custom_prompts if provided
    if update_settings.custom_prompts is not None:
        # Merge with existing custom prompts
        existing = _parse_custom_prompts(db_session.custom_prompts) or CustomPrompts()
        existing_data = existing.model_dump()
        new_data = update_settings.custom_prompts.model_dump()

        # Update only non-None values
        for key, value in new_data.items():
            if value is not None:
                existing_data[key] = value

        db_session.custom_prompts = _serialize_custom_prompts(CustomPrompts(**existing_data))

    # Update LLM config if provided
    if update_settings.llm_config is not None:
        llm_config = update_settings.llm_config

        # Update model if provided
        if llm_config.model is not None:
            db_session.llm_model = llm_config.model if llm_config.model else None

        # Update api_base if provided
        if llm_config.api_base is not None:
            db_session.llm_api_base = llm_config.api_base if llm_config.api_base else None

        # Update api_key if provided (encrypt it)
        if llm_config.api_key is not None:
            if llm_config.api_key:
                db_session.llm_api_key_encrypted = _encrypt_api_key(llm_config.api_key)
            else:
                db_session.llm_api_key_encrypted = None

    db.commit()
    db.refresh(db_session)

    # Build response with masked API key
    llm_config_response = None
    if db_session.llm_model or db_session.llm_api_base or db_session.llm_api_key_encrypted:
        masked_key = None
        if db_session.llm_api_key_encrypted:
            try:
                decrypted = _decrypt_api_key(db_session.llm_api_key_encrypted)
                masked_key = _mask_api_key(decrypted)
            except Exception:
                masked_key = "****"

        llm_config_response = LLMConfig(
            model=db_session.llm_model,
            api_key=masked_key,
            api_base=db_session.llm_api_base
        )

    return ExpertSettingsResponse(
        expert_mode=db_session.expert_mode or False,
        prompt_language=db_session.prompt_language or "en",
        custom_prompts=_parse_custom_prompts(db_session.custom_prompts),
        llm_config=llm_config_response
    )


@router.post("/{session_uuid}/expert-settings/reset-prompt/{prompt_key}")
def reset_prompt_to_default(
    session_uuid: str,
    prompt_key: str,
    db: Session = Depends(get_db)
):
    """Reset a specific prompt to its default value."""
    valid_keys = [
        "brainstorming_system",
        "brainstorming_round1",
        "brainstorming_subsequent",
        "consultation_system",
        "extraction_summary"
    ]

    if prompt_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid prompt key. Must be one of: {', '.join(valid_keys)}"
        )

    db_session = _get_session(db, session_uuid)

    # Parse existing custom prompts
    custom_prompts = _parse_custom_prompts(db_session.custom_prompts)

    if custom_prompts:
        # Set the specified prompt to None (will use default)
        data = custom_prompts.model_dump()
        data[prompt_key] = None
        db_session.custom_prompts = _serialize_custom_prompts(CustomPrompts(**data))

        db.commit()
        db.refresh(db_session)

    return {"status": "success", "message": f"Prompt '{prompt_key}' reset to default"}


@router.post("/{session_uuid}/expert-settings/reset-all")
def reset_all_prompts(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Reset all custom prompts to defaults."""
    db_session = _get_session(db, session_uuid)

    db_session.custom_prompts = None

    db.commit()
    db.refresh(db_session)

    return {"status": "success", "message": "All custom prompts reset to defaults"}
