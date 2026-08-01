"""
Config Router — LLM configuration and health check endpoints.
"""

import logging

from fastapi import APIRouter

from app.config import settings
from app.schemas import LLMConfigOut, LLMConfigUpdate
from app.services.llm_service import llm_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=LLMConfigOut)
async def get_config():
    """Get current LLM configuration."""
    return LLMConfigOut(
        llm_provider=llm_manager.provider.value,
        model_name=llm_manager.model_name,
        embedding_provider=settings.embedding_provider.value,
        embedding_model=(
            settings.ollama_embed_model
            if settings.embedding_provider.value == "ollama"
            else settings.openai_embed_model
        ),
    )


@router.put("", response_model=LLMConfigOut)
async def update_config(body: LLMConfigUpdate):
    """Switch the LLM provider at runtime."""
    try:
        llm_manager.switch_provider(
            provider=body.llm_provider,
            model=body.model_name,
            api_key=body.api_key,
        )
        return LLMConfigOut(
            llm_provider=llm_manager.provider.value,
            model_name=llm_manager.model_name,
            embedding_provider=settings.embedding_provider.value,
            embedding_model=(
                settings.ollama_embed_model
                if settings.embedding_provider.value == "ollama"
                else settings.openai_embed_model
            ),
        )
    except Exception as e:
        logger.error(f"Failed to switch LLM: {e}")
        raise


@router.get("/health")
async def health_check():
    """Check connectivity to the current LLM provider."""
    try:
        llm = llm_manager.get_llm()
        is_healthy = await llm.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "provider": llm_manager.provider.value,
            "model": llm_manager.model_name,
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": llm_manager.provider.value,
            "error": str(e),
        }
