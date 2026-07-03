"""Tests for router input validation and error handling paths."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from macon.db.base import Base
from macon.local_async import test_named as test_named_ops


@pytest.fixture
async def app(init_test_db):
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


class TestCreateValidation:
    async def test_create_rows_exceeds_limit(self, client):
        data = [{"name": f"item_{i}"} for i in range(10001)]
        response = await client.post("/test_named/create_rows", json=data)
        assert response.status_code == 400
        assert "10000" in response.json()["detail"]

    async def test_bulk_insert_exceeds_limit(self, client):
        data = [{"name": f"item_{i}"} for i in range(100001)]
        response = await client.post("/test_named/bulk_insert_rows", json=data)
        assert response.status_code == 400
        assert "100000" in response.json()["detail"]

    async def test_create_row_missing_required_field(self, client):
        response = await client.post("/test_named/create_row", json={})
        assert response.status_code == 400


class TestUpdateValidation:
    async def test_update_rows_exceeds_limit(self, client):
        data = [{"id": i, "name": f"item_{i}"} for i in range(10001)]
        response = await client.put("/test_named/update_rows", json=data)
        assert response.status_code == 400
        assert "10000" in response.json()["detail"]

    async def test_update_rows_missing_id(self, client):
        data = [{"name": "no_id_field"}]
        response = await client.put("/test_named/update_rows", json=data)
        assert response.status_code == 400
        assert "id" in response.json()["detail"].lower()


class TestDeleteValidation:
    async def test_delete_rows_exceeds_limit(self, client):
        data = list(range(10001))
        response = await client.request("DELETE", "/test_named/delete_rows", json=data)
        assert response.status_code == 400
        assert "10000" in response.json()["detail"]

    async def test_bulk_delete_exceeds_limit(self, client):
        data = list(range(100001))
        response = await client.request("DELETE", "/test_named/bulk_delete_rows", json=data)
        assert response.status_code == 400
        assert "100000" in response.json()["detail"]


class TestFilterValidation:
    async def test_filter_one_missing_filters(self, client):
        response = await client.post("/test_named/filter_one", json={"filters": [], "logical_op": "and"})
        assert response.status_code == 400

    async def test_filter_one_or_none_missing_filters(self, client):
        response = await client.post(
            "/test_named/filter_one_or_none", json={"filters": [], "logical_op": "and"}
        )
        assert response.status_code == 400


class TestLookupValidation:
    async def test_lookup_missing_both_params(self, client):
        response = await client.get("/test_named/lookup_by_id_or_name")
        assert response.status_code == 400
        assert "id_" in response.json()["detail"].lower() or "name" in response.json()["detail"].lower()


class TestFindValidation:
    async def test_find_by_empty_body(self, client):
        response = await client.post("/test_named/find_by", json={})
        assert response.status_code == 400

    async def test_find_one_by_empty_body(self, client):
        response = await client.post("/test_named/find_one_by", json={})
        assert response.status_code == 400
