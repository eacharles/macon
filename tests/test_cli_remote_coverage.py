"""Additional unit tests for macon.cli.remote.base — covering untested command paths."""

from typing import ClassVar
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
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
    mock = MagicMock(spec=SyncRemoteOperations)
    mock.async_ops = MagicMock()
    mock.async_ops.table_name = "test_item"
    mock.async_ops.response_model = FakeResponse
    return mock


@pytest.fixture
def cli_group(mock_sync_ops):
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


class TestHandleErrorExtended:
    def test_generic_exception(self, runner):
        @click.command()
        def cmd():
            handle_error(RuntimeError("remote down"), "fetching data")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "remote down" in result.output

    def test_no_context(self, runner):
        @click.command()
        def cmd():
            handle_error(ValueError("bad"))

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "bad" in result.output


class TestCreateManyCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}, {"name": "b"}]')
        mock_sync_ops.create_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully created 2" in result.output

    def test_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{bad")

        result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "obj.json"
        json_file.write_text('{"name": "x"}')

        result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_api_error(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "x"}]')
        mock_sync_ops.create_rows.side_effect = ValueError("server rejected")

        result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "server rejected" in result.output


class TestCreateBatchedCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}, {"name": "b"}]')
        mock_sync_ops.create_rows_batched.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        result = runner.invoke(cli_group, ["create-batched", "--batch-size", "1", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully created 2" in result.output

    def test_bad_batch_size(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}]')

        result = runner.invoke(cli_group, ["create-batched", "--batch-size", "0", str(json_file)])

        assert result.exit_code != 0
        assert "Batch size" in result.output

    def test_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("not json")

        result = runner.invoke(cli_group, ["create-batched", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "obj.json"
        json_file.write_text('{"key": "val"}')

        result = runner.invoke(cli_group, ["create-batched", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_empty_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]")

        result = runner.invoke(cli_group, ["create-batched", str(json_file)])

        assert result.exit_code != 0
        assert "empty" in result.output.lower()


class TestBulkInsertCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "x"}]')
        mock_sync_ops.bulk_insert_rows.return_value = 1

        result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully inserted 1" in result.output

    def test_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("[[bad")

        result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "obj.json"
        json_file.write_text('{"a": 1}')

        result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_empty_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]")

        result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "empty" in result.output.lower()

    def test_api_error(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "x"}]')
        mock_sync_ops.bulk_insert_rows.side_effect = ValueError("timeout")

        result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "timeout" in result.output


class TestUpdateRowExtended:
    def test_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "update.json"
        json_file.write_text('{"name": "new_name"}')
        mock_sync_ops.update_row.return_value = FakeResponse(id_=1, name="new_name")

        result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code == 0
        assert "new_name" in result.output

    def test_id_change_blocked(self, runner, cli_group):
        result = runner.invoke(cli_group, ["update", "1", "id=99"])

        assert result.exit_code != 0
        assert "Cannot change row ID" in result.output

    def test_invalid_json_file(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{bad")

        result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_bad_field_format(self, runner, cli_group):
        result = runner.invoke(cli_group, ["update", "1", "no_equals"])

        assert result.exit_code != 0
        assert "KEY=VALUE" in result.output

    def test_no_data(self, runner, cli_group):
        result = runner.invoke(cli_group, ["update", "1"])

        assert result.exit_code != 0
        assert "No update data" in result.output

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.update_row.side_effect = ValueError("not found")

        result = runner.invoke(cli_group, ["update", "999", "name=x"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestUpdateManyCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text('[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]')
        mock_sync_ops.update_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully updated 2" in result.output

    def test_missing_id(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text('[{"name": "no_id"}]')

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "missing 'id'" in result.output

    def test_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text('{"id": 1, "name": "x"}')

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_empty_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]")

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "empty" in result.output.lower()

    def test_not_dict_item(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text("[1, 2, 3]")

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "not an object" in result.output


class TestDeleteRowExtended:
    def test_with_capture(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_row.return_value = FakeResponse(id_=1, name="gone")

        result = runner.invoke(cli_group, ["delete", "--confirm", "1"])

        assert result.exit_code == 0
        assert "Successfully deleted" in result.output
        assert "Deleted data" in result.output

    def test_no_capture(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_row.return_value = None

        result = runner.invoke(cli_group, ["delete", "--confirm", "--no-capture", "1"])

        assert result.exit_code == 0
        assert "Successfully deleted" in result.output

    def test_cancelled(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["delete", "1"], input="n\n")

        assert "cancelled" in result.output.lower()
        mock_sync_ops.delete_row.assert_not_called()

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_row.side_effect = ValueError("not found")

        result = runner.invoke(cli_group, ["delete", "--confirm", "999"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestDeleteManyCommand:
    def test_with_ids(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "1", "2"])

        assert result.exit_code == 0
        assert "Successfully deleted 2" in result.output

    def test_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[10, 20]")
        mock_sync_ops.delete_rows.return_value = 2

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0
        assert "Successfully deleted 2" in result.output

    def test_from_text_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("5\n6\n7\n")
        mock_sync_ops.delete_rows.return_value = 3

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0

    def test_no_ids(self, runner, cli_group):
        result = runner.invoke(cli_group, ["delete-many", "--confirm"])

        assert result.exit_code != 0
        assert "No IDs" in result.output

    def test_with_capture(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_rows.return_value = [FakeResponse(id_=1, name="del")]

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "--capture-data", "1"])

        assert result.exit_code == 0
        assert "Deleted data" in result.output

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_rows.side_effect = ValueError("server error")

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "1"])

        assert result.exit_code != 0
        assert "server error" in result.output


class TestBulkDeleteCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.bulk_delete_rows.return_value = 3

        result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "1", "2", "3"])

        assert result.exit_code == 0
        assert "Successfully deleted 3" in result.output

    def test_from_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[4, 5]")
        mock_sync_ops.bulk_delete_rows.return_value = 2

        result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0
        assert "Successfully deleted 2" in result.output

    def test_partial_delete(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.bulk_delete_rows.return_value = 1

        result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "1", "2", "3"])

        assert result.exit_code == 0
        assert "2 IDs were not found" in result.output

    def test_no_ids(self, runner, cli_group):
        result = runner.invoke(cli_group, ["bulk-delete", "--confirm"])

        assert result.exit_code != 0
        assert "No IDs" in result.output

    def test_cancelled(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["bulk-delete", "1", "2"], input="n\n")

        assert "cancelled" in result.output.lower()
        mock_sync_ops.bulk_delete_rows.assert_not_called()


class TestFilterCommandExtended:
    def test_invalid_format(self, runner, cli_group):
        result = runner.invoke(cli_group, ["filter", "--field", "badformat"])

        assert result.exit_code != 0
        assert "FIELD:OPERATOR:VALUE" in result.output

    def test_unknown_operator(self, runner, cli_group):
        result = runner.invoke(cli_group, ["filter", "--field", "name:bogus:val"])

        assert result.exit_code != 0
        assert "Unknown operator" in result.output

    def test_or_logic(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="a")]

        result = runner.invoke(cli_group, ["filter", "--field", "name:eq:a", "--field", "name:eq:b", "--or"])

        assert result.exit_code == 0
        call_kwargs = mock_sync_ops.filter_rows.call_args[1]
        assert call_kwargs["logical_op"] == "or"

    def test_with_order_by(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="sorted")]

        result = runner.invoke(cli_group, ["filter", "--field", "name:eq:sorted", "--order-by", "name:desc"])

        assert result.exit_code == 0

    def test_in_operator(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = []

        result = runner.invoke(cli_group, ["filter", "--field", "name:in:alpha,beta"])

        assert result.exit_code == 0

    def test_no_filters(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="all")]

        result = runner.invoke(cli_group, ["filter"])

        assert result.exit_code == 0

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.side_effect = ValueError("bad filter")

        result = runner.invoke(cli_group, ["filter", "--field", "name:eq:x"])

        assert result.exit_code != 0
        assert "bad filter" in result.output


class TestCountFilteredExtended:
    def test_no_filters(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 50

        result = runner.invoke(cli_group, ["count-filtered"])

        assert result.exit_code == 0
        assert "50" in result.output
        assert "all" in result.output.lower()

    def test_with_filter(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 3

        result = runner.invoke(cli_group, ["count-filtered", "--field", "name:eq:x"])

        assert result.exit_code == 0
        assert "3" in result.output
        assert "matching" in result.output.lower()

    def test_invalid_filter(self, runner, cli_group):
        result = runner.invoke(cli_group, ["count-filtered", "--field", "badformat"])

        assert result.exit_code != 0
        assert "FIELD:OPERATOR:VALUE" in result.output

    def test_unknown_operator(self, runner, cli_group):
        result = runner.invoke(cli_group, ["count-filtered", "--field", "name:bad:x"])

        assert result.exit_code != 0
        assert "Unknown operator" in result.output

    def test_or_logic(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 7

        result = runner.invoke(
            cli_group, ["count-filtered", "--field", "name:eq:a", "--field", "name:eq:b", "--or"]
        )

        assert result.exit_code == 0
        call_kwargs = mock_sync_ops.count_filtered_rows.call_args[1]
        assert call_kwargs["logical_op"] == "or"


class TestFindByCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = [FakeResponse(id_=1, name="match")]

        result = runner.invoke(cli_group, ["find-by", "name=match"])

        assert result.exit_code == 0
        assert "match" in result.output

    def test_no_conditions(self, runner, cli_group):
        result = runner.invoke(cli_group, ["find-by"])

        assert result.exit_code != 0
        assert "No conditions" in result.output

    def test_with_order_by(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = []

        result = runner.invoke(cli_group, ["find-by", "--order-by", "name:desc", "name=x"])

        assert result.exit_code == 0

    def test_with_pagination(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = []

        result = runner.invoke(cli_group, ["find-by", "--skip", "5", "--limit", "10", "name=x"])

        assert result.exit_code == 0

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.side_effect = ValueError("bad field")

        result = runner.invoke(cli_group, ["find-by", "name=x"])

        assert result.exit_code != 0
        assert "bad field" in result.output


class TestFindOneByCommand:
    def test_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_one_by.return_value = FakeResponse(id_=1, name="unique")

        result = runner.invoke(cli_group, ["find-one-by", "name=unique"])

        assert result.exit_code == 0
        assert "unique" in result.output

    def test_no_conditions(self, runner, cli_group):
        result = runner.invoke(cli_group, ["find-one-by"])

        assert result.exit_code != 0
        assert "No conditions" in result.output

    def test_invalid_format(self, runner, cli_group):
        result = runner.invoke(cli_group, ["find-one-by", "no_equals"])

        assert result.exit_code != 0
        assert "KEY=VALUE" in result.output

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_one_by.side_effect = ValueError("not found")

        result = runner.invoke(cli_group, ["find-one-by", "name=ghost"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestLookupExtended:
    def test_by_id(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.return_value = (1, FakeResponse(id_=1, name="found"))

        result = runner.invoke(cli_group, ["lookup", "--id", "1"])

        assert result.exit_code == 0

    def test_both_args(self, runner, cli_group):
        result = runner.invoke(cli_group, ["lookup", "--id", "1", "--name", "x"])

        assert result.exit_code != 0

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.side_effect = ValueError("not found")

        result = runner.invoke(cli_group, ["lookup", "--name", "ghost"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestGetRowsExtended:
    def test_with_pagination(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.return_value = [FakeResponse(id_=1, name="paged")]

        result = runner.invoke(cli_group, ["get-rows", "--skip", "2", "--limit", "5"])

        assert result.exit_code == 0
        mock_sync_ops.get_rows.assert_called_once_with(skip=2, limit=5)

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.side_effect = ValueError("timeout")

        result = runner.invoke(cli_group, ["get-rows"])

        assert result.exit_code != 0
        assert "timeout" in result.output


class TestCreateRowExtended:
    def test_no_data(self, runner, cli_group):
        result = runner.invoke(cli_group, ["create"])

        assert result.exit_code != 0
        assert "No data provided" in result.output

    def test_json_value_parsing(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="parsed")

        result = runner.invoke(cli_group, ["create", 'name="parsed"'])

        assert result.exit_code == 0
        call_kwargs = mock_sync_ops.create_row.call_args[1]
        assert call_kwargs["name"] == "parsed"

    def test_api_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.side_effect = ValueError("validation failed")

        result = runner.invoke(cli_group, ["create", "name=bad"])

        assert result.exit_code != 0
        assert "validation failed" in result.output


class TestMakeTableGroupExtended:
    def test_creates_all_commands(self, mock_sync_ops):
        factory = MagicMock(return_value=mock_sync_ops)
        grp = make_table_group("items", factory, "Manage items")

        assert isinstance(grp, click.Group)
        command_names = list(grp.commands.keys())
        assert "get-row" in command_names
        assert "create" in command_names
        assert "update" in command_names
        assert "delete" in command_names
        assert "filter" in command_names
        assert "find-by" in command_names
        assert "bulk-delete" in command_names
        factory.assert_called_once()


class TestPaginationValidation:
    def test_get_rows_negative_skip(self, runner, cli_group):
        result = runner.invoke(cli_group, ["get-rows", "--skip", "-1"])

        assert result.exit_code != 0
        assert "skip" in result.output.lower()

    def test_filter_negative_skip(self, runner, cli_group):
        result = runner.invoke(cli_group, ["filter", "--skip", "-1"])

        assert result.exit_code != 0
        assert "skip" in result.output.lower()

    def test_find_by_negative_skip(self, runner, cli_group, mock_sync_ops):
        result = runner.invoke(cli_group, ["find-by", "--skip", "-1", "name=x"])

        assert result.exit_code != 0
        assert "skip" in result.output.lower()


class TestOSErrorOnFiles:
    def test_create_from_json_oserror(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('{"name": "x"}')

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["create", "--from-json", str(json_file)])

        assert result.exit_code != 0
        assert "Cannot read file" in result.output

    def test_create_many_oserror(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('[{"name": "x"}]')

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "Cannot read file" in result.output

    def test_create_batched_oserror(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('[{"name": "x"}]')

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["create-batched", str(json_file)])

        assert result.exit_code != 0
        assert "Cannot read file" in result.output

    def test_update_from_json_oserror(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('{"name": "x"}')

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code != 0
        assert "Cannot read file" in result.output

    def test_update_many_oserror(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "data.json"
        json_file.write_text('[{"id": 1, "name": "x"}]')

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "Cannot read file" in result.output


class TestDeleteFromFileErrors:
    def test_delete_many_from_text_file_fallback(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("1\n2\n3\n")
        mock_sync_ops.delete_rows.return_value = 3

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0

    def test_delete_many_from_file_oserror(self, runner, cli_group, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[1, 2]")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code != 0
        assert "Error reading file" in result.output

    def test_bulk_delete_from_text_file_fallback(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("10\n20\n")
        mock_sync_ops.bulk_delete_rows.return_value = 2

        result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0

    def test_bulk_delete_from_file_oserror(self, runner, cli_group, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[1]")

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code != 0
        assert "Error reading file" in result.output


class TestFromJsonDecodeErrors:
    def test_create_from_json_invalid(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{not valid json")

        result = runner.invoke(cli_group, ["create", "--from-json", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_update_from_json_invalid(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{not valid")

        result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_update_many_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("not json at all")

        result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output


class TestDeleteFromFileNonArray:
    def test_delete_many_non_array_json(self, runner, cli_group, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text('{"not": "an array"}')

        result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code != 0
        assert "Error reading file" in result.output

    def test_bulk_delete_non_array_json(self, runner, cli_group, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text('{"not": "an array"}')

        result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code != 0
        assert "Error reading file" in result.output


class TestCountFilteredInOperator:
    def test_in_operator(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 2

        result = runner.invoke(cli_group, ["count-filtered", "--field", "name:in:alpha,beta"])

        assert result.exit_code == 0
        assert "2" in result.output
