"""
Embedding Service — Generates vector embeddings via Ollama or OpenAI.
"""

import logging
from typing import List

import httpx

from app.config import EmbeddingProvider, settings

logger = logging.getLogger(__name__)


async def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for a single text string."""
    if settings.embedding_provider == EmbeddingProvider.OLLAMA:
        return await _ollama_embed(text)
    else:
        return await _openai_embed(text)


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    if settings.embedding_provider == EmbeddingProvider.OLLAMA:
        # Ollama doesn't have native batch — process sequentially
        results = []
        for text in texts:
            emb = await _ollama_embed(text)
            results.append(emb)
        return results
    else:
        return await _openai_embed_batch(texts)


async def _ollama_embed(text: str) -> List[float]:
    """Get embedding from Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={
                "model": settings.ollama_embed_model,
                "prompt": text,
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def _openai_embed(text: str) -> List[float]:
    """Get embedding from OpenAI."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embed_model,
        input=text,
    )
    return response.data[0].embedding


async def _openai_embed_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a batch from OpenAI."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embed_model,
        input=texts,
    )
    return [item.embedding for item in response.data]
