from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import config as global_config

# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str | None = None, **engine_kwargs: Any) -> None:
    """
    Initialize the database engine and session factory.

    Parameters
    ----------
    database_url
        Database connection string (e.g., 'sqlite+aiosqlite:///./test.db')
    **engine_kwargs
        Additional arguments to pass to create_async_engine

    Examples
    --------
    >>> init_db("sqlite+aiosqlite:///./test.db", echo=True)
    >>> init_db("postgresql+asyncpg://user:pass@localhost/dbname")
    """
    global _engine, _async_session_factory  # pylint: disable=global-statement

    if database_url is None:
        database_url = global_config.db.url

    _engine = create_async_engine(database_url, echo=engine_kwargs.pop("echo", False), **engine_kwargs)

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """
    Get an async database session.

    Yields
    ------
        An async SQLAlchemy session

    Raises
    ------
    RuntimeError
        If database has not been initialized

    Examples
    --------
    >>> async with get_session() as session:
    ...     result = await session.execute(select(User))
    ...     users = result.scalars().all()
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """
    Close the database engine.

    Notes
    -----
    This should be called during application shutdown to properly
    dispose of database connections.

    Examples
    --------
    >>> await close_db()
    """
    global _engine, _async_session_factory  # pylint: disable=global-statement
    if _engine:
        await _engine.dispose()
        _engine = None
    _async_session_factory = None  # Also clear the session factory
