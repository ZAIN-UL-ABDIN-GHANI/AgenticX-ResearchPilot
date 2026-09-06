"""
Database connection and session management.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Build engine kwargs based on database type
engine_kwargs = {
    "echo": settings.database_echo,
}

# Only apply pool parameters for PostgreSQL
if "postgresql" in settings.database_url:
    engine_kwargs.update({
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,  # Verify connections before use
    })
else:
    # For SQLite (testing), use StaticPool
    from sqlalchemy.pool import StaticPool
    engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    })

# Create async engine
engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

# Session factory
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Usage:
        async def my_endpoint(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """Get a new database session."""
    async with async_session_maker() as session:
        return session
