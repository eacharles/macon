"""Tests for macon.local_sync — SyncOperations wrapper using mocked async layer."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from macon.local_async.base import LocalOperations
from macon.local_sync.base import SyncOperations, sync_wrapper


class MockResponse(BaseModel):
    id_: int
    name: str


class MockCreate(BaseModel):
    name: str


@pytest.fixture
def mock_async_ops():
    """Create a mocked LocalOperations instance."""
    mock = MagicMock(spec=LocalOperations)
    return mock


@pytest.fixture
def sync_ops(mock_async_ops):
    """Create SyncOperations with mocked async ops."""
    return SyncOperations(mock_async_ops)


class TestSyncWrapper:
    def test_calls_asyncio_run(self):
        """sync_wrapper should run the coroutine via asyncio.run."""

        class FakeAsync:
            async def do_thing(self, x: int) -> int:
                return x * 2

        class FakeSync:
            def __init__(self):
                self.async_ops = FakeAsync()

            @sync_wrapper(FakeAsync.do_thing)
            def do_thing(self, *args, **kwargs):
                return self.async_ops.do_thing(*args, **kwargs)

        s = FakeSync()
        result = s.do_thing(21)
        assert result == 42

    def test_preserves_docstring(self):
        class FakeAsync:
            async def documented(self) -> None:
                """This is the docstring."""

        class FakeSync:
            def __init__(self):
                self.async_ops = FakeAsync()

            @sync_wrapper(FakeAsync.documented)
            def documented(self, *args, **kwargs):
                return self.async_ops.documented(*args, **kwargs)

        assert FakeSync.documented.__doc__ == "This is the docstring."


class TestSyncOperationsCreate:
    def test_create_row(self, sync_ops, mock_async_ops):
        mock_async_ops.create_row = AsyncMock(return_value=MockResponse(id_=1, name="created"))
        result = sync_ops.create_row(name="created")
        assert result.name == "created"
        mock_async_ops.create_row.assert_called_once_with(name="created")

    def test_create_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.create_rows = AsyncMock(
            return_value=[MockResponse(id_=1, name="a"), MockResponse(id_=2, name="b")]
        )
        result = sync_ops.create_rows([{"name": "a"}, {"name": "b"}])
        assert len(result) == 2

    def test_create_rows_batched(self, sync_ops, mock_async_ops):
        mock_async_ops.create_rows_batched = AsyncMock(return_value=[MockResponse(id_=1, name="x")])
        result = sync_ops.create_rows_batched([{"name": "x"}], batch_size=100)
        assert len(result) == 1

    def test_bulk_insert_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.bulk_insert_rows = AsyncMock(return_value=5)
        result = sync_ops.bulk_insert_rows([{"name": f"b{i}"} for i in range(5)])
        assert result == 5


class TestSyncOperationsRead:
    def test_get_row(self, sync_ops, mock_async_ops):
        mock_async_ops.get_row = AsyncMock(return_value=MockResponse(id_=1, name="found"))
        result = sync_ops.get_row(1)
        assert result.id_ == 1

    def test_get_row_by_name(self, sync_ops, mock_async_ops):
        mock_async_ops.get_row_by_name = AsyncMock(return_value=MockResponse(id_=1, name="alice"))
        result = sync_ops.get_row_by_name("alice")
        assert result.name == "alice"

    def test_get_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.get_rows = AsyncMock(
            return_value=[MockResponse(id_=i, name=f"r{i}") for i in range(3)]
        )
        result = sync_ops.get_rows(limit=10)
        assert len(result) == 3

    def test_get_row_or_none_found(self, sync_ops, mock_async_ops):
        mock_async_ops.get_row_or_none = AsyncMock(return_value=MockResponse(id_=1, name="x"))
        result = sync_ops.get_row_or_none(1)
        assert result is not None

    def test_get_row_or_none_missing(self, sync_ops, mock_async_ops):
        mock_async_ops.get_row_or_none = AsyncMock(return_value=None)
        result = sync_ops.get_row_or_none(999)
        assert result is None

    def test_count_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.count_rows = AsyncMock(return_value=42)
        result = sync_ops.count_rows()
        assert result == 42

    def test_lookup_by_id_or_name(self, sync_ops, mock_async_ops):
        mock_async_ops.lookup_by_id_or_name = AsyncMock(return_value=(5, MockResponse(id_=5, name="looked")))
        row_id, obj = sync_ops.lookup_by_id_or_name(None, "looked")
        assert row_id == 5


class TestSyncOperationsUpdate:
    def test_update_row(self, sync_ops, mock_async_ops):
        mock_async_ops.update_row = AsyncMock(return_value=MockResponse(id_=1, name="updated"))
        result = sync_ops.update_row(1, name="updated")
        assert result.name == "updated"

    def test_update_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.update_rows = AsyncMock(return_value=[MockResponse(id_=1, name="u")])
        result = sync_ops.update_rows([{"id": 1, "name": "u"}])
        assert len(result) == 1


class TestSyncOperationsDelete:
    def test_delete_row(self, sync_ops, mock_async_ops):
        mock_async_ops.delete_row = AsyncMock(return_value={"id_": 1, "name": "gone"})
        result = sync_ops.delete_row(1, capture_data=True)
        assert result["name"] == "gone"

    def test_delete_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.delete_rows = AsyncMock(return_value=[{"id_": 1, "name": "a"}])
        result = sync_ops.delete_rows([1], capture_data=True)
        assert len(result) == 1

    def test_bulk_delete_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.bulk_delete_rows = AsyncMock(return_value=3)
        result = sync_ops.bulk_delete_rows([1, 2, 3])
        assert result == 3


class TestSyncOperationsFilter:
    def test_filter_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.filter_rows = AsyncMock(return_value=[MockResponse(id_=1, name="match")])
        result = sync_ops.filter_rows(filters=[])
        assert len(result) == 1

    def test_count_filtered_rows(self, sync_ops, mock_async_ops):
        mock_async_ops.count_filtered_rows = AsyncMock(return_value=7)
        result = sync_ops.count_filtered_rows(filters=[])
        assert result == 7

    def test_filter_one(self, sync_ops, mock_async_ops):
        mock_async_ops.filter_one = AsyncMock(return_value=MockResponse(id_=1, name="only"))
        result = sync_ops.filter_one(filters=[])
        assert result.name == "only"

    def test_filter_one_or_none(self, sync_ops, mock_async_ops):
        mock_async_ops.filter_one_or_none = AsyncMock(return_value=None)
        result = sync_ops.filter_one_or_none(filters=[])
        assert result is None

    def test_find_by(self, sync_ops, mock_async_ops):
        mock_async_ops.find_by = AsyncMock(return_value=[MockResponse(id_=1, name="found")])
        result = sync_ops.find_by(name="found")
        assert len(result) == 1

    def test_find_one_by(self, sync_ops, mock_async_ops):
        mock_async_ops.find_one_by = AsyncMock(return_value=MockResponse(id_=1, name="one"))
        result = sync_ops.find_one_by(name="one")
        assert result.name == "one"
