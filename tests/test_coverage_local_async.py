"""Coverage tests for macon.local_async.base — lines 80-86 (function decorator path)
and local_async/test_classes.py lines 29, 38."""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

from macon.local_async.base import with_session, with_session_transaction


@asynccontextmanager
async def _mock_session_ctx():
    """Lightweight mock that behaves like get_session()."""
    yield MagicMock(name="mock_session")


@asynccontextmanager
async def _mock_session_with_begin_ctx():
    """Mock session whose .begin() is also an async context manager."""
    session = MagicMock(name="mock_session")
    session.begin = MagicMock(return_value=_noop_ctx())
    yield session


@asynccontextmanager
async def _noop_ctx():
    yield


class TestWithSessionFunctionPath:
    async def test_with_session_decorates_standalone_function(self):
        @with_session
        async def standalone_func(session, value):
            return f"got {value} with session={session is not None}"

        with patch("macon.local_async.base.get_session", _mock_session_ctx):
            result = await standalone_func("test_value")
            assert "got test_value" in result
            assert "session=True" in result


class TestWithSessionTransactionFunctionPath:
    async def test_with_session_transaction_decorates_standalone_function(self):
        @with_session_transaction
        async def standalone_func(session, value):
            return f"transacted {value}"

        with patch("macon.local_async.base.get_session", _mock_session_with_begin_ctx):
            result = await standalone_func("hello")
            assert result == "transacted hello"


class TestTableLocalOperationsReadSlice:
    async def test_read_slice_delegates(self, init_test_db):
        from macon.local_async import test_table
        from macon.db.test_classes import TestTable
        from macon.db.session import _engine, get_session
        from macon.db.base import Base

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with get_session() as session:
            row = TestTable(name="slice_test", path="test/file.hdf5", n_objects=10)
            session.add(row)

        with patch("macon.db_oper.test_classes.tables_io") as mock_tio:
            mock_tio.read.return_value = {"col1": [1, 2, 3]}
            with patch("macon.db_oper.test_classes.global_config") as mock_config:
                mock_config.storage.archive = "/tmp/archive"
                result = await test_table.read_slice(1, slice(0, 3))

        assert result == {"col1": [1, 2, 3]}


class TestTableSyncOperationsReadSlice:
    def test_sync_read_slice(self, init_test_db):
        import asyncio
        from macon.local_async import test_table as async_test_table
        from macon.local_sync.test_classes import TestTableSyncOperations
        from macon.db.test_classes import TestTable
        from macon.db.session import _engine, get_session
        from macon.db.base import Base

        async def setup():
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with get_session() as session:
                row = TestTable(name="sync_slice_test", path="test/file.hdf5", n_objects=5)
                session.add(row)

        asyncio.run(setup())

        sync_ops = TestTableSyncOperations(async_test_table)

        with patch("macon.db_oper.test_classes.tables_io") as mock_tio:
            mock_tio.read.return_value = {"data": [10, 20]}
            with patch("macon.db_oper.test_classes.global_config") as mock_config:
                mock_config.storage.archive = "/tmp/archive"
                result = sync_ops.read_slice(1, slice(0, 2))

        assert result == {"data": [10, 20]}


class TestLookupByIdOrNameNeedObjectFalse:
    async def test_returns_none_when_need_object_false(self, init_test_db):
        from macon.local_async import test_named
        from macon.db.test_classes import TestNamed
        from macon.db.session import _engine, get_session
        from macon.db.base import Base

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with get_session() as session:
            session.add(TestNamed(name="lookup_test"))

        row_id, result = await test_named.lookup_by_id_or_name(1, None, need_object=False)
        assert row_id == 1
        assert result is None
