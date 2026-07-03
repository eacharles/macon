"""Tests for macon.remote_async — AsyncRemoteOperations with mocked HTTP."""

import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from macon.remote_async.base import AsyncRemoteOperations
from macon.client.base import RemoteTableOperations
from macon.models import Filter, FilterOp


class ItemResponse(BaseModel):
    id_: int
    name: str


class ItemCreate(BaseModel):
    name: str


def mock_response(status_code: int = 200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ""
    return resp


@pytest.fixture
def ops():
    """Create an AsyncRemoteOperations instance."""
    return AsyncRemoteOperations(
        base_url="http://test-server:8000",
        table_name="items",
        response_model=ItemResponse,
        create_model=ItemCreate,
    )


class TestContextManager:
    async def test_enter_exit(self, ops):
        with patch.object(ops, "_api", create=True):
            async with ops:
                assert ops._client is not None
                assert ops._owns_api is True
            assert ops._client is None
            assert ops._owns_api is False

    async def test_stores_attributes(self, ops):
        assert ops.base_url == "http://test-server:8000"
        assert ops.table_name == "items"
        assert ops.response_model is ItemResponse
        assert ops.create_model is ItemCreate

    async def test_context_manager_creates_client(self):
        ops = AsyncRemoteOperations(
            base_url="http://localhost:9999",
            table_name="things",
            response_model=ItemResponse,
            create_model=ItemCreate,
            timeout=5.0,
            auth_token="tok123",
        )
        async with ops:
            assert ops._client is not None
            assert ops._api is not None


class TestGetClientWithoutContext:
    async def test_warns_on_first_call(self, ops):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # get_client outside context manager should warn
            # but it will fail because no real server — that's fine,
            # we just want to verify the warning logic
            try:
                await ops.get_client()
            except Exception:
                pass
            # Check warning was issued
            resource_warnings = [x for x in w if issubclass(x.category, ResourceWarning)]
            assert len(resource_warnings) == 1
            assert "context manager" in str(resource_warnings[0].message)

    async def test_warns_only_once(self, ops):
        ops._has_warned = True
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                await ops.get_client()
            except Exception:
                pass
            resource_warnings = [x for x in w if issubclass(x.category, ResourceWarning)]
            assert len(resource_warnings) == 0


class TestWithClientDecorator:
    async def test_injects_client(self):
        mock_client = AsyncMock(spec=RemoteTableOperations)
        mock_client.get_row = AsyncMock(return_value=ItemResponse(id_=1, name="x"))

        ops = AsyncRemoteOperations(
            base_url="http://test:8000",
            table_name="items",
            response_model=ItemResponse,
            create_model=ItemCreate,
        )
        ops._client = mock_client

        result = await ops.get_row(1)
        mock_client.get_row.assert_called_once_with(1)
        assert result.id_ == 1


class TestCRUDOperationsViaContext:
    """Test all CRUD operations delegate correctly to the underlying client."""

    @pytest.fixture
    async def ctx_ops(self):
        """Ops with a mocked internal client."""
        ops = AsyncRemoteOperations(
            base_url="http://test:8000",
            table_name="items",
            response_model=ItemResponse,
            create_model=ItemCreate,
        )
        mock_client = AsyncMock(spec=RemoteTableOperations)
        ops._client = mock_client
        return ops, mock_client

    async def test_create_row(self, ctx_ops):
        ops, client = ctx_ops
        client.create_row = AsyncMock(return_value=ItemResponse(id_=1, name="new"))
        result = await ops.create_row(name="new")
        client.create_row.assert_called_once_with(name="new")
        assert result.name == "new"

    async def test_create_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.create_rows = AsyncMock(
            return_value=[ItemResponse(id_=1, name="a"), ItemResponse(id_=2, name="b")]
        )
        result = await ops.create_rows([{"name": "a"}, {"name": "b"}])
        assert len(result) == 2

    async def test_bulk_insert_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.bulk_insert_rows = AsyncMock(return_value=5)
        result = await ops.bulk_insert_rows([{"name": f"b{i}"} for i in range(5)])
        assert result == 5

    async def test_get_row(self, ctx_ops):
        ops, client = ctx_ops
        client.get_row = AsyncMock(return_value=ItemResponse(id_=3, name="found"))
        result = await ops.get_row(3)
        client.get_row.assert_called_once_with(3)
        assert result.id_ == 3

    async def test_get_row_or_none(self, ctx_ops):
        ops, client = ctx_ops
        client.get_row_or_none = AsyncMock(return_value=None)
        result = await ops.get_row_or_none(999)
        assert result is None

    async def test_get_row_by_name(self, ctx_ops):
        ops, client = ctx_ops
        client.get_row_by_name = AsyncMock(return_value=ItemResponse(id_=1, name="alice"))
        result = await ops.get_row_by_name("alice")
        assert result.name == "alice"

    async def test_get_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.get_rows = AsyncMock(return_value=[ItemResponse(id_=1, name="x")])
        result = await ops.get_rows(limit=10)
        client.get_rows.assert_called_once_with(limit=10)
        assert len(result) == 1

    async def test_count_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.count_rows = AsyncMock(return_value=42)
        result = await ops.count_rows()
        assert result == 42

    async def test_lookup_by_id_or_name(self, ctx_ops):
        ops, client = ctx_ops
        client.lookup_by_id_or_name = AsyncMock(return_value=(5, ItemResponse(id_=5, name="looked")))
        row_id, obj = await ops.lookup_by_id_or_name(name="looked")
        assert row_id == 5

    async def test_update_row(self, ctx_ops):
        ops, client = ctx_ops
        client.update_row = AsyncMock(return_value=ItemResponse(id_=1, name="updated"))
        result = await ops.update_row(1, name="updated")
        assert result.name == "updated"

    async def test_update_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.update_rows = AsyncMock(return_value=[ItemResponse(id_=1, name="u")])
        result = await ops.update_rows([{"id": 1, "name": "u"}])
        assert len(result) == 1

    async def test_delete_row(self, ctx_ops):
        ops, client = ctx_ops
        client.delete_row = AsyncMock(return_value=ItemResponse(id_=1, name="gone"))
        result = await ops.delete_row(1)
        assert result.name == "gone"

    async def test_delete_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.delete_rows = AsyncMock(return_value=3)
        result = await ops.delete_rows([1, 2, 3])
        assert result == 3

    async def test_bulk_delete_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.bulk_delete_rows = AsyncMock(return_value=10)
        result = await ops.bulk_delete_rows([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert result == 10

    async def test_filter_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.filter_rows = AsyncMock(return_value=[ItemResponse(id_=1, name="match")])
        result = await ops.filter_rows(filters=[Filter(field="name", op=FilterOp.EQ, value="match")])
        assert len(result) == 1

    async def test_count_filtered_rows(self, ctx_ops):
        ops, client = ctx_ops
        client.count_filtered_rows = AsyncMock(return_value=7)
        result = await ops.count_filtered_rows(
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="a")]
        )
        assert result == 7

    async def test_filter_one(self, ctx_ops):
        ops, client = ctx_ops
        client.filter_one = AsyncMock(return_value=ItemResponse(id_=1, name="only"))
        result = await ops.filter_one(filters=[Filter(field="name", op=FilterOp.EQ, value="only")])
        assert result.name == "only"

    async def test_filter_one_or_none(self, ctx_ops):
        ops, client = ctx_ops
        client.filter_one_or_none = AsyncMock(return_value=None)
        result = await ops.filter_one_or_none(filters=[Filter(field="name", op=FilterOp.EQ, value="nope")])
        assert result is None

    async def test_find_by(self, ctx_ops):
        ops, client = ctx_ops
        client.find_by = AsyncMock(return_value=[ItemResponse(id_=1, name="found")])
        result = await ops.find_by(name="found")
        assert len(result) == 1

    async def test_find_one_by(self, ctx_ops):
        ops, client = ctx_ops
        client.find_one_by = AsyncMock(return_value=ItemResponse(id_=1, name="one"))
        result = await ops.find_one_by(name="one")
        assert result.name == "one"


class TestCustomClientClass:
    async def test_uses_custom_class_in_context(self):
        class CustomOps(RemoteTableOperations):
            pass

        ops = AsyncRemoteOperations(
            base_url="http://test:8000",
            table_name="items",
            response_model=ItemResponse,
            create_model=ItemCreate,
            client_class=CustomOps,
        )
        async with ops:
            assert isinstance(ops._client, CustomOps)
