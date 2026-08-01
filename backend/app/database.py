"""
Database setup — Async SQLAlchemy engine for PostgreSQL with pgvector.
"""

from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


# Global state to indicate if real database is ready
db_initialized = False

# In-memory storage fallback when database is not running
mock_db = {
    "users": {},
    "sessions": {},
    "messages": {},
    "artifacts": {},
    "transcript_chunks": []
}


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    if not db_initialized:
        # Yield None if not initialized — routes will handle mock fallback
        yield None
        return

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables (used in development; production uses Alembic)."""
    global db_initialized
    try:
        async with engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            await conn.run_sync(Base.metadata.create_all)
        db_initialized = True
    except Exception as e:
        db_initialized = False
        raise e


async def close_db():
    """Dispose of the database engine."""
    await engine.dispose()
