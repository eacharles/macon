"""Shared test fixtures for macon tests."""

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from macon.db.base import Base
from macon.db import init_db, close_db
from macon.db.test_classes import TestNamed
from macon.db_oper.test_classes import (
    test_named as test_named_ops_singleton,
    test_ref as test_ref_ops_singleton,
    test_list_pair as test_list_pair_ops_singleton,
)

DB_URL = "sqlite+aiosqlite://"


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite async engine."""
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Provide a transactional database session for each test.

    All db_funcs operations only flush (never commit), so the session
    auto-commits on successful context exit via get_session() in production.
    Here we just let the session commit on close.
    """
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def test_named_ops():
    """Return a TestNamedOperations instance."""
    return test_named_ops_singleton


@pytest.fixture
def test_ref_ops():
    """Return a TestRefOperations instance."""
    return test_ref_ops_singleton


@pytest.fixture
def test_list_pair_ops():
    """Return a TestListPairOperations instance."""
    return test_list_pair_ops_singleton


@pytest.fixture
async def seed_named_rows(db_session):
    """Insert test rows into TestNamed table and return them."""
    for name in ["alpha", "beta", "gamma", "delta", "epsilon"]:
        row = TestNamed(name=name)
        db_session.add(row)
    await db_session.commit()
    result = await db_session.execute(sqlalchemy.select(TestNamed))
    rows = list(result.scalars().all())
    return rows


@pytest.fixture
async def init_test_db():
    """Initialize the global DB session factory for LocalOperations tests."""
    init_db(DB_URL)
    from macon.db.session import _engine

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()


@pytest.fixture
async def local_db_session(init_test_db):
    """Provide a clean DB state for local operations tests."""
    yield
    from macon.db.session import _engine

    if _engine:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
