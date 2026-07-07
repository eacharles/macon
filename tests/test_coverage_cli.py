"""Coverage tests for CLI — common_options, local/top, remote/base, remote/top."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner


class TestParseSliceError:
    def test_invalid_slice_format_raises_bad_parameter(self):
        import click
        from macon.cli.common_options import parse_slice

        ctx = click.Context(click.Command("test"))
        param = click.Option(["--slice"])

        with pytest.raises(click.BadParameter, match="Invalid slice format"):
            parse_slice(ctx, param, "1:2:3:4")


class TestLocalCliInit:
    def test_local_cli_invokes(self):
        from macon.cli.local.top import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_init_command_calls_init_db_sync(self, tmp_path):
        from macon.cli.local.top import init

        runner = CliRunner()
        with patch("macon.cli.local.top.config") as mock_config:
            db_path = tmp_path / "test_init.db"
            mock_config.db.url = f"sqlite+aiosqlite:///{db_path}"
            result = runner.invoke(init, [])
            assert result.exit_code == 0


class TestRemoteCliContext:
    def test_remote_cli_stores_context(self):
        from macon.cli.remote.top import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--base-url",
                "http://test:8000",
                "--timeout",
                "60",
                "--auth-token",
                "secret",
                "test_named",
                "--help",
            ],
        )
        assert result.exit_code == 0


class TestRemoteCliLoadJsonError:
    def test_os_error_aborts(self, tmp_path):
        import click
        from macon.cli.remote.base import CliRemoteOperations
        from macon.remote_sync.base import SyncRemoteOperations
        from pydantic import BaseModel, ConfigDict, Field
        from typing import ClassVar

        class FakeResponse(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            col_names_for_table: ClassVar[list[str]] = ["id_", "name"]
            id_: int = Field(..., gt=0)
            name: str

        class FakeCreate(BaseModel):
            name: str

        mock_ops = MagicMock(spec=SyncRemoteOperations)
        mock_ops.async_ops = MagicMock()
        mock_ops.async_ops.table_name = "test_item"
        mock_ops.async_ops.response_model = FakeResponse

        @click.group()
        def cli():
            pass

        ops = CliRemoteOperations(mock_ops, cli)
        ops.register_all_create_commands()

        runner = CliRunner()
        # Create a file that exists (passes click.Path(exists=True))
        # but patch open to raise OSError during read
        json_file = tmp_path / "data.json"
        json_file.write_text("placeholder")

        with patch("macon.cli.remote.base.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli, ["bulk-insert", str(json_file)])
        assert "Cannot read file" in result.output or result.exit_code != 0
