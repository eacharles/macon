"""Common utilities and functions"""

import shutil
from enum import Enum
from pathlib import Path
from typing import Any

from .config import config as global_config


class LoadType(Enum):
    """How to load the file."""

    in_place = "in_place"
    link = "link"
    copy = "copy"


def unexpected(condition: Any) -> Any:
    """A simple wrapper to mark evaluations that we don't expected to fail"""
    return condition


def copy_file_to_archive(
    orig_path: str | Path,
    relative_path: str | Path,
) -> Path:
    """
    Copy a file to the archive directory.

    This function copies a file from its original location to a specified
    relative path within the configured archive directory, preserving metadata
    (timestamps, permissions, etc.).

    Parameters
    ----------
    orig_path
        Path to the original file to be copied
    relative_path
        Relative path within the archive directory where the file should be copied

    Returns
    -------
        The relative path where the file was copied (same as input relative_path)

    Raises
    ------
    FileNotFoundError
        If the original file does not exist
    PermissionError
        If there are insufficient permissions to read the source or write to the destination
    OSError
        If there are other filesystem-related errors during the copy operation

    Notes
    -----
    Uses shutil.copy2 to preserve file metadata including modification time,
    access time, and permission bits.
    """
    archive_dir = Path(global_config.storage.archive)
    shutil.copy2(orig_path, archive_dir / relative_path)
    return Path(relative_path)


def link_file_to_archive(
    orig_path: str | Path,
    relative_path: str | Path,
) -> Path:
    """
    Create a symbolic link to a file in the archive directory.

    This function creates a symbolic link at a specified relative path within
    the configured archive directory that points to the original file location.
    This is useful for avoiding data duplication when the original file should
    remain in its current location.

    Parameters
    ----------
    orig_path
        Path to the original file to be linked
    relative_path
        Relative path within the archive directory where the symlink should be created

    Returns
    -------
        The relative path where the symlink was created (same as input relative_path)

    Raises
    ------
    FileExistsError
        If a file or link already exists at the target path
    PermissionError
        If there are insufficient permissions to create the symlink
    OSError
        If there are other filesystem-related errors during the link operation

    Notes
    -----
    The symlink points to orig_path, which can be either an absolute or relative path.
    If using a relative path for orig_path, it should be relative to the location
    of the symlink (archive_dir / relative_path), not the current working directory.
    """
    archive_dir = Path(global_config.storage.archive)
    full_path = archive_dir / relative_path
    full_path.symlink_to(orig_path)
    return Path(relative_path)


def handle_file(
    orig_path: str | Path,
    relative_path: str | Path,
    load_type: LoadType,
) -> Path:
    if load_type == LoadType.in_place:
        return Path(orig_path)
    if load_type == LoadType.link:
        return link_file_to_archive(orig_path, relative_path)
    if load_type == LoadType.copy:
        return copy_file_to_archive(orig_path, relative_path)
    raise AssertionError(f"Unknown load_type {load_type}")


def str_to_slice(value: str | None) -> slice | None:
    """Parse a string into a Python slice object.

    Accepts formats like:
    - "5" -> slice(5, None, None)
    - "1:5" -> slice(1, 5, None)
    - "1:10:2" -> slice(1, 10, 2)
    - ":5" -> slice(None, 5, None)
    - "5:" -> slice(5, None, None)
    - "::2" -> slice(None, None, 2)
    """
    if value is None:
        return None

    parts = value.split(":")

    if len(parts) == 1:
        # Single number: treat as stop value
        return slice(int(parts[0]) if parts[0] else None, None, None)
    if len(parts) == 2:
        # start:stop
        start = int(parts[0]) if parts[0] else None
        stop = int(parts[1]) if parts[1] else None
        return slice(start, stop, None)
    if len(parts) == 3:
        # start:stop:step
        start = int(parts[0]) if parts[0] else None
        stop = int(parts[1]) if parts[1] else None
        step = int(parts[2]) if parts[2] else None
        return slice(start, stop, step)
    raise ValueError(f"Invalid slice format: {value}")


def slice_to_str(value: slice | int | None) -> str | None:
    """Parse a Python slice object into string.

    Returns formats like:
    - "1:5" -> slice(1, 5, None)
    - "1:10:2" -> slice(1, 10, 2)
    - ":5" -> slice(None, 5, None)
    - "5:" -> slice(5, None, None)
    - "::2" -> slice(None, None, 2)
    """
    if value is None:
        return None
    if isinstance(value, int):
        return str(int)

    s = ""
    if value.start is not None:
        s += f"{value.start}:"
    else:
        s += ":"
    if value.stop is not None:
        s += f"{value.stop}"
    if value.step is not None:
        s += f":{value.step}"
    return s
