"""Tests for macon.router.app — app factory and middleware functions."""

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from macon.router.app import (
    register_all_routers,
    add_health_check,
    add_error_handlers,
    add_rate_limiting,
    setup_fastapi_app,
)


@pytest.fixture
def base_app():
    """A plain FastAPI app with no routers."""
    return FastAPI()


@pytest.fixture
async def client_for(base_app):
    """Factory that returns an AsyncClient for a given app."""

    async def _make_client(app):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    return _make_client


class TestRegisterAllRouters:
    async def test_registers_routers_with_prefix(self, base_app, client_for):
        router = APIRouter(prefix="/items")

        @router.get("/list")
        async def list_items():
            return [{"id": 1}]

        register_all_routers(base_app, [router], prefix="/api/v1")

        async with await client_for(base_app) as client:
            response = await client.get("/api/v1/items/list")
            assert response.status_code == 200
            assert response.json() == [{"id": 1}]

    async def test_custom_prefix(self, base_app, client_for):
        router = APIRouter(prefix="/things")

        @router.get("/count")
        async def count_things():
            return {"count": 42}

        register_all_routers(base_app, [router], prefix="/api/v2")

        async with await client_for(base_app) as client:
            response = await client.get("/api/v2/things/count")
            assert response.status_code == 200


class TestAddHealthCheck:
    async def test_health_endpoint(self, base_app, client_for):
        add_health_check(base_app)

        async with await client_for(base_app) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "service" in data


class TestAddErrorHandlers:
    async def test_404_handler(self, base_app, client_for):
        add_error_handlers(base_app)

        async with await client_for(base_app) as client:
            response = await client.get("/nonexistent/path")
            assert response.status_code == 404
            data = response.json()
            assert "error" in data

    async def test_405_handler(self, base_app, client_for):
        add_error_handlers(base_app)

        @base_app.get("/only_get")
        async def only_get():
            return {}

        async with await client_for(base_app) as client:
            response = await client.post("/only_get")
            assert response.status_code == 405
            data = response.json()
            assert "error" in data


class TestAddRateLimiting:
    def test_adds_limiter_to_state(self, base_app):
        limiter = add_rate_limiting(base_app)
        assert limiter is not None
        assert hasattr(base_app.state, "limiter")

    def test_custom_limits(self, base_app):
        limiter = add_rate_limiting(base_app, default_limits=["10 per minute"])
        assert limiter is not None


class TestSetupFastapiApp:
    async def test_sets_up_app(self, client_for):
        app = FastAPI()
        router = APIRouter(prefix="/test")

        @router.get("/ping")
        async def ping():
            return {"pong": True}

        setup_fastapi_app(
            app,
            [router],
            enable_rate_limiting=False,
            enable_cors=False,
        )

        async with await client_for(app) as client:
            response = await client.get("/api/v1/test/ping")
            assert response.status_code == 200

            response = await client.get("/health")
            assert response.status_code == 200
