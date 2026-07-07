"""Coverage tests for remote_sync/base.py and remote_async/base.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel

from macon.remote_sync.base import SyncRemoteOperations, _make_sync_method


class MockResponse(BaseModel):
    id: int
    name: str


class MockCreate(BaseModel):
    name: str


class TestMakeSyncMethod:
    def test_generated_method_calls_async_ops(self):
        method = _make_sync_method("get_row")
        assert callable(method)
        assert method.__name__ == "get_row"


class TestSyncRemoteOperationsSubclass:
    def test_extra_methods_added_to_subclass(self):
        class CustomSync(SyncRemoteOperations[MockResponse, MockCreate]):
            _extra_methods = ["load", "download"]

        assert hasattr(CustomSync, "load")
        assert hasattr(CustomSync, "download")
        assert callable(getattr(CustomSync, "load"))

    def test_extra_methods_not_overwritten_if_defined(self):
        class CustomSync(SyncRemoteOperations[MockResponse, MockCreate]):
            _extra_methods = ["load"]

            def load(self):
                return "custom"

        instance = CustomSync(async_ops=MagicMock())
        assert instance.load() == "custom"


class TestSyncMethodExecution:
    def test_sync_method_runs_async_operation(self):
        mock_async_ops = MagicMock()
        mock_async_ops.base_url = "http://localhost:8000"
        mock_async_ops.api_prefix = "/api/v1"
        mock_async_ops.table_name = "test"
        mock_async_ops.timeout = 30.0
        mock_async_ops.auth_token = None
        mock_async_ops.response_model = MockResponse
        mock_async_ops.create_model = MockCreate
        mock_async_ops.client_class = None

        # Create a mock that simulates the async context manager
        mock_client = MagicMock()
        mock_client.get_row = AsyncMock(return_value=MockResponse(id=1, name="test"))

        mock_async_ops.__aenter__ = AsyncMock(return_value=mock_async_ops)
        mock_async_ops.__aexit__ = AsyncMock(return_value=None)
        mock_async_ops.get_row = AsyncMock(return_value=MockResponse(id=1, name="test"))

        ops = SyncRemoteOperations(async_ops=mock_async_ops)
        result = ops.get_row(1)
        assert result.id == 1
        assert result.name == "test"


class TestAsyncRemoteCreateRowsBatched:
    async def test_create_rows_batched_delegates(self):
        from macon.remote_async.base import AsyncRemoteOperations

        ops = AsyncRemoteOperations(
            base_url="http://localhost:8000",
            table_name="test",
            response_model=MockResponse,
            create_model=MockCreate,
        )

        mock_client = AsyncMock()
        mock_client.create_rows_batched = AsyncMock(
            return_value=[MockResponse(id=1, name="a"), MockResponse(id=2, name="b")]
        )
        ops._client = mock_client

        result = await ops.create_rows_batched([{"name": "a"}, {"name": "b"}])
        assert len(result) == 2
        mock_client.create_rows_batched.assert_called_once()


class TestAsyncRemoteCustomClient:
    async def test_custom_client_class_used_in_get_client(self):
        from macon.remote_async.base import AsyncRemoteOperations

        class CustomClient:
            def __init__(self, client, endpoint, response_model, create_model):
                self.client = client
                self.endpoint = endpoint

        ops = AsyncRemoteOperations(
            base_url="http://localhost:8000",
            table_name="test",
            response_model=MockResponse,
            create_model=MockCreate,
            client_class=CustomClient,
        )

        import warnings

        with (
            patch("macon.remote_async.base.RemoteAPI") as MockAPI,
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", ResourceWarning)
            mock_api = MagicMock()
            mock_api.client = MagicMock()
            MockAPI.return_value = mock_api

            client = await ops.get_client()
            assert isinstance(client, CustomClient)
            assert client.endpoint == "http://localhost:8000/api/v1/test"
