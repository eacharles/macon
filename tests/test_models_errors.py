"""Tests for Pydantic validation errors in macon.models."""

import pytest
from pydantic import ValidationError

from macon.models import (
    Filter,
    FilterOp,
    FilterRequest,
    OrderBy,
    TestNamedCreate,
    TestRefCreate,
    TestListPairCreate,
)


class TestFilterOpInvalid:
    def test_invalid_string(self):
        with pytest.raises(ValueError):
            FilterOp("invalid_operator")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            FilterOp("")


class TestFilterValidationErrors:
    def test_invalid_op_value(self):
        with pytest.raises(ValidationError):
            Filter(field="name", op="not_a_real_op", value="x")

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            Filter(op=FilterOp.EQ, value="x")

    def test_missing_op(self):
        with pytest.raises(ValidationError):
            Filter(field="name", value="x")


class TestOrderByValidationErrors:
    def test_missing_field(self):
        with pytest.raises(ValidationError):
            OrderBy(descending=True)

    def test_wrong_descending_type(self):
        # Pydantic coerces "true"/"false" strings, but non-bool-like values fail
        with pytest.raises(ValidationError):
            OrderBy(field="name", descending="not_a_bool")


class TestFilterRequestValidation:
    def test_invalid_filter_in_list(self):
        with pytest.raises(ValidationError):
            FilterRequest(filters=[{"field": "x", "op": "bad_op"}])

    def test_wrong_filters_type(self):
        with pytest.raises(ValidationError):
            FilterRequest(filters="not_a_list")


class TestTestNamedCreateErrors:
    def test_wrong_type_for_name(self):
        # Pydantic coerces many types to str; lists/dicts should fail
        with pytest.raises(ValidationError):
            TestNamedCreate(name=["not", "a", "string"])

    def test_null_name(self):
        with pytest.raises(ValidationError):
            TestNamedCreate(name=None)


class TestTestRefCreateErrors:
    def test_missing_name(self):
        with pytest.raises(ValidationError):
            TestRefCreate(ref_name="parent")

    def test_missing_ref_name(self):
        with pytest.raises(ValidationError):
            TestRefCreate(name="orphan")


class TestTestListPairCreateErrors:
    def test_missing_lists(self):
        with pytest.raises(ValidationError):
            TestListPairCreate(name="no_lists")

    def test_non_numeric_list_values(self):
        with pytest.raises(ValidationError):
            TestListPairCreate(name="bad", list_1=["a", "b"], list_2=[1.0, 2.0])
