"""
Transcript Ingestion — Loads, chunks, and embeds Lenny's Podcast transcripts into pgvector.
"""

import logging
import os
import re
import uuid
from pathlib import Path
from typing import List, Tuple

import yaml
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.ingestion.embeddings import generate_embedding
from app.models import TranscriptChunk

logger = logging.getLogger(__name__)

TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "transcripts"


def parse_transcript(filepath: Path) -> Tuple[dict, str]:
    """Parse a transcript.md file into (metadata, content)."""
    raw = filepath.read_text(encoding="utf-8", errors="replace")

    # Split YAML frontmatter
    parts = raw.split("---", 2)
    if len(parts) >= 3:
        try:
            metadata = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            metadata = {}
        content = parts[2].strip()
    else:
        metadata = {}
        content = raw.strip()

    return metadata, content


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks by character count.
    Uses paragraph boundaries when possible for natural breaks.
    """
    if not text:
        return []

    # Split on double newlines (paragraphs) first
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += ("\n\n" + para) if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Keep overlap from the end of the current chunk
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                # Single paragraph longer than chunk_size — force split
                while len(para) > chunk_size:
                    chunks.append(para[:chunk_size].strip())
                    para = para[chunk_size - overlap:]
                current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def ingest_transcripts(db: AsyncSession = None, force: bool = False):
    """
    Main ingestion pipeline:
    1. Scan transcripts directory
    2. Parse each transcript
    3. Chunk the text
    4. Generate embeddings
    5. Store in DB
    """
    episodes_dir = TRANSCRIPTS_DIR / "episodes"

    if not episodes_dir.exists():
        logger.error(f"Transcripts directory not found: {episodes_dir}")
        logger.info("Please clone the transcripts repo first:")
        logger.info("  git clone https://github.com/ChatPRD/lennys-podcast-transcripts.git backend/data/transcripts")
        return 0

    own_session = db is None
    if own_session:
        session = async_session_factory()
    else:
        session = db

    try:
        # Check if already ingested
        if not force:
            result = await session.execute(
                text("SELECT COUNT(*) FROM transcript_chunks")
            )
            count = result.scalar()
            if count and count > 0:
                logger.info(f"Database already has {count} transcript chunks. Use force=True to re-ingest.")
                return count

        total_chunks = 0
        episode_dirs = sorted(episodes_dir.iterdir())

        for episode_dir in episode_dirs:
            transcript_file = episode_dir / "transcript.md"
            if not transcript_file.exists():
                continue

            guest_name = episode_dir.name
            metadata, content = parse_transcript(transcript_file)

            if not content:
                logger.warning(f"Empty transcript for {guest_name}, skipping")
                continue

            episode_title = metadata.get("title", guest_name)
            chunks = chunk_text(content)

            logger.info(f"Processing {guest_name}: {len(chunks)} chunks")

            for i, chunk_text_content in enumerate(chunks):
                try:
                    embedding = await generate_embedding(chunk_text_content)
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {i} for {guest_name}: {e}")
                    embedding = None

                chunk = TranscriptChunk(
                    id=uuid.uuid4(),
                    episode_guest=guest_name,
                    episode_title=episode_title,
                    chunk_text=chunk_text_content,
                    chunk_index=i,
                    embedding=embedding,
                    metadata_={
                        "guest": metadata.get("guest", guest_name),
                        "publish_date": str(metadata.get("publish_date", "")),
                        "youtube_url": metadata.get("youtube_url", ""),
                        "duration": metadata.get("duration", ""),
                    },
                )
                session.add(chunk)
                total_chunks += 1

            # Commit per episode to avoid huge transactions
            await session.commit()

        logger.info(f"Ingestion complete: {total_chunks} chunks from {len(episode_dirs)} episodes")
        return total_chunks

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        await session.rollback()
        raise
    finally:
        if own_session:
            await session.close()
