"""Alembic environment configuration for ResearchPilot AI."""

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import models to support auto-generate
from app.db.base import Base
from app.db.models import ResearchRun, Source, ToolCall, Claim, ClaimSource
from app.core.config import settings

# Get Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for auto-generate
target_metadata = Base.metadata


def _sync_database_url() -> str:
    """Alembic runs migrations synchronously, but the app's DATABASE_URL
    uses an async driver (asyncpg/aiosqlite) so the app itself can use
    SQLAlchemy's async engine. Swap in the matching sync driver here so
    `alembic upgrade` doesn't try to run async I/O outside an event loop.
    """
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create engine configuration
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
