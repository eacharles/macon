"""Local operations API with automatic session management."""

from .. import db_oper
from .base import LocalOperations
from .test_classes import (
    TestNamedLocalOperations,
    TestRefLocalOperations,
    TestListPairLocalOperations,
)

test_named = TestNamedLocalOperations(db_oper.test_named)
test_ref = TestRefLocalOperations(db_oper.test_ref)
test_list_pair = TestListPairLocalOperations(db_oper.test_list_pair)

__all__ = [
    "LocalOperations",
    "TestNamedLocalOperations",
    "TestRefLocalOperations",
    "TestListPairLocalOperations",
]
