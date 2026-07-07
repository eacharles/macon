"""Additional unit tests for macon.cli.local.base — covering untested command paths."""

from typing import ClassVar
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from macon.cli.local.base import CliOperations, handle_database_error


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
    mock_ctx = MagicMock()
    mock_ctx.class_string = "test_item"
    mock_ctx.response_class = FakeResponse
    mock_ctx.create_class = FakeCreate

    mock = MagicMock()
    mock.async_ops._table_ops.ctx = mock_ctx
    return mock


@pytest.fixture
def cli_group(mock_sync_ops):
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


class TestHandleDatabaseErrorExtended:
    def test_integrity_error(self, runner):
        @click.command()
        def cmd():
            exc = IntegrityError("INSERT", {}, Exception("UNIQUE constraint"))
            handle_database_error(exc, "creating item")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "Integrity constraint" in result.output

    def test_generic_exception(self, runner):
        @click.command()
        def cmd():
            handle_database_error(RuntimeError("something broke"), "doing stuff")

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "something broke" in result.output

    def test_no_context(self, runner):
        @click.command()
        def cmd():
            handle_database_error(ValueError("oops"))

        result = runner.invoke(cmd)
        assert result.exit_code != 0
        assert "oops" in result.output


class TestCreateManyCommand:
    def test_create_many_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}, {"name": "b"}]')
        mock_sync_ops.create_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully created 2" in result.output

    def test_create_many_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("not valid json{{{")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_create_many_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "obj.json"
        json_file.write_text('{"name": "single"}')

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_create_many_db_error(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "dup"}]')
        mock_sync_ops.create_rows.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-many", str(json_file)])

        assert result.exit_code != 0
        assert "Integrity constraint" in result.output


class TestCreateBatchedCommand:
    def test_create_batched_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}, {"name": "b"}, {"name": "c"}]')
        mock_sync_ops.create_rows_batched.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
            FakeResponse(id_=3, name="c"),
        ]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-batched", "--batch-size", "2", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully created 3" in result.output

    def test_create_batched_bad_batch_size(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "a"}]')

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-batched", "--batch-size", "0", str(json_file)])

        assert result.exit_code != 0
        assert "at least 1" in result.output.lower() or "Batch size" in result.output

    def test_create_batched_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{bad json")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create-batched", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output


class TestBulkInsertCommand:
    def test_bulk_insert_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "x"}, {"name": "y"}]')
        mock_sync_ops.bulk_insert_rows.return_value = 2

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully inserted 2" in result.output

    def test_bulk_insert_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("[[invalid")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_bulk_insert_db_error(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "rows.json"
        json_file.write_text('[{"name": "x"}]')
        mock_sync_ops.bulk_insert_rows.side_effect = ValueError("bad data")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-insert", str(json_file)])

        assert result.exit_code != 0
        assert "bad data" in result.output


class TestUpdateRowExtended:
    def test_update_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "update.json"
        json_file.write_text('{"name": "updated_name"}')
        mock_sync_ops.update_row.return_value = FakeResponse(id_=1, name="updated_name")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code == 0
        assert "updated_name" in result.output

    def test_update_id_change_blocked(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "1", "id=99"])

        assert result.exit_code != 0
        assert "Cannot change row ID" in result.output

    def test_update_invalid_json_file(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("not json")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "--from-json", str(json_file), "1"])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output

    def test_update_db_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.update_row.side_effect = KeyError("not found")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update", "999", "name=x"])

        assert result.exit_code != 0


class TestUpdateManyCommand:
    def test_update_many_happy_path(self, runner, cli_group, mock_sync_ops, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text('[{"id": 1, "name": "new_a"}, {"id": 2, "name": "new_b"}]')
        mock_sync_ops.update_rows.return_value = [
            FakeResponse(id_=1, name="new_a"),
            FakeResponse(id_=2, name="new_b"),
        ]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code == 0
        assert "Successfully updated 2" in result.output

    def test_update_many_missing_id(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text('[{"name": "no_id"}]')

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "missing 'id'" in result.output

    def test_update_many_not_array(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "updates.json"
        json_file.write_text('{"id": 1, "name": "x"}')

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "array" in result.output.lower()

    def test_update_many_invalid_json(self, runner, cli_group, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("bad{")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["update-many", str(json_file)])

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output


class TestDeleteManyCommand:
    def test_delete_many_with_ids(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_rows.return_value = None

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "--confirm", "1", "2", "3"])

        assert result.exit_code == 0
        assert "Successfully deleted 3" in result.output

    def test_delete_many_from_json_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[10, 20, 30]")
        mock_sync_ops.delete_rows.return_value = None

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0
        assert "Successfully deleted 3" in result.output

    def test_delete_many_from_text_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("5\n6\n7\n")
        mock_sync_ops.delete_rows.return_value = None

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0
        assert "Successfully deleted 3" in result.output

    def test_delete_many_no_ids(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "--confirm"])

        assert result.exit_code != 0
        assert "No IDs" in result.output

    def test_delete_many_cancelled(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "1", "2"], input="n\n")

        assert "cancelled" in result.output.lower() or result.exit_code == 0
        mock_sync_ops.delete_rows.assert_not_called()

    def test_delete_many_with_capture(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.delete_rows.return_value = [{"id_": 1, "name": "del1"}, {"id_": 2, "name": "del2"}]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["delete-many", "--confirm", "--capture-data", "1", "2"])

        assert result.exit_code == 0
        assert "Deleted data" in result.output


class TestBulkDeleteCommand:
    def test_bulk_delete_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.bulk_delete_rows.return_value = 3

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "1", "2", "3"])

        assert result.exit_code == 0
        assert "Successfully deleted 3" in result.output

    def test_bulk_delete_from_file(self, runner, cli_group, mock_sync_ops, tmp_path):
        ids_file = tmp_path / "ids.json"
        ids_file.write_text("[4, 5]")
        mock_sync_ops.bulk_delete_rows.return_value = 2

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "--from-file", str(ids_file)])

        assert result.exit_code == 0
        assert "Successfully deleted 2" in result.output

    def test_bulk_delete_partial(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.bulk_delete_rows.return_value = 1

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-delete", "--confirm", "1", "2", "3"])

        assert result.exit_code == 0
        assert "2 IDs were not found" in result.output

    def test_bulk_delete_cancelled(self, runner, cli_group, mock_sync_ops):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["bulk-delete", "1", "2"], input="n\n")

        assert "cancelled" in result.output.lower() or result.exit_code == 0
        mock_sync_ops.bulk_delete_rows.assert_not_called()


class TestFilterCommandExtended:
    def test_filter_invalid_format(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter", "--field", "name_eq_value"])

        assert result.exit_code != 0
        assert "FIELD:OPERATOR:VALUE" in result.output

    def test_filter_unknown_operator(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter", "--field", "name:badop:val"])

        assert result.exit_code != 0
        assert "Unknown operator" in result.output

    def test_filter_with_order_by(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="sorted")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(
                cli_group, ["filter", "--field", "name:eq:sorted", "--order-by", "name:desc"]
            )

        assert result.exit_code == 0
        assert "sorted" in result.output

    def test_filter_or_logic(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [
            FakeResponse(id_=1, name="a"),
            FakeResponse(id_=2, name="b"),
        ]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(
                cli_group, ["filter", "--field", "name:eq:a", "--field", "name:eq:b", "--or"]
            )

        assert result.exit_code == 0
        mock_sync_ops.filter_rows.assert_called_once()
        call_kwargs = mock_sync_ops.filter_rows.call_args[1]
        assert call_kwargs["logical_op"] == "or"

    def test_filter_in_operator(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="a")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter", "--field", "name:in:alpha,beta,gamma"])

        assert result.exit_code == 0

    def test_filter_no_filters(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.return_value = [FakeResponse(id_=1, name="all")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter"])

        assert result.exit_code == 0

    def test_filter_db_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.filter_rows.side_effect = ValueError("bad filter")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["filter", "--field", "name:eq:x"])

        assert result.exit_code != 0
        assert "bad filter" in result.output


class TestFindByCommand:
    def test_find_by_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = [FakeResponse(id_=1, name="found")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-by", "name=found"])

        assert result.exit_code == 0
        assert "found" in result.output

    def test_find_by_no_conditions(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-by"])

        assert result.exit_code != 0
        assert "No conditions" in result.output

    def test_find_by_invalid_format(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-by", "no_equals"])

        assert result.exit_code != 0
        assert "KEY=VALUE" in result.output

    def test_find_by_with_order(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = [FakeResponse(id_=1, name="ordered")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-by", "--order-by", "name", "name=ordered"])

        assert result.exit_code == 0

    def test_find_by_with_pagination(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_by.return_value = []

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-by", "--skip", "5", "--limit", "10", "name=x"])

        assert result.exit_code == 0


class TestFindOneByCommand:
    def test_find_one_by_happy_path(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_one_by.return_value = FakeResponse(id_=1, name="unique")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-one-by", "name=unique"])

        assert result.exit_code == 0
        assert "unique" in result.output

    def test_find_one_by_no_conditions(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-one-by"])

        assert result.exit_code != 0
        assert "No conditions" in result.output

    def test_find_one_by_not_found(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.find_one_by.side_effect = KeyError("No item found")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["find-one-by", "name=ghost"])

        assert result.exit_code != 0


class TestLookupExtended:
    def test_lookup_by_name(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.return_value = FakeResponse(id_=1, name="looked")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["lookup", "--name", "looked"])

        assert result.exit_code == 0

    def test_lookup_both_args(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["lookup", "--id", "1", "--name", "x"])

        assert result.exit_code != 0

    def test_lookup_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.lookup_by_id_or_name.side_effect = KeyError("not found")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["lookup", "--name", "ghost"])

        assert result.exit_code != 0


class TestGetRowsExtended:
    def test_get_rows_with_pagination(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.return_value = [FakeResponse(id_=1, name="paged")]

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-rows", "--skip", "2", "--limit", "5"])

        assert result.exit_code == 0
        mock_sync_ops.get_rows.assert_called_once_with(skip=2, limit=5)

    def test_get_rows_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.get_rows.side_effect = RuntimeError("db offline")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["get-rows"])

        assert result.exit_code != 0
        assert "db offline" in result.output


class TestCreateRowExtended:
    def test_create_no_data(self, runner, cli_group):
        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create"])

        assert result.exit_code != 0
        assert "No data provided" in result.output

    def test_create_json_value_parsing(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.return_value = FakeResponse(id_=1, name="parsed")

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create", 'name="parsed"'])

        assert result.exit_code == 0
        mock_sync_ops.create_row.assert_called_once()
        call_kwargs = mock_sync_ops.create_row.call_args[1]
        assert call_kwargs["name"] == "parsed"

    def test_create_db_error(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.create_row.side_effect = IntegrityError("INSERT", {}, Exception("dup"))

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["create", "name=dup"])

        assert result.exit_code != 0
        assert "Integrity constraint" in result.output


class TestCountFilteredExtended:
    def test_count_filtered_no_filters(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 100

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(cli_group, ["count-filtered"])

        assert result.exit_code == 0
        assert "100" in result.output
        assert "all" in result.output.lower()

    def test_count_filtered_or_logic(self, runner, cli_group, mock_sync_ops):
        mock_sync_ops.count_filtered_rows.return_value = 5

        with patch("macon.cli.local.base.init_db"):
            result = runner.invoke(
                cli_group, ["count-filtered", "--field", "name:eq:a", "--field", "name:eq:b", "--or"]
            )

        assert result.exit_code == 0
        call_kwargs = mock_sync_ops.count_filtered_rows.call_args[1]
        assert call_kwargs["logical_op"] == "or"
