"""Tests for macon.db.base — Base class, hooks, ensure_base_inheritance."""

import pytest


from macon.db.base import ensure_base_inheritance
from macon.db.test_classes import TestNamed


class TestEnsureBaseInheritance:
    def test_valid_subclass(self):
        ensure_base_inheritance(TestNamed)

    def test_invalid_class_raises(self):
        class NotAModel:
            pass

        with pytest.raises(TypeError, match="must inherit from"):
            ensure_base_inheritance(NotAModel)


class TestBaseClassMethods:
    def test_class_string_default(self):
        assert TestNamed.class_string() == "test_named"

    def test_get_pagination_limit(self):
        assert TestNamed.get_pagination_limit() == 100

    def test_get_hooks_default(self):
        hooks = TestNamed.get_hooks()
        # TestNamed doesn't override any hooks
        assert isinstance(hooks, dict)
        assert set(hooks.keys()) == {
            "pre_create",
            "after_create",
            "pre_update",
            "after_update",
            "pre_delete",
            "after_delete",
        }

    def test_to_pydantic(self, db_session):
        pass  # tested in test_db_oper


class TestBaseToPydantic:
    async def test_to_pydantic(self, db_session):
        row = TestNamed(name="pydantic_test")
        db_session.add(row)
        await db_session.flush()

        result = TestNamed.to_pydantic(row)
        assert result.name == "pydantic_test"

    async def test_to_pydantic_list(self, db_session):
        rows = [TestNamed(name=f"list_{i}") for i in range(3)]
        db_session.add_all(rows)
        await db_session.flush()

        results = TestNamed.to_pydantic_list(rows)
        assert len(results) == 3

    async def test_to_pydantic_dict(self, db_session):
        row = TestNamed(name="dict_test")
        db_session.add(row)
        await db_session.flush()

        result = TestNamed.to_pydantic_dict(row)
        assert isinstance(result, dict)
        assert result["name"] == "dict_test"
        assert "id_" in result
