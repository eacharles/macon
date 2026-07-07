"""Coverage tests for macon.db_oper.base — lines 800-817 (path traversal), 1395-1401 (factory)."""

import pytest
from unittest.mock import patch

from macon.db.test_classes import TestNamed
from macon.db_oper.base import create_operations, TableOperations
from macon.models.test_classes import TestNamed as TestNamedResponse, TestNamedCreate


class TestCreateOperationsFactory:
    def test_creates_operations_instance(self):
        ops = create_operations(TestNamed, TestNamedResponse, TestNamedCreate)
        assert isinstance(ops, TableOperations)
        assert ops.ctx.db_class is TestNamed
        assert ops.ctx.response_class is TestNamedResponse
        assert ops.ctx.create_class is TestNamedCreate
        assert ops.ctx.class_string == "test_named"


class TestPathTraversalCheck:
    def test_traversal_blocked_when_forbid_enabled(self, tmp_path):
        from macon.db_oper.test_classes import test_table

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        # Create a symlink inside archive that points outside
        escape_link = archive_dir / "escape"
        escape_link.symlink_to(tmp_path.parent)

        with (
            patch("macon.db_oper.base.global_config") as mock_config,
            patch("macon.db_oper.base.FORBID_TRAVERSAL", new=True),
        ):
            mock_config.storage.archive = str(archive_dir)
            with pytest.raises(ValueError, match="would escape archive directory"):
                test_table._validate_path_security("escape/something.txt")

    def test_valid_path_returns_fullpath(self, tmp_path):
        from macon.db_oper.test_classes import test_table

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        (archive_dir / "data").mkdir()

        with patch("macon.db_oper.base.global_config") as mock_config:
            mock_config.storage.archive = str(archive_dir)
            result = test_table._validate_path_security("data/test.hdf5")

        assert result == (archive_dir / "data" / "test.hdf5").resolve()
