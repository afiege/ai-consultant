"""Router for expert mode settings."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
import httpx
from typing import Optional, List
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


class FetchModelsRequest(BaseModel):
    """Request model for fetching available models from a provider."""
    api_base: str
    api_key: str


class FetchModelsResponse(BaseModel):
    """Response model for fetched models."""
    success: bool
    models: List[str]
    fallback: bool = False  # True if using hardcoded fallback list
    message: Optional[str] = None

router = APIRouter()


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


# Keywords that indicate non-text models (vision, image generation, embeddings, audio, etc.)
NON_TEXT_MODEL_KEYWORDS = [
    "vision", "image", "img", "visual", "picture", "photo",
    "embed", "embedding",
    "audio", "speech", "tts", "whisper", "voice",
    "video", "clip",
    "dall-e", "dalle", "stable-diffusion", "sdxl", "flux",
    "moderation",
]


def is_text_model(model_id: str) -> bool:
    """Check if a model is a text-based model (not vision/image/audio/embedding)."""
    model_lower = model_id.lower()
    for keyword in NON_TEXT_MODEL_KEYWORDS:
        if keyword in model_lower:
            return False
    return True


@router.post("/expert-settings/fetch-models", response_model=FetchModelsResponse)
async def fetch_provider_models(request: FetchModelsRequest):
    """
    Fetch available models from a provider's /v1/models endpoint.

    Falls back to hardcoded list if the provider is unreachable or doesn't support listing.
    Only returns text-based models (filters out vision/image/audio models).
    """
    if not request.api_base:
        return FetchModelsResponse(
            success=False,
            models=[],
            message="API base URL is required"
        )

    if not request.api_key:
        return FetchModelsResponse(
            success=False,
            models=[],
            message="API key is required to fetch models"
        )

    # Find fallback models from hardcoded list
    fallback_models = []
    for provider in LLM_PROVIDERS:
        if provider.api_base == request.api_base:
            fallback_models = provider.models
            break

    # Normalize the API base URL
    api_base = request.api_base.rstrip('/')
    models_url = f"{api_base}/models"

    print(f"[Fetch Models] Querying: {models_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json"
                }
            )

            print(f"[Fetch Models] Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # OpenAI-compatible format: {"data": [{"id": "model-name", ...}, ...]}
                if "data" in data and isinstance(data["data"], list):
                    models = []
                    filtered_count = 0
                    for model_info in data["data"]:
                        model_id = model_info.get("id", "")
                        if model_id:
                            # Add openai/ prefix for LiteLLM compatibility with custom endpoints
                            if not any(model_id.startswith(p) for p in ["openai/", "mistral/", "anthropic/", "ollama/"]):
                                model_id = f"openai/{model_id}"
                            # Filter out non-text models (vision, image, audio, etc.)
                            if is_text_model(model_id):
                                models.append(model_id)
                            else:
                                filtered_count += 1

                    # Sort models alphabetically
                    models.sort()

                    print(f"[Fetch Models] Found {len(models)} text models (filtered out {filtered_count} non-text models)")

                    return FetchModelsResponse(
                        success=True,
                        models=models,
                        fallback=False,
                        message=f"Found {len(models)} text models"
                    )
                else:
                    print(f"[Fetch Models] Unexpected response format: {list(data.keys())}")
                    # Fall through to fallback

            elif response.status_code == 401:
                return FetchModelsResponse(
                    success=False,
                    models=fallback_models,
                    fallback=True,
                    message="Authentication failed. Using default model list."
                )

            else:
                print(f"[Fetch Models] Error response: {response.text[:200]}")
                # Fall through to fallback

    except httpx.TimeoutException:
        print(f"[Fetch Models] Timeout connecting to {models_url}")
        return FetchModelsResponse(
            success=False,
            models=fallback_models,
            fallback=True,
            message="Connection timeout. Using default model list."
        )
    except Exception as e:
        print(f"[Fetch Models] Error: {type(e).__name__}: {str(e)}")
        return FetchModelsResponse(
            success=False,
            models=fallback_models,
            fallback=True,
            message=f"Could not fetch models: {str(e)[:100]}. Using default model list."
        )

    # Fallback if we got here without returning
    if fallback_models:
        return FetchModelsResponse(
            success=False,
            models=fallback_models,
            fallback=True,
            message="Could not fetch models from provider. Using default model list."
        )
    else:
        return FetchModelsResponse(
            success=False,
            models=[],
            fallback=False,
            message="Could not fetch models and no default list available for this provider."
        )


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

        # Debug logging
        print(f"[LLM Test] Model: {request.model}")
        print(f"[LLM Test] API Base: {request.api_base}")
        print(f"[LLM Test] API Key (first 10 chars): {request.api_key[:10] if request.api_key else 'None'}...")
        print(f"[LLM Test] Full completion_kwargs: {list(completion_kwargs.keys())}")

        # Safety check: if model has openai/ prefix but no api_base, warn
        if request.model and request.model.startswith("openai/") and not request.api_base:
            print(f"[LLM Test] WARNING: Model has 'openai/' prefix but no api_base - will call OpenAI API!")
            return LLMTestResponse(
                success=False,
                message="Model uses 'openai/' prefix but no API base URL is set. This would call the OpenAI API. Please select a provider first."
            )

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
        print(f"[LLM Test] Error: {error_message}")
        print(f"[LLM Test] Exception type: {type(e).__name__}")

        # Provide more helpful error messages
        if "401" in error_message or "Unauthorized" in error_message.lower() or "invalid" in error_message.lower():
            return LLMTestResponse(
                success=False,
                message=f"Authentication failed. Please check your API key. (Details: {error_message[:100]})"
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

    # Build LLM config (api_key is not stored, only model and api_base)
    llm_config = None
    if db_session.llm_model or db_session.llm_api_base:
        llm_config = LLMConfig(
            model=db_session.llm_model,
            api_key=None,  # API key is not stored
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

    # Update LLM config if provided (only model and api_base, NOT api_key)
    if update_settings.llm_config is not None:
        llm_config = update_settings.llm_config

        # Update model if provided
        if llm_config.model is not None:
            db_session.llm_model = llm_config.model if llm_config.model else None

        # Update api_base if provided
        if llm_config.api_base is not None:
            db_session.llm_api_base = llm_config.api_base if llm_config.api_base else None

        # Note: api_key is NOT stored - it's passed per-request by the frontend

    db.commit()
    db.refresh(db_session)

    # Build response (api_key is not stored)
    llm_config_response = None
    if db_session.llm_model or db_session.llm_api_base:
        llm_config_response = LLMConfig(
            model=db_session.llm_model,
            api_key=None,  # API key is not stored
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
        "idea_clustering_system",
        "consultation_system",
        "consultation_context",
        "extraction_summary",
        "business_case_system",
        "business_case_extraction",
        "cost_estimation_system",
        "cost_estimation_extraction",
        "transition_briefing_system",
        "swot_analysis_system"
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
