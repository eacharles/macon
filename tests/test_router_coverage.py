"""Additional unit tests for macon.router.base — covering untested endpoint paths."""

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


@pytest.fixture
async def seeded_client(client):
    """Client with some rows pre-created."""
    for name in ["alpha", "beta", "gamma", "delta", "epsilon"]:
        await client.post("/test_named/create_row", json={"name": name})
    return client


class TestCreateRowExtended:
    async def test_create_no_validate(self, client):
        response = await client.post(
            "/test_named/create_row", json={"name": "no_val"}, params={"validate": "false"}
        )
        assert response.status_code == 201
        assert response.json()["name"] == "no_val"

    async def test_create_duplicate_name(self, client):
        await client.post("/test_named/create_row", json={"name": "unique"})
        response = await client.post("/test_named/create_row", json={"name": "unique"})
        assert response.status_code == 500


class TestCreateRowsBatchedExtended:
    async def test_validation_error(self, client):
        response = await client.post(
            "/test_named/create_rows_batched",
            json=[{}],
            params={"batch_size": 1},
        )
        assert response.status_code == 400


class TestGetRowsExtended:
    async def test_get_rows_with_skip_and_limit(self, seeded_client):
        response = await seeded_client.get("/test_named/get_rows", params={"skip": 1, "limit": 2})
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_get_rows_negative_skip(self, client):
        response = await client.get("/test_named/get_rows", params={"skip": -1})
        assert response.status_code == 422

    async def test_get_rows_zero_limit(self, client):
        response = await client.get("/test_named/get_rows", params={"limit": 0})
        # FastAPI Query(ge=1) handles this — returns 422
        assert response.status_code == 422

    async def test_get_rows_limit_too_large(self, client):
        response = await client.get("/test_named/get_rows", params={"limit": 10001})
        # FastAPI Query(le=10000) handles this — returns 422
        assert response.status_code == 422


class TestGetRowsStreaming:
    async def test_streaming_with_filters(self, seeded_client):
        response = await seeded_client.get("/test_named/get_rows_streaming", params={"limit": 3})
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) == 3

    async def test_streaming_skip(self, seeded_client):
        response = await seeded_client.get("/test_named/get_rows_streaming", params={"skip": 3, "limit": 100})
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) == 2


class TestUpdateRowExtended:
    async def test_update_via_patch(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 1})
        row_id = get_resp.json()[0]["id_"]

        response = await seeded_client.patch(f"/test_named/update_row/{row_id}", json={"name": "patched"})
        assert response.status_code == 200
        assert response.json()["name"] == "patched"

    async def test_update_rows_via_patch(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 2})
        rows = get_resp.json()

        response = await seeded_client.patch(
            "/test_named/update_rows",
            json=[{"id": rows[0]["id_"], "name": "p1"}, {"id": rows[1]["id_"], "name": "p2"}],
        )
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestDeleteRowExtended:
    async def test_delete_no_capture(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 1})
        row_id = get_resp.json()[0]["id_"]

        response = await seeded_client.delete(
            f"/test_named/delete_row/{row_id}", params={"capture_data": "false"}
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    async def test_delete_with_capture(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 1})
        row_id = get_resp.json()[0]["id_"]

        response = await seeded_client.delete(
            f"/test_named/delete_row/{row_id}", params={"capture_data": "true"}
        )
        assert response.status_code == 200
        assert "name" in response.json()


class TestDeleteRowsExtended:
    async def test_delete_rows_with_capture(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 2})
        ids = [r["id_"] for r in get_resp.json()]

        response = await seeded_client.request(
            "DELETE", "/test_named/delete_rows", json=ids, params={"capture_data": "true"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 2

    async def test_delete_rows_no_capture(self, seeded_client):
        get_resp = await seeded_client.get("/test_named/get_rows", params={"limit": 2})
        ids = [r["id_"] for r in get_resp.json()]

        response = await seeded_client.request(
            "DELETE", "/test_named/delete_rows", json=ids, params={"capture_data": "false"}
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2


class TestFilterRowsExtended:
    async def test_filter_with_order_by(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows",
            json={
                "filters": [],
                "logical_op": "and",
                "order_by": {"field": "name", "descending": True},
                "limit": 5,
            },
        )
        assert response.status_code == 200
        names = [r["name"] for r in response.json()]
        assert names == sorted(names, reverse=True)

    async def test_filter_with_or_logic(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows",
            json={
                "filters": [
                    {"field": "name", "op": "eq", "value": "alpha"},
                    {"field": "name", "op": "eq", "value": "beta"},
                ],
                "logical_op": "or",
            },
        )
        assert response.status_code == 200
        names = {r["name"] for r in response.json()}
        assert names == {"alpha", "beta"}

    async def test_filter_with_pagination(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows",
            json={"filters": [], "logical_op": "and", "skip": 2, "limit": 2},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_filter_pagination_skip_negative(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows",
            json={"filters": [], "logical_op": "and", "skip": -1},
        )
        assert response.status_code == 400
        assert "skip" in response.json()["detail"]

    async def test_filter_pagination_limit_too_large(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows",
            json={"filters": [], "logical_op": "and", "limit": 10001},
        )
        assert response.status_code == 400
        assert "limit" in response.json()["detail"]


class TestFilterRowsStreamingExtended:
    async def test_streaming_with_filter(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows_streaming",
            json={
                "filters": [{"field": "name", "op": "like", "value": "%a%"}],
                "logical_op": "and",
                "limit": 100,
            },
        )
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) >= 1

    async def test_streaming_with_or_logic(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/filter_rows_streaming",
            json={
                "filters": [
                    {"field": "name", "op": "eq", "value": "alpha"},
                    {"field": "name", "op": "eq", "value": "beta"},
                ],
                "logical_op": "or",
                "limit": 100,
            },
        )
        assert response.status_code == 200
        lines = [line for line in response.text.strip().split("\n") if line]
        assert len(lines) == 2


class TestCountFilteredExtended:
    async def test_count_with_filter(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/count_filtered_rows",
            json={
                "filters": [{"field": "name", "op": "like", "value": "%a%"}],
                "logical_op": "and",
            },
        )
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    async def test_count_with_or_logic(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/count_filtered_rows",
            json={
                "filters": [
                    {"field": "name", "op": "eq", "value": "alpha"},
                    {"field": "name", "op": "eq", "value": "beta"},
                ],
                "logical_op": "or",
            },
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2

    async def test_count_no_filters(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/count_filtered_rows",
            json={"filters": [], "logical_op": "and"},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 5


class TestFindByExtended:
    async def test_find_by_with_order(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/find_by",
            json={"name": "alpha", "order_by": {"field": "name", "descending": False}},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_find_by_with_pagination(self, seeded_client):
        # Create multiple matching rows by name pattern — use a unique field
        await seeded_client.post("/test_named/create_row", json={"name": "find_a"})
        await seeded_client.post("/test_named/create_row", json={"name": "find_b"})

        response = await seeded_client.post(
            "/test_named/find_by",
            json={"name": "find_a", "skip": 0, "limit": 10},
        )
        assert response.status_code == 200

    async def test_find_by_invalid_order_by(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/find_by",
            json={"name": "alpha", "order_by": "not_a_dict"},
        )
        assert response.status_code == 400
        assert "order_by" in str(response.json()["detail"]).lower()

    async def test_find_by_multiple_order_by(self, seeded_client):
        response = await seeded_client.post(
            "/test_named/find_by",
            json={
                "name": "alpha",
                "order_by": [{"field": "name", "descending": False}],
            },
        )
        assert response.status_code == 200


class TestRequireAuth:
    async def test_missing_auth_header(self):
        from macon.router.base import require_auth
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_auth(authorization=None)
        assert exc_info.value.status_code == 401

    async def test_invalid_format(self):
        from macon.router.base import require_auth
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_auth(authorization="Basic abc123")
        assert exc_info.value.status_code == 401

    async def test_empty_token(self):
        from macon.router.base import require_auth
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_auth(authorization="Bearer ")
        assert exc_info.value.status_code == 401

    async def test_valid_token(self):
        from macon.router.base import require_auth

        token = require_auth(authorization="Bearer my_secret_token")
        assert token == "my_secret_token"


class TestValidatePaginationParams:
    async def test_negative_skip(self):
        from macon.router.base import validate_pagination_params
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(-1, None)
        assert exc_info.value.status_code == 400

    async def test_zero_limit(self):
        from macon.router.base import validate_pagination_params
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(0, 0)
        assert exc_info.value.status_code == 400

    async def test_limit_too_large(self):
        from macon.router.base import validate_pagination_params
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_pagination_params(0, 10001)
        assert exc_info.value.status_code == 400

    async def test_valid_params(self):
        from macon.router.base import validate_pagination_params

        result = validate_pagination_params(5, 100)
        assert result == (5, 100)

    async def test_none_limit(self):
        from macon.router.base import validate_pagination_params

        result = validate_pagination_params(0, None)
        assert result == (0, None)


class TestValidateBatchSize:
    async def test_too_small(self):
        from macon.router.base import validate_batch_size
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_batch_size(0)
        assert exc_info.value.status_code == 400

    async def test_too_large(self):
        from macon.router.base import validate_batch_size
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_batch_size(10001)
        assert exc_info.value.status_code == 400

    async def test_valid(self):
        from macon.router.base import validate_batch_size

        assert validate_batch_size(500) == 500
