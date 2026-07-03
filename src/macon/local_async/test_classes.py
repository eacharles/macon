from .. import db, models
from .base import LocalOperations


class TestNamedLocalOperations(LocalOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations on local DB for TestNamed table."""


class TestRefLocalOperations(LocalOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations on local DB for TestRef table."""


class TestListPairLocalOperations(
    LocalOperations[db.TestListPair, models.TestListPair, models.TestListPairCreate]
):
    """Operations on local DB for TestListPair table."""
