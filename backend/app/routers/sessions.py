"""
Session Router — CRUD endpoints for chat sessions.
"""

from datetime import datetime, timezone
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, mock_db
from app.models import Message, Session, User, Artifact
from app.schemas import SessionCreate, SessionDetailOut, SessionOut, SessionUpdate

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Default user ID (simplified — no auth for this demo)
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def ensure_default_user(db: AsyncSession):
    """Create the default user if it doesn't exist."""
    if db is None:
        if str(DEFAULT_USER_ID) not in mock_db["users"]:
            mock_db["users"][str(DEFAULT_USER_ID)] = {
                "id": DEFAULT_USER_ID,
                "created_at": datetime.now(timezone.utc)
            }
        return mock_db["users"][str(DEFAULT_USER_ID)]

    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=DEFAULT_USER_ID)
        db.add(user)
        await db.flush()
    return user


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate = SessionCreate(),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    await ensure_default_user(db)
    
    if db is None:
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        session = {
            "id": session_id,
            "user_id": DEFAULT_USER_ID,
            "title": body.title or "New Chat",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
        mock_db["sessions"][str(session_id)] = session
        mock_db["messages"][str(session_id)] = []
        mock_db["artifacts"][str(session_id)] = []
        return SessionOut(
            id=session["id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            message_count=0,
        )

    session = Session(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        title=body.title or "New Chat",
    )
    db.add(session)
    await db.flush()
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.get("", response_model=List[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all chat sessions, newest first."""
    if db is None:
        sessions = sorted(
            mock_db["sessions"].values(),
            key=lambda x: x["updated_at"],
            reverse=True
        )
        return [
            SessionOut(
                id=s["id"],
                title=s["title"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
                message_count=len(mock_db["messages"].get(str(s["id"]), [])),
            )
            for s in sessions
        ]

    result = await db.execute(
        select(
            Session,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.session_id == Session.id)
        .where(Session.user_id == DEFAULT_USER_ID)
        .group_by(Session.id)
        .order_by(Session.updated_at.desc())
    )
    sessions = []
    for row in result:
        s = row[0]
        sessions.append(
            SessionOut(
                id=s.id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=row[1],
            )
        )
    return sessions


@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a session with all its messages and artifacts."""
    if db is None:
        session = mock_db["sessions"].get(str(session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = mock_db["messages"].get(str(session_id), [])
        artifacts = mock_db["artifacts"].get(str(session_id), [])
        return SessionDetailOut(
            id=session["id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            message_count=len(messages),
            messages=messages,
            artifacts=artifacts,
        )

    result = await db.execute(
        select(Session)
        .options(
            selectinload(Session.messages).selectinload(Message.artifacts),
            selectinload(Session.artifacts),
        )
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetailOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        messages=session.messages,
        artifacts=session.artifacts,
    )


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update session title."""
    if db is None:
        session = mock_db["sessions"].get(str(session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session["title"] = body.title
        session["updated_at"] = datetime.now(timezone.utc)
        return SessionOut(
            id=session["id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            message_count=len(mock_db["messages"].get(str(session_id), [])),
        )

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = body.title
    await db.flush()
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a session and all its messages."""
    if db is None:
        if str(session_id) not in mock_db["sessions"]:
            raise HTTPException(status_code=404, detail="Session not found")
        mock_db["sessions"].pop(str(session_id))
        mock_db["messages"].pop(str(session_id), None)
        mock_db["artifacts"].pop(str(session_id), None)
        return

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
