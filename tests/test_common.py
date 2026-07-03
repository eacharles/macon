"""Tests for macon.common utilities."""

import pytest
from pathlib import Path
from unittest.mock import patch

from macon.common import str_to_slice, slice_to_str, handle_file, LoadType


class TestStrToSlice:
    def test_none_input(self):
        assert str_to_slice(None) is None

    def test_single_number(self):
        s = str_to_slice("5")
        assert s == slice(5, None, None)

    def test_start_stop(self):
        s = str_to_slice("1:5")
        assert s == slice(1, 5, None)

    def test_start_stop_step(self):
        s = str_to_slice("1:10:2")
        assert s == slice(1, 10, 2)

    def test_stop_only(self):
        s = str_to_slice(":5")
        assert s == slice(None, 5, None)

    def test_start_only(self):
        s = str_to_slice("5:")
        assert s == slice(5, None, None)

    def test_step_only(self):
        s = str_to_slice("::2")
        assert s == slice(None, None, 2)

    def test_empty_parts(self):
        s = str_to_slice("::")
        assert s == slice(None, None, None)

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid slice format"):
            str_to_slice("1:2:3:4")


class TestSliceToStr:
    def test_none_input(self):
        assert slice_to_str(None) is None

    def test_start_stop(self):
        result = slice_to_str(slice(1, 5, None))
        assert result == "1:5"

    def test_stop_only(self):
        result = slice_to_str(slice(None, 5, None))
        assert result == ":5"

    def test_start_only(self):
        result = slice_to_str(slice(5, None, None))
        assert result == "5:"

    def test_step(self):
        result = slice_to_str(slice(None, None, 2))
        assert result == "::2"

    def test_full(self):
        result = slice_to_str(slice(1, 10, 2))
        assert result == "1:10:2"


class TestHandleFile:
    def test_in_place(self, tmp_path):
        orig = tmp_path / "test.txt"
        orig.write_text("hello")
        result = handle_file(str(orig), "sub/test.txt", LoadType.in_place)
        assert result == Path(str(orig))

    def test_copy(self, tmp_path):
        orig = tmp_path / "source.txt"
        orig.write_text("data")
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        (archive_dir / "sub").mkdir()

        with patch("macon.common.global_config") as mock_config:
            mock_config.storage.archive = str(archive_dir)
            result = handle_file(str(orig), "sub/source.txt", LoadType.copy)
            assert result == Path("sub/source.txt")
            assert (archive_dir / "sub" / "source.txt").read_text() == "data"

    def test_link(self, tmp_path):
        orig = tmp_path / "source.txt"
        orig.write_text("linked")
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        with patch("macon.common.global_config") as mock_config:
            mock_config.storage.archive = str(archive_dir)
            result = handle_file(str(orig), "source.txt", LoadType.link)
            assert result == Path("source.txt")
            assert (archive_dir / "source.txt").is_symlink()
