from .. import local_async
from .base import (
    SyncOperations,
)
from .test_classes import (
    TestNamedSyncOperations,
    TestRefOperations,
    TestListPairOperations,
)

test_named = TestNamedSyncOperations(local_async.test_named)
test_ref = TestRefOperations(local_async.test_ref)
test_list_pair = TestListPairOperations(local_async.test_list_pair)

__all__ = [
    "SyncOperations",
    "test_named",
    "test_ref",
    "test_list_pair",
]
