"""Coverage tests for macon.client.base — lines 426, 859, 1078-1091, 1116-1145."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel

from macon.client.base import RemoteTableOperations, RemoteFileOperations
from macon.models import OrderBy


class MockResponse(BaseModel):
    id: int
    name: str


class MockCreate(BaseModel):
    name: str


def _make_client_ops():
    mock_client = AsyncMock()
    ops = RemoteTableOperations.__new__(RemoteTableOperations)
    ops.client = mock_client
    ops.endpoint = "http://test/api/v1/test_table"
    ops.response_model = MockResponse
    ops.create_model = MockCreate
    ops._default_filename_prefix = "test"
    return ops, mock_client


def _make_file_ops():
    mock_client = AsyncMock()
    ops = RemoteFileOperations.__new__(RemoteFileOperations)
    ops.client = mock_client
    ops.endpoint = "http://test/api/v1/test_table"
    ops.response_model = MockResponse
    ops.create_model = MockCreate
    ops._default_filename_prefix = "test"
    return ops, mock_client


class TestLookupByName:
    async def test_lookup_with_name_param(self):
        ops, mock_client = _make_client_ops()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "data": {"id": 1, "name": "alpha"}}
        mock_client.get = AsyncMock(return_value=mock_response)

        await ops.lookup_by_id_or_name(name="alpha")

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["name"] == "alpha"


class TestFindBySingleOrderBy:
    async def test_single_order_by_object(self):
        ops, mock_client = _make_client_ops()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "alpha"}]
        mock_client.post = AsyncMock(return_value=mock_response)

        order = OrderBy(field="name", descending=False)
        await ops.find_by(order_by=order)

        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"]
        assert "order_by" in body
        assert body["order_by"]["field"] == "name"


class TestLoadMethod:
    async def test_load_posts_file_data(self):
        ops, mock_client = _make_file_ops()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 1, "name": "loaded"}
        mock_client.post = AsyncMock(return_value=mock_response)

        from macon.common import LoadType

        await ops.load(
            path=Path("/tmp/test.hdf5"),
            load_type=LoadType.copy,
            name="loaded",
        )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"]
        assert body["path"] == "/tmp/test.hdf5"
        assert body["load_type"] == "copy"
        assert body["data"] == {"name": "loaded"}


class TestDownloadMethod:
    async def test_download_writes_file(self, tmp_path):
        ops, mock_client = _make_file_ops()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-disposition": 'attachment; filename="data.hdf5"'}
        mock_response.content = b"fake file content"
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("macon.client.base.global_config") as mock_config:
            mock_config.storage.download_area = str(tmp_path)
            result = await ops.download(row_id=42)

        assert result == tmp_path / "data.hdf5"
        assert (tmp_path / "data.hdf5").read_bytes() == b"fake file content"

    async def test_download_with_output_path(self, tmp_path):
        ops, mock_client = _make_file_ops()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-disposition": 'attachment; filename="data.hdf5"'}
        mock_response.content = b"custom output"
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("macon.client.base.global_config") as mock_config:
            mock_config.storage.download_area = str(tmp_path)
            result = await ops.download(row_id=42, output_path="subdir/custom.hdf5")

        assert result == tmp_path / "subdir" / "custom.hdf5"
        assert (tmp_path / "subdir" / "custom.hdf5").read_bytes() == b"custom output"
        # Verify output_path was passed as param
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["output_path"] == "subdir/custom.hdf5"
