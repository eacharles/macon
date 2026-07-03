"""Extended tests for macon.router — more endpoints and edge cases."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from macon.db.base import Base
from macon.local_async import test_named as test_named_ops


@pytest.fixture
async def app(init_test_db):
    """Create a FastAPI app with the test_named router."""
    from macon.db.session import _engine
    from macon.router.base import create_table_router

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = FastAPI()
    router = create_table_router("test_named", test_named_ops)
    application.include_router(router)
    yield application

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestCreateBatch:
    async def test_create_rows_batched(self, client):
        response = await client.post(
            "/test_named/create_rows_batched",
            json=[{"name": f"batched_{i}"} for i in range(5)],
            params={"batch_size": 2},
        )
        assert response.status_code == 201
        assert len(response.json()) == 5

    async def test_bulk_insert_rows(self, client):
        response = await client.post(
            "/test_named/bulk_insert_rows",
            json=[{"name": f"bulk_{i}"} for i in range(10)],
        )
        assert response.status_code == 201
        assert response.json()["count"] == 10


class TestReadExtended:
    async def test_get_row_or_none_found(self, client):
        resp = await client.post("/test_named/create_row", json={"name": "or_none_found"})
        row_id = resp.json()["id_"]

        response = await client.get(f"/test_named/get_row_or_none/{row_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "or_none_found"

    async def test_get_row_or_none_missing(self, client):
        response = await client.get("/test_named/get_row_or_none/99999")
        assert response.status_code == 200
        assert response.json() is None

    async def test_get_rows_streaming(self, client):
        for i in range(3):
            await client.post("/test_named/create_row", json={"name": f"stream_{i}"})

        response = await client.get("/test_named/get_rows_streaming?limit=100")
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) >= 3

    async def test_lookup_by_id(self, client):
        resp = await client.post("/test_named/create_row", json={"name": "lookup_id"})
        row_id = resp.json()["id_"]

        response = await client.get(f"/test_named/lookup_by_id_or_name?id_={row_id}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "lookup_id"

    async def test_lookup_by_name(self, client):
        await client.post("/test_named/create_row", json={"name": "lookup_name"})

        response = await client.get("/test_named/lookup_by_id_or_name?name=lookup_name")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "lookup_name"

    async def test_lookup_missing_params(self, client):
        response = await client.get("/test_named/lookup_by_id_or_name")
        assert response.status_code == 400


class TestUpdateExtended:
    async def test_update_rows_batch(self, client):
        ids = []
        for i in range(3):
            resp = await client.post("/test_named/create_row", json={"name": f"upd_batch_{i}"})
            ids.append(resp.json()["id_"])

        updates = [{"id": id_, "name": f"updated_{i}"} for i, id_ in enumerate(ids)]
        response = await client.put("/test_named/update_rows", json=updates)
        assert response.status_code == 200
        assert len(response.json()) == 3
        assert response.json()[0]["name"] == "updated_0"


class TestDeleteExtended:
    async def test_delete_rows_batch(self, client):
        ids = []
        for i in range(3):
            resp = await client.post("/test_named/create_row", json={"name": f"del_batch_{i}"})
            ids.append(resp.json()["id_"])

        response = await client.request("DELETE", "/test_named/delete_rows", json=ids)
        assert response.status_code == 200

    async def test_bulk_delete_rows(self, client):
        ids = []
        for i in range(5):
            resp = await client.post("/test_named/create_row", json={"name": f"bulk_del_{i}"})
            ids.append(resp.json()["id_"])

        response = await client.request("DELETE", "/test_named/bulk_delete_rows", json=ids)
        assert response.status_code == 200
        assert response.json()["count"] == 5


class TestFilterExtended:
    async def test_filter_rows_streaming(self, client):
        await client.post("/test_named/create_row", json={"name": "fstream_a"})
        await client.post("/test_named/create_row", json={"name": "fstream_b"})

        response = await client.post(
            "/test_named/filter_rows_streaming",
            json={"filters": [{"field": "name", "op": "starts_with", "value": "fstream"}]},
        )
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) == 2

    async def test_filter_one(self, client):
        await client.post("/test_named/create_row", json={"name": "filter_one_target"})

        response = await client.post(
            "/test_named/filter_one",
            json={"filters": [{"field": "name", "op": "eq", "value": "filter_one_target"}]},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "filter_one_target"

    async def test_filter_one_or_none_missing(self, client):
        response = await client.post(
            "/test_named/filter_one_or_none",
            json={"filters": [{"field": "name", "op": "eq", "value": "zzz_never_exists"}]},
        )
        assert response.status_code == 200

    async def test_find_by(self, client):
        await client.post("/test_named/create_row", json={"name": "find_by_target"})

        response = await client.post(
            "/test_named/find_by",
            json={"name": "find_by_target"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_find_one_by(self, client):
        await client.post("/test_named/create_row", json={"name": "find_one_target"})

        response = await client.post(
            "/test_named/find_one_by",
            json={"name": "find_one_target"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "find_one_target"
