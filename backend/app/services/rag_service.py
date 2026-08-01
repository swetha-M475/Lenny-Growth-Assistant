from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import List, Optional
import yaml
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embeddings import generate_embedding
from app.models import TranscriptChunk

logger = logging.getLogger(__name__)

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "transcripts"


@dataclass
class RetrievedChunk:
    """A retrieved transcript chunk with relevance score."""
    guest: str
    episode_title: str
    chunk_text: str
    similarity: float
    metadata: dict


async def retrieve_from_files(query: str, top_k: int = 5) -> List[RetrievedChunk]:
    """Fallback RAG: keyword search directly over files when PostgreSQL is offline."""
    logger.info(f"Database offline: performing keyword search over local transcripts directory...")
    episodes_dir = TRANSCRIPTS_DIR / "episodes"
    if not episodes_dir.exists():
        logger.warning(f"Transcripts directory not found at: {episodes_dir}")
        return []

    # Import ingestion parser helpers
    from app.ingestion.ingest import parse_transcript, chunk_text

    keywords = [w.lower() for w in re.findall(r"\b\w{4,}\b", query)]
    if not keywords:
        keywords = [w.lower() for w in query.split() if w.strip()]

    scored_chunks = []
    episode_dirs = list(episodes_dir.iterdir())

    for episode_dir in episode_dirs:
        transcript_file = episode_dir / "transcript.md"
        if not transcript_file.exists():
            continue

        guest_name = episode_dir.name
        metadata, content = parse_transcript(transcript_file)
        if not content:
            continue

        title = metadata.get("title", guest_name)
        chunks = chunk_text(content)

        for chunk_text_content in chunks:
            chunk_lower = chunk_text_content.lower()
            # Calculate match frequency
            score = sum(chunk_lower.count(kw) for kw in keywords)

            # Give bonus if guest's name is mentioned in query
            if guest_name.replace("-", " ").lower() in query.lower():
                score += 5

            if score > 0:
                scored_chunks.append((
                    score,
                    RetrievedChunk(
                        guest=guest_name,
                        episode_title=title,
                        chunk_text=chunk_text_content,
                        similarity=min(0.5 + (score / 20.0), 0.99),
                        metadata={
                            "guest": metadata.get("guest", guest_name),
                            "publish_date": str(metadata.get("publish_date", "")),
                            "youtube_url": metadata.get("youtube_url", ""),
                            "duration": metadata.get("duration", ""),
                        }
                    )
                ))

    # Sort by keyword matching score descending
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:top_k]]


async def retrieve_relevant_chunks(
    query: str,
    db: AsyncSession,
    top_k: int = 5,
    similarity_threshold: float = 0.3,
) -> List[RetrievedChunk]:
    """
    Embed the query and find the most relevant transcript chunks via cosine similarity.
    If database connection is offline (db is None), fall back to direct file search.
    """
    if db is None:
        return await retrieve_from_files(query, top_k)

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
