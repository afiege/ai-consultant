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
    idea_clustering_system: Optional[str] = None
    consultation_system: Optional[str] = None
    consultation_context: Optional[str] = None
    extraction_summary: Optional[str] = None
    business_case_system: Optional[str] = None
    business_case_extraction: Optional[str] = None
    cost_estimation_system: Optional[str] = None
    cost_estimation_extraction: Optional[str] = None
    transition_briefing_system: Optional[str] = None
    swot_analysis_system: Optional[str] = None


class LLMConfig(BaseModel):
    """Schema for LLM configuration (model and api_base stored, api_key passed per-request)."""
    model: Optional[str] = None  # e.g., "meta-llama-3.1-8b-instruct"
    api_key: Optional[str] = None  # Only used for connection testing, NOT stored
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
        key="idea_clustering_system",
        label="Idea Clustering System Prompt",
        description="Groups brainstormed ideas into technology/concept clusters for two-phase prioritization",
        variables=[]
    ),
    PromptInfo(
        key="consultation_system",
        label="Consultation System Prompt",
        description="Behavioral rules for the AI consultant - response format, what to avoid, conversation style",
        variables=["multi_participant_section"]
    ),
    PromptInfo(
        key="consultation_context",
        label="Consultation Context Template",
        description="Session-specific context injected at start - company info, maturity, focus project, ideas",
        variables=["company_name", "company_info_text", "maturity_section", "focus_idea", "top_ideas_text"]
    ),
    PromptInfo(
        key="extraction_summary",
        label="CRISP-DM Summary Extraction",
        description="Extracts structured Business Understanding outputs: objectives, situation, AI goals, and project plan",
        variables=[]
    ),
    PromptInfo(
        key="business_case_system",
        label="Business Case System Prompt",
        description="Guides the AI through business case development using the 5-level value framework",
        variables=["company_info_text", "focus_idea", "business_objectives", "situation_assessment", "ai_goals", "project_plan"]
    ),
    PromptInfo(
        key="business_case_extraction",
        label="Business Case Extraction",
        description="Extracts structured business case: classification, calculation, validation questions, management pitch",
        variables=[]
    ),
    PromptInfo(
        key="cost_estimation_system",
        label="Cost Estimation System Prompt",
        description="Guides the AI through project cost estimation and budgeting",
        variables=["company_info_text", "focus_idea", "business_objectives", "situation_assessment", "ai_goals", "project_plan", "potentials_summary"]
    ),
    PromptInfo(
        key="cost_estimation_extraction",
        label="Cost Estimation Extraction",
        description="Extracts structured cost estimate: complexity, initial investment, recurring costs, TCO",
        variables=[]
    ),
    PromptInfo(
        key="transition_briefing_system",
        label="Transition Briefing System Prompt",
        description="Creates technical handover document for the Technical Understanding phase",
        variables=["company_profile", "executive_summary", "business_case_summary", "cost_estimation_summary"]
    ),
    PromptInfo(
        key="swot_analysis_system",
        label="SWOT Analysis System Prompt",
        description="Creates SWOT analysis evaluating company readiness for the AI project",
        variables=["company_profile", "executive_summary", "business_case_summary", "cost_estimation_summary"]
    ),
]
