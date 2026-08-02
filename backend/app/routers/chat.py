"""
Chat Router — SSE-streaming chat endpoint with agentic skill routing.
"""

from datetime import datetime, timezone
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

from app.database import get_db, mock_db
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
    """
    if db is None:
        session = mock_db["sessions"].get(str(session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Save user message
        user_message_id = uuid.uuid4()
        user_message = {
            "id": user_message_id,
            "session_id": session_id,
            "role": "user",
            "content": body.content,
            "skill_used": None,
            "created_at": datetime.now(timezone.utc),
            "artifacts": []
        }
        mock_db["messages"][str(session_id)].append(user_message)

        # Auto-title
        if session["title"] == "New Chat" and len(mock_db["messages"][str(session_id)]) <= 1:
            title = body.content[:80].strip()
            if len(body.content) > 80:
                title += "..."
            session["title"] = title

        # Build history
        history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in mock_db["messages"][str(session_id)]
            if str(msg["id"]) != str(user_message_id)
        ]

    else:
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

        # Create a dedicated local session for the duration of the event stream
        from app.database import db_initialized, async_session_factory
        local_db = async_session_factory() if db_initialized else None

        try:
            # Route to appropriate skill using local_db session
            skill_type, token_stream = await agent_router.route(
                message=body.content,
                conversation_history=history,
                db=local_db,
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
            logger.warning(f"LLM provider failed: {e}. Switching to simulated fallback responses...")
            
            # Stream simulated notice banner first
            yield {
                "event": "token",
                "data": json.dumps({"token": "*(Notice: The configured LLM engine is offline. Switching to simulated offline response grounded in transcripts...)*\n\n"}),
            }
            
            try:
                # Classify intent for fallback
                from app.services.llm_service import MockLLM
                
                skill_type = agent_router.classify_intent(body.content, body.skill_hint)
                
                # Send skill badge update
                yield {
                    "event": "skill",
                    "data": json.dumps({"skill": skill_type.value}),
                }
                
                # Retrieve RAG context using files fallback (passing None as db)
                from app.services.rag_service import retrieve_relevant_chunks, format_context
                rag_chunks = await retrieve_relevant_chunks(body.content, None)
                context = format_context(rag_chunks)
                
                # Load prompt matching the skill
                from app.skills.qa_skill import get_qa_system_prompt
                from app.skills.ship30_skill import get_ship30_system_prompt
                from app.skills.artifact_skill import get_artifact_system_prompt
                
                if skill_type.value == "ship30for30":
                    system_prompt = get_ship30_system_prompt(context)
                elif skill_type.value == "artifact":
                    system_prompt = get_artifact_system_prompt(context)
                else:
                    system_prompt = get_qa_system_prompt(context)
                
                mock_llm = MockLLM()
                
                # Build messages history list from history + user prompt
                messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
                messages.append({"role": "user", "content": body.content})

                token_stream = mock_llm.generate_stream(messages, system_prompt)
                
                async for token in token_stream:
                    full_response += token
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": token}),
                    }
            except Exception as mock_err:
                logger.error(f"Fallback generation failed: {mock_err}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": f"LLM offline and fallback failed: {str(mock_err)}"}),
                }
                return

        # Save assistant message using local_db session
        try:
            assistant_msg_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            
            if local_db is None:
                assistant_message = {
                    "id": assistant_msg_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "content": full_response,
                    "skill_used": skill_type.value if skill_type else None,
                    "created_at": now,
                    "artifacts": []
                }
                mock_db["messages"][str(session_id)].append(assistant_message)

                # Extract and save artifacts
                artifacts = extract_artifacts(full_response, assistant_msg_id, session_id)
                for artifact in artifacts:
                    # Convert to dict for mock storage
                    art_dict = {
                        "id": artifact.id,
                        "message_id": assistant_msg_id,
                        "session_id": session_id,
                        "artifact_type": artifact.artifact_type,
                        "title": artifact.title,
                        "content": artifact.content,
                        "created_at": now
                    }
                    mock_db["artifacts"][str(session_id)].append(art_dict)
                    assistant_message["artifacts"].append(art_dict)

                    yield {
                        "event": "artifact",
                        "data": json.dumps({
                            "id": str(artifact.id),
                            "type": artifact.artifact_type,
                            "title": artifact.title,
                            "content": artifact.content,
                        }),
                    }
                
                # Update session timestamp
                session["updated_at"] = now

            else:
                assistant_message = Message(
                    id=assistant_msg_id,
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    skill_used=skill_type.value if skill_type else None,
                )
                local_db.add(assistant_message)
                await local_db.flush()

                # Extract and save artifacts if present
                artifacts = extract_artifacts(full_response, assistant_message.id, session_id)
                for artifact in artifacts:
                    local_db.add(artifact)
                    await local_db.flush()

                    yield {
                        "event": "artifact",
                        "data": json.dumps({
                            "id": str(artifact.id),
                            "type": artifact.artifact_type,
                            "title": artifact.title,
                            "content": artifact.content,
                        }),
                    }

                await local_db.commit()

            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": str(assistant_msg_id),
                    "skill_used": skill_type.value if skill_type else None,
                    "session_title": session["title"] if local_db is None else session.title,
                }),
            }

        except Exception as e:
            logger.error(f"Error saving response: {e}", exc_info=True)
            if local_db is not None:
                await local_db.rollback()
            yield {
                "event": "error",
                "data": json.dumps({"error": "Failed to save response"}),
            }
        finally:
            if local_db is not None:
                await local_db.close()

    return EventSourceResponse(event_stream())


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session."""
    if db is None:
        return mock_db["messages"].get(str(session_id), [])

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
    if db is None:
        for session_artifacts in mock_db["artifacts"].values():
            for art in session_artifacts:
                if str(art["id"]) == str(artifact_id):
                    return ArtifactOut(
                        id=art["id"],
                        artifact_type=art["artifact_type"],
                        title=art["title"],
                        content=art["content"],
                        created_at=art["created_at"]
                    )
        raise HTTPException(status_code=404, detail="Artifact not found")

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
