"""Coverage tests for macon.db.session — lines 33, 65."""

import pytest
from unittest.mock import patch

import macon.db.session as session_module


class TestInitDbConfigFallback:
    def test_uses_global_config_when_no_url(self):
        original_engine = session_module._engine
        original_factory = session_module._async_session_factory
        session_module._engine = None
        session_module._async_session_factory = None

        try:
            with patch.object(session_module, "global_config") as mock_config:
                mock_config.db.url = "sqlite+aiosqlite://"
                session_module.init_db()
            assert session_module._engine is not None
        finally:
            session_module._engine = original_engine
            session_module._async_session_factory = original_factory


class TestGetSessionNotInitialized:
    async def test_raises_runtime_error_before_init(self):
        original_factory = session_module._async_session_factory
        session_module._async_session_factory = None

        try:
            with pytest.raises(RuntimeError):
                async with session_module.get_session():
                    pass
        finally:
            session_module._async_session_factory = original_factory
