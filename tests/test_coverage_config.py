"""Coverage tests for macon.config — lines 162-166, 219, 251-253."""

import pytest

from macon.config import LoggingConfiguration, DatabaseConfiguration, StorageConfiguration


class TestLogLevelValidation:
    def test_invalid_log_level_raises(self):
        with pytest.raises(ValueError):
            LoggingConfiguration(level="INVALID")

    def test_valid_log_level_normalizes(self):
        config = LoggingConfiguration(level="debug")
        assert config.level == "DEBUG"


class TestDatabaseUrlValidation:
    def test_invalid_scheme_raises(self):
        with pytest.raises(ValueError):
            DatabaseConfiguration(url="badscheme://localhost/db")

    def test_valid_sqlite_url(self):
        config = DatabaseConfiguration(url="sqlite+aiosqlite:///test.db")
        assert config.url == "sqlite+aiosqlite:///test.db"


class TestStoragePathValidation:
    def test_nonexistent_path_raises(self, tmp_path):
        bad_path = str(tmp_path / "nonexistent_dir")
        with pytest.raises(ValueError):
            StorageConfiguration(archive=bad_path, import_area=str(tmp_path), download_area=str(tmp_path))
