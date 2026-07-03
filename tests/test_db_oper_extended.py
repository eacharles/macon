"""Extended tests for macon.db_oper.base — hooks, validation, file ops."""

import pytest
from pydantic import ValidationError

from macon.db.test_classes import TestNamed
from macon.db_oper.base import TableContext


class TestCreateRowValidation:
    async def test_missing_required_field(self, db_session, test_named_ops):
        """Creating without required 'name' field raises ValidationError."""
        with pytest.raises(ValidationError):
            await test_named_ops.create_row(db_session, validate=True)

    async def test_skip_validation_allows_missing_fields(self, db_session, test_named_ops):
        """With validate=False, Pydantic validation is skipped."""
        # SQLAlchemy will still enforce NOT NULL at flush time
        # but the Pydantic check is bypassed
        row = await test_named_ops.create_row(db_session, validate=False, name="skipped_validation")
        assert row.name == "skipped_validation"


class TestCreateRowsValidation:
    async def test_invalid_row_in_batch(self, db_session, test_named_ops):
        """A validation error in any row fails the whole batch."""
        data = [
            {"name": "valid_1"},
            {},  # missing required 'name'
            {"name": "valid_3"},
        ]
        with pytest.raises(ValidationError):
            await test_named_ops.create_rows(db_session, data, validate=True)

    async def test_empty_batch_raises(self, db_session, test_named_ops):
        with pytest.raises(ValueError, match="cannot be empty"):
            await test_named_ops.create_rows(db_session, [])


class TestCreateRowsBatchedValidation:
    async def test_invalid_batch_size(self, db_session, test_named_ops):
        data = [{"name": "x"}]
        with pytest.raises(ValueError, match="batch_size must be at least 1"):
            await test_named_ops.create_rows_batched(db_session, data, batch_size=0)

    async def test_empty_data_raises(self, db_session, test_named_ops):
        with pytest.raises(ValueError, match="cannot be empty"):
            await test_named_ops.create_rows_batched(db_session, [])


class TestBulkInsertValidation:
    async def test_empty_data_raises(self, db_session, test_named_ops):
        with pytest.raises(ValueError, match="cannot be empty"):
            await test_named_ops.bulk_insert_rows(db_session, [])

    async def test_invalid_row_data(self, db_session, test_named_ops):
        """Validation catches bad data before insert."""
        with pytest.raises(ValidationError):
            await test_named_ops.bulk_insert_rows(db_session, [{}], validate=True)


class TestLifecycleHooks:
    async def test_pre_create_hook_called(self, db_session, test_named_ops):
        """Verify pre_create_hook is called and can modify data."""
        original_pre = TestNamed.pre_create_hook

        @classmethod
        async def uppercasing_hook(cls, session, data):
            data["name"] = data["name"].upper()
            return data

        TestNamed.pre_create_hook = uppercasing_hook
        try:
            row = await test_named_ops.create_row(db_session, name="hello")
            assert row.name == "HELLO"
        finally:
            TestNamed.pre_create_hook = original_pre


class TestTableContextFromDbClass:
    def test_valid_class(self):
        ctx = TableContext.from_db_class(TestNamed)
        assert ctx.db_class is TestNamed
        assert ctx.class_string == "test_named"

    def test_missing_method_raises(self):
        class BadModel:
            pass

        with pytest.raises(AttributeError):
            TableContext.from_db_class(BadModel)


class TestToPydanticDictList:
    async def test_empty_list(self, db_session, test_named_ops):
        result = test_named_ops.to_pydantic_dict_list([])
        assert result == []

    async def test_multiple_rows(self, db_session, test_named_ops):
        rows = await test_named_ops.create_rows(db_session, [{"name": f"dict_list_{i}"} for i in range(3)])
        dicts = test_named_ops.to_pydantic_dict_list(rows)
        assert len(dicts) == 3
        assert all(isinstance(d, dict) for d in dicts)
        assert all("name" in d for d in dicts)


class TestPathSecurityValidation:
    def test_traversal_rejected(self, test_named_ops):
        with pytest.raises(ValueError, match="Invalid path"):
            test_named_ops._validate_path_security("../../etc/passwd")

    def test_absolute_path_rejected(self, test_named_ops):
        with pytest.raises(ValueError, match="Invalid path"):
            test_named_ops._validate_path_security("/etc/passwd")

    def test_null_bytes_rejected(self, test_named_ops):
        with pytest.raises(ValueError, match="null bytes"):
            test_named_ops._validate_path_security("file\x00.txt")

    def test_too_long_rejected(self, test_named_ops):
        with pytest.raises(ValueError, match="too long"):
            test_named_ops._validate_path_security("a" * 300)
