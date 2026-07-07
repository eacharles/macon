"""Coverage tests for macon.db.base — lines 94, 461-463, 526-528, 596-598."""

from unittest.mock import AsyncMock, MagicMock

from macon.db.base import Base
from macon.db.test_classes import TestNamed


class TestClassString:
    def test_class_string_default_returns_class_name(self):
        result = Base.class_string()
        assert result == "Base"


class TestAfterCreateHook:
    async def test_default_after_create_hook(self):
        session = AsyncMock()
        row = MagicMock()
        result = await TestNamed.after_create_hook(session, row)
        assert result is None


class TestPreUpdateHook:
    async def test_default_pre_update_hook_returns_data(self):
        session = AsyncMock()
        row = MagicMock()
        data = {"name": "updated"}
        result = await TestNamed.pre_update_hook(session, row, data)
        assert result == {"name": "updated"}


class TestAfterUpdateHook:
    async def test_default_after_update_hook(self):
        session = AsyncMock()
        row = MagicMock()
        result = await TestNamed.after_update_hook(session, row, {"name"})
        assert result is None
