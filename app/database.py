import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def _add_missing_columns(connection):
    """Add columns that exist in models but not yet in the database (lightweight migration)."""
    insp = inspect(connection)
    migrations = [
        ("vendors", "icon_class", "VARCHAR(100)"),
        ("vendors", "icon_color", "VARCHAR(20)"),
    ]
    for table, column, col_type in migrations:
        if table in insp.get_table_names():
            existing = [c["name"] for c in insp.get_columns(table)]
            if column not in existing:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                logger.info("Added column %s.%s", table, column)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
