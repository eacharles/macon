"""Tests for macon.models Pydantic models."""

import pytest
from pydantic import ValidationError

from macon.models import (
    Filter,
    FilterOp,
    OrderBy,
    CountResponse,
    DeleteResponse,
    FilterRequest,
    LookupResponse,
    TestNamed,
    TestNamedCreate,
    TestRef,
    TestRefCreate,
    TestListPairCreate,
)


class TestFilterOp:
    def test_all_values_accessible(self):
        assert FilterOp.EQ == "eq"
        assert FilterOp.NE == "ne"
        assert FilterOp.LT == "lt"
        assert FilterOp.LE == "le"
        assert FilterOp.GT == "gt"
        assert FilterOp.GE == "ge"
        assert FilterOp.IN == "in"
        assert FilterOp.NOT_IN == "not_in"
        assert FilterOp.LIKE == "like"
        assert FilterOp.IS_NULL == "is_null"
        assert FilterOp.BETWEEN == "between"


class TestFilter:
    def test_construction(self):
        f = Filter(field="name", op=FilterOp.EQ, value="test")
        assert f.field == "name"
        assert f.op == FilterOp.EQ
        assert f.value == "test"

    def test_repr(self):
        f = Filter(field="age", op=FilterOp.GT, value=18)
        assert "age" in repr(f)
        assert "gt" in repr(f)

    def test_no_value(self):
        f = Filter(field="deleted_at", op=FilterOp.IS_NULL)
        assert f.value is None


class TestOrderBy:
    def test_default_ascending(self):
        o = OrderBy(field="name")
        assert o.descending is False

    def test_descending(self):
        o = OrderBy(field="created_at", descending=True)
        assert o.descending is True

    def test_repr(self):
        o = OrderBy(field="name", descending=False)
        assert "ASC" in repr(o)


class TestWebModels:
    def test_count_response(self):
        r = CountResponse(count=42)
        assert r.count == 42

    def test_delete_response(self):
        r = DeleteResponse()
        assert r.deleted is True

    def test_lookup_response(self):
        r = LookupResponse[TestNamed](id=1, data=TestNamed(id_=1, name="x"))
        assert r.id == 1
        assert r.data.name == "x"

    def test_filter_request_defaults(self):
        r = FilterRequest()
        assert r.filters == []
        assert r.logical_op == "and"
        assert r.skip == 0
        assert r.limit is None


class TestTestNamedModels:
    def test_create(self):
        m = TestNamedCreate(name="test_row")
        assert m.name == "test_row"

    def test_response(self):
        m = TestNamed(id_=1, name="test_row")
        assert m.id_ == 1
        assert m.name == "test_row"

    def test_create_missing_name(self):
        with pytest.raises(ValidationError):
            TestNamedCreate()


class TestTestRefModels:
    def test_create(self):
        m = TestRefCreate(name="ref_row", ref_name="parent")
        assert m.ref_name == "parent"

    def test_response(self):
        m = TestRef(id_=1, name="ref_row", ref_id=5)
        assert m.ref_id == 5


class TestTestListPairModels:
    def test_create_valid(self):
        m = TestListPairCreate(name="pair", list_1=[1.0, 2.0], list_2=[3.0, 4.0])
        assert len(m.list_1) == 2

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            TestListPairCreate(name="pair", list_1=[], list_2=[1.0])

    def test_different_lengths_rejected(self):
        with pytest.raises(ValidationError):
            TestListPairCreate(name="pair", list_1=[1.0, 2.0], list_2=[3.0])
