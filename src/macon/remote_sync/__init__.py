"""Sync wrapper instances for remote table operations.

This module provides factory functions to create synchronous wrappers
around async remote operations for each database table.

Examples
--------
>>> ops = algorithm()
>>> result = ops.get_row(1)

>>> # With custom configuration:
>>> ops = algorithm(timeout=60.0, auth_token="...")
>>> result = ops.get_row(1)
"""

from typing import Any

from .. import remote_async
from .base import (
    TestNamedSyncRemoteOperations,
    TestRefSyncRemoteOperations,
    TestListPairSyncRemoteOperations,
    SyncRemoteOperations,
)


def test_named() -> TestNamedSyncRemoteOperations:
    """Create sync remote operations for test_named table."""
    return TestNamedSyncRemoteOperations(remote_async.test_named)


def test_ref() -> TestRefSyncRemoteOperations:
    """Create sync remote operations for test_ref table."""
    return TestRefSyncRemoteOperations(remote_async.test_ref)


def test_list_pair() -> TestListPairSyncRemoteOperations:
    """Create sync remote operations for test_list_pair table."""
    return TestListPairSyncRemoteOperations(remote_async.test_list_pair)


__all__ = [
    "test_named",
    "test_ref",
    "test_list_pair",
    "SyncRemoteOperations",
]
