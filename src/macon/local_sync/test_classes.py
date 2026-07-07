from typing import Any

from .. import db, models
from .base import SyncOperations, sync_wrapper
from ..local_async.test_classes import TestTableLocalOperations


class TestNamedSyncOperations(SyncOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations on local DB for TestNamed table."""


class TestRefOperations(SyncOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations on local DB for TestRef table."""


class TestListPairOperations(SyncOperations[db.TestListPair, models.TestListPair, models.TestListPairCreate]):
    """Operations on local DB for TestListPair table."""


class TestTableSyncOperations(SyncOperations[db.TestTable, models.TestTable, models.TestTableCreate]):
    """Synchronous operations for TestTable (file-backed) table."""

    @sync_wrapper(TestTableLocalOperations.read_slice)
    def read_slice(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.async_ops.read_slice(*args, **kwargs)  # type: ignore
