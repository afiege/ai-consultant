from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./database/ai_consultant.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # File Upload
    upload_dir: str = "./uploads"
    max_file_size: int = 10485760  # 10MB

    # LLM Configuration (LiteLLM - OpenAI API compatible)
    # Model format: provider/model (e.g., "mistral/mistral-small-latest", "openai/gpt-4")
    # For OpenAI-compatible endpoints, use "openai/model-name" with custom api_base
    llm_model: str = "mistral/mistral-small-latest"

    # Optional: Custom API base URL for OpenAI-compatible endpoints
    # Examples:
    #   http://localhost:11434/v1 (Ollama)
    #   http://localhost:1234/v1 (LM Studio)
    #   https://your-azure-endpoint.openai.azure.com (Azure OpenAI)
    llm_api_base: str = ""

    # API Keys - LiteLLM uses standard env vars: MISTRAL_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    mistral_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
