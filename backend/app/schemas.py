"""
Pydantic Schemas — Request/Response models for the API.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Sessions ───────────────────────────────────────────

class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class SessionUpdate(BaseModel):
    title: str


class SessionOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class SessionDetailOut(SessionOut):
    messages: List["MessageOut"] = []
    artifacts: List["ArtifactOut"] = []


# ─── Messages ───────────────────────────────────────────

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    skill_hint: Optional[str] = None  # "auto", "qa", "ship30for30", "artifact"


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    skill_used: Optional[str] = None
    created_at: datetime
    artifacts: List["ArtifactOut"] = []

    class Config:
        from_attributes = True


# ─── Artifacts ──────────────────────────────────────────

class ArtifactOut(BaseModel):
    id: UUID
    artifact_type: str
    title: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Config ─────────────────────────────────────────────

class LLMConfigOut(BaseModel):
    llm_provider: str
    model_name: str
    embedding_provider: str
    embedding_model: str


class LLMConfigUpdate(BaseModel):
    llm_provider: str  # "ollama", "anthropic", "openai"
    model_name: Optional[str] = None
    api_key: Optional[str] = None


# ─── Chat Streaming ────────────────────────────────────

class ChatStreamEvent(BaseModel):
    event: str  # "token", "done", "error", "artifact", "skill"
    data: str = ""
    metadata: Optional[dict] = None


# Resolve forward references
SessionDetailOut.model_rebuild()
MessageOut.model_rebuild()
