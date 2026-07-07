"""Coverage tests for macon.router.base — 404/400 error paths."""

import pytest
from unittest.mock import AsyncMock, patch
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


class TestGetRow404:
    async def test_returns_404_when_ops_returns_none(self, app):
        with patch.object(test_named_ops, "get_row", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/test_named/get_row/1")
                assert response.status_code == 404


class TestGetRowByName404:
    async def test_returns_404_when_ops_returns_none(self, app):
        with patch.object(test_named_ops, "get_row_by_name", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/test_named/get_row_by_name/nonexistent")
                assert response.status_code == 404


class TestLookupByIdOrName404:
    async def test_returns_404_when_ops_returns_none(self, app):
        with patch.object(
            test_named_ops, "lookup_by_id_or_name", new_callable=AsyncMock, return_value=(None, None)
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/test_named/lookup_by_id_or_name", params={"name": "x"})
                assert response.status_code == 404


class TestUpdateRow404And400:
    async def test_returns_404_when_ops_returns_none(self, app):
        with patch.object(test_named_ops, "update_row", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.put("/test_named/update_row/99999", json={"name": "x"})
                assert response.status_code == 404

    async def test_returns_400_on_validation_error(self, app):
        from macon.models.test_classes import TestNamedCreate

        async def raise_validation(*args, **kwargs):
            TestNamedCreate()  # missing required 'name' field triggers ValidationError

        with patch.object(test_named_ops, "update_row", side_effect=raise_validation):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.put("/test_named/update_row/1", json={"name": "x"})
                assert response.status_code == 400


class TestUpdateRows400:
    async def test_returns_400_on_validation_error(self, app):
        from macon.models.test_classes import TestNamedCreate

        async def raise_validation(*args, **kwargs):
            TestNamedCreate()  # missing required 'name' field triggers ValidationError

        with patch.object(test_named_ops, "update_rows", side_effect=raise_validation):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.put("/test_named/update_rows", json=[{"id": 1, "name": "x"}])
                assert response.status_code == 400


class TestDeleteRow404:
    async def test_returns_404_when_none_with_capture(self, app):
        with patch.object(test_named_ops, "delete_row", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.delete("/test_named/delete_row/99999", params={"capture_data": "true"})
                assert response.status_code == 404


class TestFilterOne404:
    async def test_returns_404_when_no_match(self, app):
        with patch.object(test_named_ops, "filter_one", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/test_named/filter_one",
                    json={
                        "filters": [{"field": "name", "op": "eq", "value": "xyz"}],
                        "logical_op": "and",
                    },
                )
                assert response.status_code == 404


class TestFindOneBy404:
    async def test_returns_404_when_no_match(self, app):
        with patch.object(test_named_ops, "find_one_by", new_callable=AsyncMock, return_value=None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post("/test_named/find_one_by", json={"name": "xyz"})
                assert response.status_code == 404
