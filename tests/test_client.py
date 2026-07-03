"""Tests for macon.client — RemoteTableOperations, RemoteAPI, RemoteDatabase."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import BaseModel

from macon.client.base import RemoteAPI, RemoteTableOperations
from macon.client.client import RemoteDatabase
from macon.models import RemoteAPIError, Filter, FilterOp


class SampleResponse(BaseModel):
    id_: int
    name: str


class SampleCreate(BaseModel):
    name: str


def make_response(status_code: int = 200, json_data=None, text: str = "") -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = text or (json.dumps(json_data) if json_data else "")
    return resp


@pytest.fixture
def mock_client():
    """A mocked httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def ops(mock_client):
    """A RemoteTableOperations instance with a mocked client."""
    return RemoteTableOperations(
        client=mock_client,
        endpoint="http://test/api/v1/items",
        response_model=SampleResponse,
        create_model=SampleCreate,
    )


class TestHandleResponse:
    def test_success(self, ops):
        resp = make_response(200, {"id_": 1, "name": "ok"})
        result = ops._handle_response(resp, expected_status=200)
        assert result == {"id_": 1, "name": "ok"}

    def test_error_with_json(self, ops):
        resp = make_response(400, {"error": "Bad input", "details": "name required"})
        with pytest.raises(RemoteAPIError, match="Bad input.*name required"):
            ops._handle_response(resp, expected_status=200)

    def test_error_with_plain_text(self, ops):
        resp = make_response(500, text="Internal Server Error")
        resp.json.side_effect = Exception("not json")
        with pytest.raises(RemoteAPIError, match="Internal Server Error"):
            ops._handle_response(resp, expected_status=200)

    def test_error_status_mismatch(self, ops):
        resp = make_response(404, {"error": "Not found"})
        with pytest.raises(RemoteAPIError, match="404"):
            ops._handle_response(resp, expected_status=200)


class TestCreateOperations:
    async def test_create_row(self, ops, mock_client):
        mock_client.post.return_value = make_response(201, {"id_": 1, "name": "new"})
        result = await ops.create_row(name="new")
        assert result.id_ == 1
        assert result.name == "new"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/create_row" in call_args[0][0]

    async def test_create_rows(self, ops, mock_client):
        mock_client.post.return_value = make_response(201, [{"id_": 1, "name": "a"}, {"id_": 2, "name": "b"}])
        result = await ops.create_rows([{"name": "a"}, {"name": "b"}])
        assert len(result) == 2
        assert result[0].name == "a"

    async def test_create_rows_batched(self, ops, mock_client):
        mock_client.post.return_value = make_response(201, [{"id_": 1, "name": "x"}])
        result = await ops.create_rows_batched([{"name": "x"}], batch_size=500)
        assert len(result) == 1

    async def test_bulk_insert_rows(self, ops, mock_client):
        mock_client.post.return_value = make_response(201, {"count": 10})
        result = await ops.bulk_insert_rows([{"name": f"b_{i}"} for i in range(10)])
        assert result == 10


class TestReadOperations:
    async def test_get_row(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, {"id_": 5, "name": "found"})
        result = await ops.get_row(5)
        assert result.id_ == 5
        assert "get_row/5" in mock_client.get.call_args[0][0]

    async def test_get_row_or_none_found(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, {"id_": 1, "name": "x"})
        result = await ops.get_row_or_none(1)
        assert result is not None

    async def test_get_row_or_none_null(self, ops, mock_client):
        resp = make_response(200)
        resp.json.return_value = None
        mock_client.get.return_value = resp
        result = await ops.get_row_or_none(999)
        assert result is None

    async def test_get_row_by_name(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, {"id_": 1, "name": "alice"})
        result = await ops.get_row_by_name("alice")
        assert result.name == "alice"

    async def test_get_rows(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, [{"id_": 1, "name": "a"}, {"id_": 2, "name": "b"}])
        result = await ops.get_rows(skip=0, limit=10)
        assert len(result) == 2

    async def test_count_rows(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, {"count": 42})
        result = await ops.count_rows()
        assert result == 42

    async def test_lookup_by_id_or_name(self, ops, mock_client):
        mock_client.get.return_value = make_response(200, {"id": 3, "data": {"id_": 3, "name": "looked_up"}})
        row_id, obj = await ops.lookup_by_id_or_name(id_=3)
        assert row_id == 3
        assert obj.name == "looked_up"


class TestUpdateOperations:
    async def test_update_row(self, ops, mock_client):
        mock_client.put.return_value = make_response(200, {"id_": 1, "name": "updated"})
        result = await ops.update_row(1, name="updated")
        assert result.name == "updated"
        assert "/update_row/1" in mock_client.put.call_args[0][0]

    async def test_update_rows(self, ops, mock_client):
        mock_client.put.return_value = make_response(200, [{"id_": 1, "name": "a"}, {"id_": 2, "name": "b"}])
        result = await ops.update_rows([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
        assert len(result) == 2


class TestDeleteOperations:
    async def test_delete_row_with_capture(self, ops, mock_client):
        mock_client.delete.return_value = make_response(200, {"id_": 1, "name": "deleted"})
        result = await ops.delete_row(1, capture_data=True)
        assert result is not None
        assert result.name == "deleted"

    async def test_delete_row_without_capture(self, ops, mock_client):
        mock_client.delete.return_value = make_response(200, {"deleted": True})
        result = await ops.delete_row(1, capture_data=False)
        assert result is None

    async def test_delete_rows_with_capture(self, ops, mock_client):
        mock_client.request.return_value = make_response(
            200, [{"id_": 1, "name": "a"}, {"id_": 2, "name": "b"}]
        )
        result = await ops.delete_rows([1, 2], capture_data=True)
        assert len(result) == 2

    async def test_delete_rows_count(self, ops, mock_client):
        mock_client.request.return_value = make_response(200, {"count": 5})
        result = await ops.delete_rows([1, 2, 3, 4, 5], capture_data=False)
        assert result == 5

    async def test_bulk_delete(self, ops, mock_client):
        mock_client.request.return_value = make_response(200, {"count": 3})
        result = await ops.bulk_delete_rows([1, 2, 3])
        assert result == 3


class TestFilterOperations:
    async def test_filter_rows(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, [{"id_": 1, "name": "match"}])
        result = await ops.filter_rows(filters=[Filter(field="name", op=FilterOp.EQ, value="match")])
        assert len(result) == 1
        assert result[0].name == "match"

    async def test_count_filtered_rows(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, {"count": 7})
        result = await ops.count_filtered_rows(
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="a")]
        )
        assert result == 7

    async def test_filter_one(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, {"id_": 1, "name": "unique"})
        result = await ops.filter_one(filters=[Filter(field="name", op=FilterOp.EQ, value="unique")])
        assert result.name == "unique"

    async def test_filter_one_or_none_found(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, {"id_": 1, "name": "x"})
        result = await ops.filter_one_or_none(filters=[Filter(field="name", op=FilterOp.EQ, value="x")])
        assert result is not None

    async def test_filter_one_or_none_null(self, ops, mock_client):
        resp = make_response(200)
        resp.json.return_value = None
        mock_client.post.return_value = resp
        result = await ops.filter_one_or_none(filters=[Filter(field="name", op=FilterOp.EQ, value="nope")])
        assert result is None

    async def test_find_by(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, [{"id_": 1, "name": "found"}])
        result = await ops.find_by(name="found", limit=10)
        assert len(result) == 1

    async def test_find_one_by(self, ops, mock_client):
        mock_client.post.return_value = make_response(200, {"id_": 1, "name": "one"})
        result = await ops.find_one_by(name="one")
        assert result.name == "one"


class TestRemoteAPI:
    async def test_context_manager(self):
        async with RemoteAPI("http://localhost:8000") as api:
            assert api.client is not None
        # After exit, client is closed (no assertion needed, just no error)

    async def test_table_returns_operations(self):
        async with RemoteAPI("http://localhost:8000", api_prefix="/api/v1") as api:
            table_ops = api.table("items", SampleResponse, SampleCreate)
            assert isinstance(table_ops, RemoteTableOperations)
            assert table_ops.endpoint == "http://localhost:8000/api/v1/items"

    def test_table_outside_context_raises(self):
        api = RemoteAPI("http://localhost:8000")
        with pytest.raises(RemoteAPIError, match="not initialized"):
            api.table("items", SampleResponse, SampleCreate)

    async def test_auth_token_header(self):
        async with RemoteAPI("http://localhost:8000", auth_token="secret") as api:
            assert api.headers["Authorization"] == "Bearer secret"


class TestRemoteDatabase:
    async def test_context_manager_sets_up_clients(self):
        configs = {
            "items": (SampleResponse, SampleCreate, None),
        }
        async with RemoteDatabase("http://localhost:8000", table_configs=configs) as db:
            assert hasattr(db, "items")
            assert db.list_tables() == ["items"]

    async def test_get_client(self):
        configs = {
            "items": (SampleResponse, SampleCreate, None),
        }
        async with RemoteDatabase("http://localhost:8000", table_configs=configs) as db:
            client = db.get_client("items")
            assert client is not None

    async def test_get_client_missing(self):
        configs = {}
        async with RemoteDatabase("http://localhost:8000", table_configs=configs) as db:
            client = db.get_client("nonexistent")
            assert client is None
