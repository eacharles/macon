"""Sync wrapper instances for remote table operations."""

from .. import remote_async
from .base import SyncRemoteOperations
from .test_classes import (
    TestNamedSyncRemoteOperations,
    TestRefSyncRemoteOperations,
    TestListPairSyncRemoteOperations,
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
