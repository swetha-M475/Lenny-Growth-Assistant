"""
Chat Router — SSE-streaming chat endpoint with agentic skill routing.
"""

import json
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import Artifact, Message, Session
from app.schemas import ArtifactOut, MessageCreate, MessageOut
from app.services.agent_router import agent_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/{session_id}")
async def send_message(
    session_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and receive a streamed response via Server-Sent Events (SSE).
    
    Events:
    - skill: {skill_type} — Which skill is handling the request
    - token: {text} — Incremental text tokens
    - artifact: {json} — Generated artifact metadata
    - done: {json} — Final message metadata
    - error: {text} — Error message
    """
    # Verify session exists
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.messages))
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_message = Message(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db.add(user_message)
    await db.flush()

    # Auto-title: use first user message as session title
    if session.title == "New Chat" and len(session.messages) <= 1:
        title = body.content[:80].strip()
        if len(body.content) > 80:
            title += "..."
        session.title = title
        await db.flush()

    # Build conversation history
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in session.messages
        if msg.id != user_message.id
    ]

    async def event_stream():
        full_response = ""
        skill_type = None

        try:
            # Route to appropriate skill
            skill_type, token_stream = await agent_router.route(
                message=body.content,
                conversation_history=history,
                db=db,
                skill_hint=body.skill_hint,
            )

            # Send skill type event
            yield {
                "event": "skill",
                "data": json.dumps({"skill": skill_type.value}),
            }

            # Stream tokens
            async for token in token_stream:
                full_response += token
                yield {
                    "event": "token",
                    "data": json.dumps({"token": token}),
                }

        except Exception as e:
            logger.error(f"Error during streaming: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
            return

        # Save assistant message
        try:
            assistant_message = Message(
                id=uuid.uuid4(),
                session_id=session_id,
                role="assistant",
                content=full_response,
                skill_used=skill_type.value if skill_type else None,
            )
            db.add(assistant_message)
            await db.flush()

            # Extract and save artifacts if present
            artifacts = extract_artifacts(full_response, assistant_message.id, session_id)
            for artifact in artifacts:
                db.add(artifact)
                await db.flush()

                yield {
                    "event": "artifact",
                    "data": json.dumps({
                        "id": str(artifact.id),
                        "type": artifact.artifact_type,
                        "title": artifact.title,
                        "content": artifact.content,
                    }),
                }

            await db.commit()

            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": str(assistant_message.id),
                    "skill_used": skill_type.value if skill_type else None,
                    "session_title": session.title,
                }),
            }

        except Exception as e:
            logger.error(f"Error saving response: {e}", exc_info=True)
            await db.rollback()
            yield {
                "event": "error",
                "data": json.dumps({"error": "Failed to save response"}),
            }

    return EventSourceResponse(event_stream())


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session."""
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.artifacts))
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [MessageOut.model_validate(m) for m in messages]


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific artifact by ID."""
    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactOut.model_validate(artifact)


def extract_artifacts(
    content: str, message_id: uuid.UUID, session_id: uuid.UUID
) -> list:
    """
    Extract <artifact> tags from the response and create Artifact model instances.
    
    Format: <artifact type="html|markdown" title="Title">content</artifact>
    """
    pattern = r'<artifact\s+type="(html|markdown)"\s+title="([^"]*)">(.*?)</artifact>'
    matches = re.findall(pattern, content, re.DOTALL)

    artifacts = []
    for artifact_type, title, artifact_content in matches:
        artifact = Artifact(
            id=uuid.uuid4(),
            message_id=message_id,
            session_id=session_id,
            artifact_type=artifact_type.strip(),
            title=title.strip(),
            content=artifact_content.strip(),
        )
        artifacts.append(artifact)

    return artifacts
