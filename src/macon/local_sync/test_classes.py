from .. import db, models
from .base import SyncOperations


class TestNamedSyncOperations(SyncOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations on local DB for TestNamed table."""


class TestRefOperations(SyncOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations on local DB for TestRef table."""


class TestListPairOperations(SyncOperations[db.TestListPair, models.TestListPair, models.TestListPairCreate]):
    """Operations on local DB for TestListPair table."""
