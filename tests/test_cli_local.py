"""Tests for macon.cli.local — CLI commands using Click's CliRunner."""

import json
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from macon.cli.local.base import CliOperations, handle_database_error, make_table_group


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
    """Create mocked SyncOperations with a realistic ctx."""
    mock_ctx = MagicMock()
    mock_ctx.class_string = "test_item"
    mock_ctx.response_class = FakeResponse
    mock_ctx.create_class = FakeCreate

    mock = MagicMock()
    mock.async_ops._table_ops.ctx = mock_ctx
    return mock


@pytest.fixture
def cli_group(mock_sync_ops):
    """Create a click group with CliOperations registered."""

    @click.group()
    def cli():
        pass

    ops = CliOperations(mock_sync_ops, cli)
    ops.register_all_read_commands()
    ops.register_all_create_commands()
    ops.register_all_update_commands()
    ops.register_all_delete_commands()
    ops.register_all_filter_commands()
    return cli


class TestHandleDatabaseError:
    def test_validation_error(self, runner):
        from pydantic import ValidationError

        @click.command()
        def cmd():
            try:
                FakeCreate()  # missing name
            except ValidationError as e:
                handle_database_error(e, "creating item")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "Validation failed" in result.output

    def test_value_error(self, runner):
        @click.command()
        def cmd():
            handle_database_error(ValueError("bad input"), "processing")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "bad input" in result.output


class TestReadCommands:
    def test_get_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row.return_value = FakeResponse(id_=1, name="alpha")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-row", "1"])

        assert result.exit_code == 0
        assert "alpha" in result.output

    def test_get_row_by_name(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_by_name.return_value = FakeResponse(id_=1, name="beta")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-by-name", "beta"])

        assert result.exit_code == 0
        assert "beta" in result.output

    def test_get_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-rows"])

        assert result.exit_code == 0
        assert "a" in result.output
        assert "b" in result.output

    def test_get_row_or_none_found(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_or_none.return_value = FakeResponse(id_=1, name="found")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-row-if-exists", "1"])

        assert result.exit_code == 0
        assert "found" in result.output

    def test_get_row_or_none_missing(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row_or_none.return_value = None

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-row-if-exists", "999"])

        assert result.exit_code == 0
        assert "No test_item found" in result.output

    def test_count_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_rows.return_value = 42

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["count"])

        assert result.exit_code == 0
        assert "42" in result.output

    def test_lookup_by_id(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.return_value = FakeResponse(id_=1, name="looked")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["lookup", "--id", "1"])

        assert result.exit_code == 0

    def test_lookup_requires_one_arg(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["lookup"])

        assert result.exit_code != 0
        assert "exactly one" in result.output.lower() or "Aborted" in result.output

    def test_get_row_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row.side_effect = KeyError("not found")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-row", "999"])

        assert result.exit_code != 0


class TestCreateCommands:
    def test_create_from_fields(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="new_item")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create", "name=new_item"])

        assert result.exit_code == 0
        assert "new_item" in result.output

    def test_create_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "row.json"
        json_file.write_text('{"name": "from_file"}')
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="from_file")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create", "--from-json", str(json_file)])

        assert result.exit_code == 0
        assert "from_file" in result.output

    def test_create_bad_field_format(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create", "no_equals_sign"])

        assert result.exit_code != 0
        assert "KEY=VALUE" in result.output


class TestUpdateCommands:
    def test_update_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.update_row.return_value = FakeResponse(id_=1, name="updated")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "1", "name=updated"])

        assert result.exit_code == 0
        assert "updated" in result.output

    def test_update_no_fields(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "1"])

        assert result.exit_code != 0
        assert "at least one" in result.output.lower() or "Aborted" in result.output


class TestDeleteCommands:
    def test_delete_row(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_row.return_value = {"id_": 1, "name": "gone"}

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete", "1", "--confirm"])

        assert result.exit_code == 0
        assert "Successfully deleted" in result.output

    def test_delete_row_aborted(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete", "1"], input="n\n")

        assert result.exit_code == 0 or "Aborted" in result.output
        mock_sync_ops.delete_row.assert_not_called()


class TestFilterCommands:
    def test_filter_rows(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="match")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter", "--field", "name:eq:match"])

        assert result.exit_code == 0
        assert "match" in result.output

    def test_count_filtered(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 7

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(
                cli_group,
                ["count-filtered", "--field", "name:eq:alpha"],
            )

        assert result.exit_code == 0
        assert "7" in result.output


class TestMakeTableGroup:
    def test_creates_group_with_commands(self, mock_sync_ops):
        grp = make_table_group("items", mock_sync_ops, "Manage items")
        assert isinstance(grp, click.Group)
        command_names = list(grp.commands.keys())
        assert "get-row" in command_names
        assert "create" in command_names
        assert "delete" in command_names
        assert "filter" in command_names


class TestOutputFormats:
    def test_json_output(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_row.return_value = FakeResponse(id_=1, name="json_test")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-row", "--output", "json", "1"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]["name"] == "json_test"
