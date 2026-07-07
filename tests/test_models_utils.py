"""Tests for macon.models.utils — output formatting functions."""

import json

import pytest
import yaml
from pydantic import BaseModel

from macon.models.utils import (
    OutputEnum,
    display_table,
    format_output,
    output_pydantic,
)


class FakeModel(BaseModel):
    id_: int
    name: str


class TestDisplayTable:
    def test_formats_table(self):
        data = [{"id_": 1, "name": "alpha"}, {"id_": 2, "name": "beta"}]
        result = display_table(data, ["id_", "name"])
        assert "alpha" in result
        assert "beta" in result
        assert "id_" in result
        assert "name" in result

    def test_empty_data(self):
        result = display_table([], ["id_", "name"])
        assert result == ""

    def test_missing_keys(self):
        data = [{"id_": 1}]
        result = display_table(data, ["id_", "name"])
        assert "1" in result

    def test_single_row(self):
        data = [{"id_": 42, "name": "only"}]
        result = display_table(data, ["id_", "name"])
        assert "42" in result
        assert "only" in result


class TestFormatOutput:
    def test_json_format_dict(self):
        data = {"name": "Alice", "age": 25}
        result = format_output(data, OutputEnum.json)
        parsed = json.loads(result)
        assert parsed["name"] == "Alice"
        assert parsed["age"] == 25

    def test_json_format_list(self):
        data = [{"a": 1}, {"a": 2}]
        result = format_output(data, OutputEnum.json)
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_yaml_format_dict(self):
        data = {"name": "Bob", "score": 99}
        result = format_output(data, OutputEnum.yaml)
        parsed = yaml.safe_load(result)
        assert parsed["name"] == "Bob"
        assert parsed["score"] == 99

    def test_yaml_format_list(self):
        data = [{"x": 1}, {"x": 2}]
        result = format_output(data, OutputEnum.yaml)
        parsed = yaml.safe_load(result)
        assert len(parsed) == 2

    def test_table_format_raises(self):
        with pytest.raises(ValueError, match="Unknown output format"):
            format_output({"a": 1}, OutputEnum.table)


class TestOutputPydantic:
    def test_json_single(self):
        model = FakeModel(id_=1, name="test")
        result = output_pydantic(model, OutputEnum.json)
        parsed = json.loads(result)
        assert parsed[0]["id_"] == 1
        assert parsed[0]["name"] == "test"

    def test_json_list(self):
        models = [FakeModel(id_=1, name="a"), FakeModel(id_=2, name="b")]
        result = output_pydantic(models, OutputEnum.json)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "a"

    def test_yaml_single(self):
        model = FakeModel(id_=1, name="yaml_test")
        result = output_pydantic(model, OutputEnum.yaml)
        parsed = yaml.safe_load(result)
        assert parsed[0]["name"] == "yaml_test"

    def test_yaml_list(self):
        models = [FakeModel(id_=1, name="y1"), FakeModel(id_=2, name="y2")]
        result = output_pydantic(models, OutputEnum.yaml)
        parsed = yaml.safe_load(result)
        assert len(parsed) == 2

    def test_table_output(self):
        models = [FakeModel(id_=1, name="row1"), FakeModel(id_=2, name="row2")]
        result = output_pydantic(models, OutputEnum.table, col_names=["id_", "name"])
        assert "row1" in result
        assert "row2" in result
        assert "id_" in result

    def test_table_single_model(self):
        model = FakeModel(id_=5, name="single")
        result = output_pydantic(model, OutputEnum.table, col_names=["id_", "name"])
        assert "single" in result
        assert "5" in result

    def test_table_no_col_names_raises(self):
        model = FakeModel(id_=1, name="x")
        with pytest.raises(ValueError, match="column names"):
            output_pydantic(model, OutputEnum.table, col_names=None)

    def test_table_empty_list(self):
        result = output_pydantic([], OutputEnum.table, col_names=["id_", "name"])
        assert result == ""
