"""Additional tests for macon.router.app — covering create_fastapi_app, CORS, lifespan, error handlers."""

from unittest.mock import patch

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from macon.router.app import (
    add_cors_middleware,
    create_fastapi_app,
    lifespan,
    setup_fastapi_app,
)


@pytest.fixture
async def client_for():
    async def _make_client(app):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    return _make_client


def _make_test_router():
    router = APIRouter(prefix="/items")

    @router.get("/list")
    async def list_items():
        return [{"id": 1}]

    return router


class TestCreateFastapiApp:
    @patch("macon.router.app.init_db")
    def test_basic_creation(self, mock_init_db):
        app = create_fastapi_app([_make_test_router()], title="Test API", version="2.0.0")
        assert app.title == "Test API"
        assert app.version == "2.0.0"
        mock_init_db.assert_called_once()

    @patch("macon.router.app.init_db")
    def test_with_cors(self, mock_init_db):
        app = create_fastapi_app(
            [_make_test_router()],
            enable_cors=True,
            cors_origins=["http://localhost:3000"],
        )
        assert app is not None

    @patch("macon.router.app.init_db")
    def test_with_rate_limiting(self, mock_init_db):
        app = create_fastapi_app(
            [_make_test_router()],
            enable_rate_limiting=True,
            rate_limits=["50 per hour"],
        )
        assert hasattr(app.state, "limiter")

    @patch("macon.router.app.init_db")
    def test_debug_mode(self, mock_init_db):
        app = create_fastapi_app([_make_test_router()], debug=True)
        assert app.debug is True

    @patch("macon.router.app.init_db")
    async def test_custom_prefix(self, mock_init_db, client_for):
        app = create_fastapi_app([_make_test_router()], api_prefix="/v2")
        async with await client_for(app) as client:
            response = await client.get("/v2/items/list")
            assert response.status_code == 200

    @patch("macon.router.app.init_db")
    async def test_health_endpoint(self, mock_init_db, client_for):
        app = create_fastapi_app([_make_test_router()])
        async with await client_for(app) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    @patch("macon.router.app.init_db")
    async def test_404_error_handler(self, mock_init_db, client_for):
        app = create_fastapi_app([_make_test_router()])
        async with await client_for(app) as client:
            response = await client.get("/nonexistent")
            assert response.status_code == 404
            assert "error" in response.json()

    @patch("macon.router.app.init_db")
    async def test_405_error_handler(self, mock_init_db, client_for):
        app = create_fastapi_app([_make_test_router()])
        async with await client_for(app) as client:
            response = await client.post("/health")
            assert response.status_code == 405
            data = response.json()
            assert data["error"] == "Method not allowed"
            assert "method" in data

    @patch("macon.router.app.init_db")
    async def test_validation_error_handler(self, mock_init_db, client_for):
        router = APIRouter(prefix="/typed")

        @router.get("/num/{val}")
        async def get_num(val: int):
            return {"val": val}

        app = create_fastapi_app([router])
        async with await client_for(app) as client:
            response = await client.get("/api/v1/typed/num/not_a_number")
            assert response.status_code == 422
            data = response.json()
            assert data["error"] == "Validation error"
            assert "details" in data


class TestAddCorsMiddleware:
    def test_default_origins(self):
        app = FastAPI()
        add_cors_middleware(app)

    def test_custom_origins(self):
        app = FastAPI()
        add_cors_middleware(app, allow_origins=["http://localhost:3000", "https://prod.example.com"])

    def test_custom_methods_and_headers(self):
        app = FastAPI()
        add_cors_middleware(
            app,
            allow_methods=["GET", "POST"],
            allow_headers=["X-Custom-Header"],
            allow_credentials=False,
        )


class TestSetupFastapiAppExtended:
    async def test_with_cors(self, client_for):
        app = FastAPI()
        setup_fastapi_app(
            app,
            [_make_test_router()],
            enable_cors=True,
            cors_origins=["http://example.com"],
        )
        async with await client_for(app) as client:
            response = await client.get("/api/v1/items/list")
            assert response.status_code == 200

    async def test_with_rate_limiting(self, client_for):
        app = FastAPI()
        setup_fastapi_app(
            app,
            [_make_test_router()],
            enable_rate_limiting=True,
            rate_limits=["100 per hour"],
        )
        assert hasattr(app.state, "limiter")

    async def test_custom_prefix(self, client_for):
        app = FastAPI()
        setup_fastapi_app(app, [_make_test_router()], api_prefix="/custom")
        async with await client_for(app) as client:
            response = await client.get("/custom/items/list")
            assert response.status_code == 200


class TestLifespan:
    async def test_lifespan_runs(self):
        app = FastAPI()
        async with lifespan(app):
            pass
