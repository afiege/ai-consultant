"""Schemas for expert mode settings."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from enum import Enum


class PromptLanguage(str, Enum):
    """Supported prompt languages."""
    EN = "en"
    DE = "de"


class CustomPrompts(BaseModel):
    """Schema for custom prompt overrides."""
    brainstorming_system: Optional[str] = None
    brainstorming_round1: Optional[str] = None
    brainstorming_subsequent: Optional[str] = None
    consultation_system: Optional[str] = None
    extraction_summary: Optional[str] = None


class LLMConfig(BaseModel):
    """Schema for LLM configuration."""
    model: Optional[str] = None  # e.g., "meta-llama-3.1-8b-instruct"
    api_key: Optional[str] = None  # Will be encrypted when stored
    api_base: Optional[str] = None  # e.g., "https://chat-ai.academiccloud.de/v1"


class ExpertSettingsUpdate(BaseModel):
    """Schema for updating expert settings."""
    expert_mode: Optional[bool] = None
    prompt_language: Optional[PromptLanguage] = None
    custom_prompts: Optional[CustomPrompts] = None
    llm_config: Optional[LLMConfig] = None


class ExpertSettingsResponse(BaseModel):
    """Schema for expert settings response."""
    expert_mode: bool = False
    prompt_language: PromptLanguage = PromptLanguage.EN
    custom_prompts: Optional[CustomPrompts] = None
    llm_config: Optional[LLMConfig] = None  # Note: api_key will be masked

    class Config:
        from_attributes = True


class LLMProviderInfo(BaseModel):
    """Information about an LLM provider preset."""
    name: str
    api_base: str
    models: List[str]


# Available LLM provider presets
# Note: Model names must include LiteLLM provider prefix (e.g., openai/, mistral/, ollama/)
LLM_PROVIDERS = [
    LLMProviderInfo(
        name="AcademicCloud (SAIA)",
        api_base="https://chat-ai.academiccloud.de/v1",
        models=[
            "openai/meta-llama-3.1-8b-instruct",
            "openai/llama-3.3-70b-instruct",
            "openai/mistral-large-instruct",
            "openai/qwen3-32b",
            "openai/qwq-32b",
            "openai/deepseek-r1",
            "openai/qwen2.5-coder-32b-instruct",
            "openai/codestral-22b",
        ]
    ),
    LLMProviderInfo(
        name="OpenAI",
        api_base="",
        models=[
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
    ),
    LLMProviderInfo(
        name="Mistral",
        api_base="",
        models=[
            "mistral/mistral-small-latest",
            "mistral/mistral-medium-latest",
            "mistral/mistral-large-latest",
        ]
    ),
    LLMProviderInfo(
        name="Local (Ollama)",
        api_base="http://localhost:11434/v1",
        models=[
            "ollama/llama2",
            "ollama/llama3",
            "ollama/mistral",
            "ollama/codellama",
        ]
    ),
]


class DefaultPromptsResponse(BaseModel):
    """Response containing default prompts for both languages."""
    en: CustomPrompts
    de: CustomPrompts


class PromptInfo(BaseModel):
    """Information about a single prompt."""
    key: str
    label: str
    description: str
    variables: list[str]


class PromptMetadataResponse(BaseModel):
    """Metadata about all available prompts."""
    prompts: list[PromptInfo]


# Prompt metadata for frontend display
PROMPT_METADATA = [
    PromptInfo(
        key="brainstorming_system",
        label="Brainstorming System Prompt",
        description="Sets the AI's role and context for the 6-3-5 brainstorming session",
        variables=["company_context"]
    ),
    PromptInfo(
        key="brainstorming_round1",
        label="Round 1 User Prompt",
        description="Instructions for generating ideas in the first round (blank sheet)",
        variables=["round_number", "uniqueness_note"]
    ),
    PromptInfo(
        key="brainstorming_subsequent",
        label="Subsequent Rounds Prompt",
        description="Instructions for building on previous ideas in rounds 2-6",
        variables=["round_number", "previous_ideas_numbered", "uniqueness_note"]
    ),
    PromptInfo(
        key="consultation_system",
        label="Business Understanding Prompt",
        description="CRISP-DM Business Understanding phase - guides the consultant through objectives, situation assessment, AI goals, and project planning",
        variables=["company_name", "company_info_text", "top_ideas_text", "focus_idea"]
    ),
    PromptInfo(
        key="extraction_summary",
        label="CRISP-DM Summary Extraction",
        description="Extracts structured Business Understanding outputs: objectives, situation, AI goals, and project plan",
        variables=[]
    ),
]
