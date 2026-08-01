"""
Configuration & Settings — The Lenny Growth Assistant

Pydantic Settings for environment-based config with LLM provider toggling.
"""

from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class EmbeddingProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lenny_assistant"

    # --- LLM Provider ---
    llm_provider: LLMProvider = LLMProvider.OLLAMA

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # --- Anthropic ---
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    # --- OpenAI ---
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # --- Embeddings ---
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OLLAMA
    ollama_embed_model: str = "nomic-embed-text"
    openai_embed_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 768

    # --- App ---
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:8000"


settings = Settings()
