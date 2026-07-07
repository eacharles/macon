"""Coverage tests for macon.client.client — lines 76-78 (custom client class)."""

from unittest.mock import MagicMock

from pydantic import BaseModel

from macon.client.client import RemoteDatabase


class MockResponse(BaseModel):
    id: int
    name: str


class MockCreate(BaseModel):
    name: str


class MockCustomClient:
    def __init__(self, client, endpoint, response_model, create_model):
        self.client = client
        self.endpoint = endpoint
        self.response_model = response_model
        self.create_model = create_model


class TestCustomClientClass:
    async def test_custom_class_instantiated(self):
        db = RemoteDatabase(
            base_url="http://localhost:8000",
            api_prefix="/api/v1",
            table_configs={
                "custom_table": (MockResponse, MockCreate, MockCustomClient),
            },
        )

        mock_api = MagicMock()
        mock_api.client = MagicMock()

        db._api = mock_api
        db._setup_clients()

        client = getattr(db, "custom_table", None)
        assert client is not None
        assert isinstance(client, MockCustomClient)
        assert client.response_model is MockResponse
        assert client.endpoint == "http://localhost:8000/api/v1/custom_table"
