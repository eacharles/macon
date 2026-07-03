"""Tests for macon.db_oper.base (TableOperations)."""

import pytest
from pydantic import ValidationError

from macon.db.test_classes import TestNamed
from macon.db_oper.base import TableContext
from macon.db_oper.test_classes import (
    test_ref as test_ref_ops,
)
from macon.models import TestNamed as TestNamedModel


class TestTableContext:
    def test_from_db_class(self):
        ctx = TableContext.from_db_class(TestNamed)
        assert ctx.db_class is TestNamed
        assert ctx.class_string == "test_named"


class TestCreateRow:
    async def test_creates_row(self, db_session, test_named_ops):
        row = await test_named_ops.create_row(db_session, name="new_row")
        assert row.name == "new_row"
        assert row.id_ is not None

    async def test_validation_error(self, db_session, test_named_ops):
        with pytest.raises(ValidationError):
            await test_named_ops.create_row(db_session, validate=True)

    async def test_skip_validation(self, db_session, test_named_ops):
        row = await test_named_ops.create_row(db_session, validate=False, name="no_validate")
        assert row.name == "no_validate"


class TestCreateRows:
    async def test_batch(self, db_session, test_named_ops):
        data = [{"name": f"batch_{i}"} for i in range(3)]
        rows = await test_named_ops.create_rows(db_session, data)
        assert len(rows) == 3
        assert rows[0].name == "batch_0"

    async def test_empty_raises(self, db_session, test_named_ops):
        with pytest.raises(ValueError):
            await test_named_ops.create_rows(db_session, [])


class TestCreateRowsBatched:
    async def test_batching(self, db_session, test_named_ops):
        data = [{"name": f"batched_{i}"} for i in range(5)]
        rows = await test_named_ops.create_rows_batched(db_session, data, batch_size=2)
        assert len(rows) == 5


class TestBulkInsertRows:
    async def test_returns_count(self, db_session, test_named_ops):
        data = [{"name": f"bulk_{i}"} for i in range(10)]
        count = await test_named_ops.bulk_insert_rows(db_session, data)
        assert count == 10


class TestToPydantic:
    async def test_converts(self, db_session, test_named_ops):
        row = await test_named_ops.create_row(db_session, name="convert_me")
        pydantic_obj = test_named_ops.to_pydantic(row)
        assert isinstance(pydantic_obj, TestNamedModel)
        assert pydantic_obj.name == "convert_me"

    async def test_list(self, db_session, test_named_ops):
        data = [{"name": f"list_{i}"} for i in range(3)]
        rows = await test_named_ops.create_rows(db_session, data)
        pydantic_list = test_named_ops.to_pydantic_list(rows)
        assert len(pydantic_list) == 3
        assert all(isinstance(p, TestNamedModel) for p in pydantic_list)

    async def test_dict(self, db_session, test_named_ops):
        row = await test_named_ops.create_row(db_session, name="to_dict")
        d = test_named_ops.to_pydantic_dict(row)
        assert d["name"] == "to_dict"
        assert "id_" in d


class TestRefOperationsGetCreateKwargs:
    async def test_resolves_fk_by_name(self, db_session):
        parent = TestNamed(name="parent_row")
        db_session.add(parent)
        await db_session.flush()

        kwargs = await test_ref_ops.get_create_kwargs(db_session, ref_name="parent_row", name="child")
        assert kwargs["ref_id"] == parent.id_
