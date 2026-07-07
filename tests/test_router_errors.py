"""Tests for expected error responses from the router layer."""

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


class TestGetRowByNameNotFound:
    async def test_nonexistent_name(self, client):
        response = await client.get("/test_named/get_row_by_name/nonexistent")
        assert response.status_code in (404, 500)

    async def test_empty_table(self, client):
        response = await client.get("/test_named/get_row_by_name/anything")
        assert response.status_code in (404, 500)


class TestLookupByIdOrNameNotFound:
    async def test_nonexistent_name(self, client):
        response = await client.get("/test_named/lookup_by_id_or_name", params={"name": "ghost"})
        assert response.status_code in (404, 500)

    async def test_nonexistent_id(self, client):
        response = await client.get("/test_named/lookup_by_id_or_name", params={"id_": 99999})
        assert response.status_code in (404, 500)


class TestFilterOneErrors:
    async def test_no_matching_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "only_one"})
        response = await client.post(
            "/test_named/filter_one",
            json={"filters": [{"field": "name", "op": "eq", "value": "nonexistent"}], "logical_op": "and"},
        )
        assert response.status_code in (404, 500)

    async def test_multiple_matching_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "dup_a"})
        await client.post("/test_named/create_row", json={"name": "dup_b"})
        response = await client.post(
            "/test_named/filter_one",
            json={"filters": [{"field": "name", "op": "like", "value": "dup_%"}], "logical_op": "and"},
        )
        assert response.status_code in (400, 500)


class TestFilterOneOrNoneErrors:
    async def test_multiple_matching_rows(self, client):
        await client.post("/test_named/create_row", json={"name": "multi_a"})
        await client.post("/test_named/create_row", json={"name": "multi_b"})
        response = await client.post(
            "/test_named/filter_one_or_none",
            json={"filters": [{"field": "name", "op": "like", "value": "multi_%"}], "logical_op": "and"},
        )
        assert response.status_code in (400, 500)


class TestFilterRowsErrors:
    async def test_invalid_logical_op(self, client):
        response = await client.post(
            "/test_named/filter_rows",
            json={"filters": [{"field": "name", "op": "eq", "value": "x"}], "logical_op": "xor"},
        )
        assert response.status_code == 400
        assert "logical_op" in response.json()["detail"]

    async def test_nonexistent_field(self, client):
        response = await client.post(
            "/test_named/filter_rows",
            json={"filters": [{"field": "bogus_field", "op": "eq", "value": "x"}], "logical_op": "and"},
        )
        assert response.status_code == 500
        assert "bogus_field" in response.json()["detail"]


class TestFindOneByErrors:
    async def test_no_matching_rows(self, client):
        response = await client.post("/test_named/find_one_by", json={"name": "nonexistent"})
        assert response.status_code in (404, 500)

    async def test_nonexistent_field(self, client):
        response = await client.post("/test_named/find_one_by", json={"bogus": "value"})
        assert response.status_code == 500
        assert "bogus" in response.json()["detail"]
