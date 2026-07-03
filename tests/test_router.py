"""Tests for macon.router (FastAPI CRUD endpoints)."""

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
    """Create an async HTTP client for the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestCreateEndpoints:
    async def test_create_row(self, client):
        response = await client.post(
            "/test_named/create_row",
            json={"name": "router_test"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "router_test"
        assert "id_" in data

    async def test_create_row_validation_error(self, client):
        response = await client.post(
            "/test_named/create_row",
            json={},
        )
        assert response.status_code == 400

    async def test_create_rows(self, client):
        response = await client.post(
            "/test_named/create_rows",
            json=[{"name": "batch_1"}, {"name": "batch_2"}],
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2


class TestReadEndpoints:
    async def test_get_row(self, client):
        create_resp = await client.post("/test_named/create_row", json={"name": "get_target"})
        row_id = create_resp.json()["id_"]

        response = await client.get(f"/test_named/get_row/{row_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "get_target"

    async def test_get_row_not_found(self, client):
        response = await client.get("/test_named/get_row/99999")
        assert response.status_code in (404, 500)

    async def test_get_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "list_1"})
        await client.post("/test_named/create_row", json={"name": "list_2"})

        response = await client.get("/test_named/get_rows")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    async def test_get_rows_pagination(self, client):
        for i in range(5):
            await client.post("/test_named/create_row", json={"name": f"page_{i}"})

        response = await client.get("/test_named/get_rows?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_count_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "count_1"})
        await client.post("/test_named/create_row", json={"name": "count_2"})

        response = await client.get("/test_named/count_rows")
        assert response.status_code == 200
        assert response.json()["count"] >= 2

    async def test_get_row_by_name(self, client):
        await client.post("/test_named/create_row", json={"name": "named_lookup"})

        response = await client.get("/test_named/get_row_by_name/named_lookup")
        assert response.status_code == 200
        assert response.json()["name"] == "named_lookup"


class TestUpdateEndpoints:
    async def test_update_row(self, client):
        create_resp = await client.post("/test_named/create_row", json={"name": "before"})
        row_id = create_resp.json()["id_"]

        response = await client.put(
            f"/test_named/update_row/{row_id}",
            json={"name": "after"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "after"

    async def test_update_row_not_found(self, client):
        response = await client.put(
            "/test_named/update_row/99999",
            json={"name": "x"},
        )
        assert response.status_code in (404, 500)


class TestDeleteEndpoints:
    async def test_delete_row(self, client):
        create_resp = await client.post("/test_named/create_row", json={"name": "delete_me"})
        row_id = create_resp.json()["id_"]

        response = await client.delete(f"/test_named/delete_row/{row_id}?capture_data=true")
        assert response.status_code == 200

    async def test_delete_row_not_found(self, client):
        response = await client.delete("/test_named/delete_row/99999")
        assert response.status_code in (404, 500)


class TestFilterEndpoints:
    async def test_filter_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "filter_a"})
        await client.post("/test_named/create_row", json={"name": "filter_b"})

        response = await client.post(
            "/test_named/filter_rows",
            json={
                "filters": [{"field": "name", "op": "eq", "value": "filter_a"}],
                "logical_op": "and",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "filter_a"

    async def test_count_filtered_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "cf_1"})
        await client.post("/test_named/create_row", json={"name": "cf_2"})

        response = await client.post(
            "/test_named/count_filtered_rows",
            json={
                "filters": [{"field": "name", "op": "starts_with", "value": "cf_"}],
            },
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2
