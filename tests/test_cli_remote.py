"""Tests for macon.cli.remote — Remote CLI commands using Click's CliRunner."""

from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from macon.cli.remote.base import CliRemoteOperations, handle_error, make_table_group
from macon.remote_sync.base import SyncRemoteOperations


class FakeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    col_names_for_table: ClassVar[list[str]] = ["id_", "name"]

    id_: int = Field(..., gt=0)
    name: str


class FakeCreate(BaseModel):
    name: str


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_sync_ops():
    """Create mocked SyncRemoteOperations."""
    mock = MagicMock(spec=SyncRemoteOperations)
    mock.async_ops = MagicMock()
    mock.async_ops.table_name = "test_item"
    mock.async_ops.response_model = FakeResponse
    return mock


@pytest.fixture
def cli_group(mock_sync_ops):
    """Create a click group with CliRemoteOperations registered."""

    @click.group()
    def cli():
        pass

    ops = CliRemoteOperations(mock_sync_ops, cli)
    ops.register_all_read_commands()
    ops.register_all_create_commands()
    ops.register_all_update_commands()
    ops.register_all_delete_commands()
    ops.register_all_filter_commands()
    return cli


class TestHandleError:
    def test_value_error(self, runner):
        @click.command()
        def cmd():
            handle_error(ValueError("bad value"), "doing stuff")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "bad value" in result.output

    def test_validation_error(self, runner):
        from pydantic import ValidationError

        @click.command()
        def cmd():
            try:
                FakeCreate()  # missing name
            except ValidationError as e:
                handle_error(e, "creating")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "Validation failed" in result.output


class TestRemoteReadCommands:
    def test_get_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row.return_value = FakeResponse(id_=1, name="alpha")
        result = runner.invoke(cli_group, ["get-row", "1"])
        assert result.exit_code == 0
        assert "alpha" in result.output

    def test_get_row_by_name(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_by_name.return_value = FakeResponse(id_=1, name="beta")
        result = runner.invoke(cli_group, ["get-by-name", "beta"])
        assert result.exit_code == 0
        assert "beta" in result.output

    def test_get_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]
        result = runner.invoke(cli_group, ["get-rows"])
        assert result.exit_code == 0
        assert "a" in result.output

    def test_get_row_or_none_found(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_or_none.return_value = FakeResponse(id_=1, name="found")
        result = runner.invoke(cli_group, ["get-row-if-exists", "1"])
        assert result.exit_code == 0
        assert "found" in result.output

    def test_get_row_or_none_missing(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_or_none.return_value = None
        result = runner.invoke(cli_group, ["get-row-if-exists", "999"])
        assert result.exit_code == 0
        assert "No test_item found" in result.output

    def test_count_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_rows.return_value = 99
        result = runner.invoke(cli_group, ["count"])
        assert result.exit_code == 0
        assert "99" in result.output

    def test_lookup_by_name(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.return_value = (1, FakeResponse(id_=1, name="looked"))
        result = runner.invoke(cli_group, ["lookup", "--name", "looked"])
        assert result.exit_code == 0

    def test_lookup_neither_param(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["lookup"])
        assert result.exit_code != 0

    def test_get_row_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row.side_effect = ValueError("not found")
        result = runner.invoke(cli_group, ["get-row", "999"])
        assert result.exit_code != 0
        assert "not found" in result.output


class TestRemoteCreateCommands:
    def test_create_from_fields(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="created")
        result = runner.invoke(cli_group, ["create", "name=created"])
        assert result.exit_code == 0
        assert "created" in result.output

    def test_create_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "row.json"
        json_file.write_text('{"name": "from_file"}')
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="from_file")
        result = runner.invoke(cli_group, ["create", "--from-json", str(json_file)])
        assert result.exit_code == 0
        assert "from_file" in result.output

    def test_create_bad_field_format(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["create", "no_equals"])
        assert result.exit_code != 0
        assert "KEY=VALUE" in result.output


class TestRemoteUpdateCommands:
    def test_update_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.update_row.return_value = FakeResponse(id_=1, name="updated")
        result = runner.invoke(cli_group, ["update", "1", "name=updated"])
        assert result.exit_code == 0
        assert "updated" in result.output

    def test_update_no_fields(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["update", "1"])
        assert result.exit_code != 0


class TestRemoteDeleteCommands:
    def test_delete_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_row.return_value = FakeResponse(id_=1, name="gone")
        result = runner.invoke(cli_group, ["delete", "1", "--confirm"])
        assert result.exit_code == 0
        assert "Successfully deleted" in result.output

    def test_delete_aborted(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["delete", "1"], input="n\n")
        assert result.exit_code == 0 or "Aborted" in result.output
        mock_sync_ops.delete_row.assert_not_called()


class TestRemoteFilterCommands:
    def test_filter_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="match")]
        result = runner.invoke(cli_group, ["filter", "--field", "name:eq:match"])
        assert result.exit_code == 0
        assert "match" in result.output

    def test_count_filtered(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 3
        result = runner.invoke(cli_group, ["count-filtered", "--field", "name:eq:x"])
        assert result.exit_code == 0
        assert "3" in result.output


class TestRemoteMakeTableGroup:
    def test_creates_group(self, mock_sync_ops):
        grp = make_table_group("things", mock_sync_ops, "Manage things")
        assert isinstance(grp, click.Group)
        assert "get-row" in grp.commands
        assert "create" in grp.commands
        assert "delete" in grp.commands
        assert "filter" in grp.commands


class TestTopLevelCli:
    def test_version(self, runner):
        from macon.cli.local.top import cli

        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_help(self, runner):
        from macon.cli.local.top import cli

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Administrative CLI" in result.output

    def test_remote_help(self, runner):
        from macon.cli.remote.top import cli

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "macon" in result.output.lower()
