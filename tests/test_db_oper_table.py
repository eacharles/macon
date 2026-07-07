"""Tests for TestTable file-backed operations (load, read_slice)."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import tables_io

from macon.common import LoadType
from macon.db.base import Base
from macon.db import init_db, close_db
from macon.db_oper.test_classes import test_table as test_table_ops


@pytest.fixture
async def archive_dir():
    """Create a temporary archive directory and patch config to use it."""
    tmpdir = tempfile.mkdtemp()
    test_tables_dir = Path(tmpdir) / "test_tables"
    test_tables_dir.mkdir()
    with patch("macon.db_oper.test_classes.global_config") as mock_config:
        mock_config.storage.archive = tmpdir
        # Also patch the common module's config for handle_file
        with patch("macon.common.global_config") as mock_common_config:
            mock_common_config.storage.archive = tmpdir
            yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_hdf5(archive_dir):
    """Create a sample HDF5 file with known data."""
    data = {
        "col_a": np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]),
        "col_b": np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]),
    }
    filepath = archive_dir / "sample_data.hdf5"
    tables_io.write(data, str(filepath))
    return filepath


@pytest.fixture
async def table_db():
    """Initialize DB for TestTable operations."""
    db_url = "sqlite+aiosqlite://"
    init_db(db_url)
    from macon.db.session import _engine

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()


class TestGetFileLength:
    def test_returns_correct_count(self, sample_hdf5):
        length = test_table_ops.get_file_length(sample_hdf5)
        assert length == 10


class TestLoad:
    async def test_load_in_place(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="in_place_table",
            orig_path=str(sample_hdf5),
            load_type=LoadType.in_place,
            validate_file=True,
        )
        assert result.name == "in_place_table"
        assert result.n_objects == 10
        assert str(sample_hdf5) in result.path or "sample_data.hdf5" in result.path

    async def test_load_copy(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="copy_table",
            orig_path=str(sample_hdf5),
            load_type=LoadType.copy,
            validate_file=True,
        )
        assert result.name == "copy_table"
        assert result.n_objects == 10
        # Verify file was actually copied to archive
        copied_path = archive_dir / result.path
        assert copied_path.exists()

    async def test_load_link(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="link_table",
            orig_path=str(sample_hdf5),
            load_type=LoadType.link,
            validate_file=True,
        )
        assert result.name == "link_table"
        assert result.n_objects == 10
        # Verify symlink was created
        link_path = archive_dir / result.path
        assert link_path.is_symlink()

    async def test_load_no_validate(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="no_validate_table",
            orig_path=str(sample_hdf5),
            load_type=LoadType.in_place,
            validate_file=False,
            n_objects=99,
        )
        assert result.name == "no_validate_table"
        assert result.n_objects == 99

    async def test_load_nonexistent_file(self, table_db, archive_dir):
        with pytest.raises(FileNotFoundError):
            await test_table_ops.load(
                name="ghost_table",
                orig_path="/nonexistent/path/data.hdf5",
                load_type=LoadType.in_place,
                validate_file=True,
            )


class TestReadSlice:
    async def test_read_all(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="slice_all",
            orig_path=str(sample_hdf5),
            load_type=LoadType.copy,
            validate_file=True,
        )
        from macon.db.session import get_session

        async with get_session() as session:
            data = await test_table_ops.read_slice(session, result.id_, the_slice=None)
        assert "col_a" in data
        assert "col_b" in data
        assert len(data["col_a"]) == 10

    async def test_read_subset(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="slice_subset",
            orig_path=str(sample_hdf5),
            load_type=LoadType.copy,
            validate_file=True,
        )
        from macon.db.session import get_session

        async with get_session() as session:
            data = await test_table_ops.read_slice(session, result.id_, the_slice=slice(2, 5))
        assert len(data["col_a"]) == 3
        np.testing.assert_array_equal(data["col_a"], [3.0, 4.0, 5.0])
        np.testing.assert_array_equal(data["col_b"], [30.0, 40.0, 50.0])

    async def test_read_single_row(self, table_db, archive_dir, sample_hdf5):
        result = await test_table_ops.load(
            name="slice_single",
            orig_path=str(sample_hdf5),
            load_type=LoadType.copy,
            validate_file=True,
        )
        from macon.db.session import get_session

        async with get_session() as session:
            data = await test_table_ops.read_slice(session, result.id_, the_slice=slice(0, 1))
        assert len(data["col_a"]) == 1
        assert data["col_a"][0] == 1.0

    async def test_read_slice_row_not_found(self, table_db, archive_dir):
        from macon.db.session import get_session

        async with get_session() as session:
            with pytest.raises(KeyError):
                await test_table_ops.read_slice(session, 99999, the_slice=None)
