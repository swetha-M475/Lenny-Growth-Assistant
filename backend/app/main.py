"""
The Lenny Growth Assistant — FastAPI Application Entry Point

A full-stack AI-powered conversational web application that ingests Lenny's Podcast
transcripts, enables RAG-powered Q&A, generates Ship30for30-style essays, and renders
HTML/Markdown artifacts inline.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_db, init_db
from app.routers import chat, config, sessions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB on startup, cleanup on shutdown."""
    logger.info("🚀 Starting The Lenny Growth Assistant...")
    logger.info(f"   LLM Provider: {settings.llm_provider.value}")
    logger.info(f"   Database: {settings.database_url[:50]}...")

    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.info("   Make sure PostgreSQL is running and DATABASE_URL is correct.")

    yield

    logger.info("🛑 Shutting down...")
    await close_db()


app = FastAPI(
    title="The Lenny Growth Assistant",
    description="AI-powered chatbot built on Lenny's Podcast transcripts",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(config.router)


@app.get("/api/health")
async def root_health():
    """Root health check endpoint."""
    return {
        "status": "running",
        "app": "The Lenny Growth Assistant",
        "version": "1.0.0",
    }


# Ingestion endpoint (admin)
@app.post("/api/admin/ingest")
async def trigger_ingestion():
    """Trigger transcript ingestion (admin endpoint)."""
    from app.ingestion.ingest import ingest_transcripts
    try:
        count = await ingest_transcripts()
        return {"status": "success", "chunks_ingested": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Serve frontend static files (must be mounted last)
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
