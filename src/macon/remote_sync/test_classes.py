from .. import models
from .base import SyncRemoteOperations


class TestNamedSyncRemoteOperations(SyncRemoteOperations[models.TestNamed, models.TestNamedCreate]):
    """Sync wrapper for remote operations on TestNamed table."""


class TestRefSyncRemoteOperations(SyncRemoteOperations[models.TestRef, models.TestRefCreate]):
    """Sync wrapper for remote operations on TestNamed table."""


class TestListPairSyncRemoteOperations(SyncRemoteOperations[models.TestListPair, models.TestListPairCreate]):
    """Sync wrapper for remote operations on TestListPair table."""
