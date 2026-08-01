"""
RAG Service — Retrieval-Augmented Generation using pgvector cosine similarity.
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embeddings import generate_embedding
from app.models import TranscriptChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved transcript chunk with relevance score."""
    guest: str
    episode_title: str
    chunk_text: str
    similarity: float
    metadata: dict


async def retrieve_relevant_chunks(
    query: str,
    db: AsyncSession,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
) -> List[RetrievedChunk]:
    """
    Embed the query and find the most relevant transcript chunks via cosine similarity.
    """
    try:
        query_embedding = await generate_embedding(query)
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return []

    # pgvector cosine distance: smaller = more similar
    # Use <=> operator for cosine distance
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text(f"""
        SELECT 
            episode_guest,
            episode_title,
            chunk_text,
            metadata,
            1 - (embedding <=> :embedding::vector) as similarity
        FROM transcript_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {"embedding": embedding_str, "top_k": top_k},
    )

    chunks = []
    for row in result:
        sim = float(row.similarity) if row.similarity else 0.0
        if sim >= similarity_threshold:
            chunks.append(
                RetrievedChunk(
                    guest=row.episode_guest,
                    episode_title=row.episode_title,
                    chunk_text=row.chunk_text,
                    similarity=sim,
                    metadata=row.metadata or {},
                )
            )

    logger.info(f"Retrieved {len(chunks)} relevant chunks for query (top similarity: {chunks[0].similarity:.3f})" if chunks else "No relevant chunks found")
    return chunks


def format_context(chunks: List[RetrievedChunk]) -> str:
    """Format retrieved chunks into a structured context string for the LLM."""
    if not chunks:
        return "No relevant transcript content found for this query."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        guest = chunk.metadata.get("guest", chunk.guest)
        context_parts.append(
            f"--- Source {i} (from episode with {guest}: \"{chunk.episode_title}\") ---\n"
            f"{chunk.chunk_text}\n"
        )

    return "\n".join(context_parts)
