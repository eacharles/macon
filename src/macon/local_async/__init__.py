"""Local operations API with automatic session management.

This module provides simplified table operations that automatically
manage database sessions and return Pydantic models.

Examples
--------
>>> from macon.local import test_named
>>>
>>> # Get single row
>>> named = await test_named.get_row(row_id=1)
>>>
>>> # Create new row
>>> new_ds = await test_named.create_row(
...     name="a_good_name",
... )
>>>
>>> # Filter rows
>>> from macon.db_funcs.filter import Filter, FilterOp
>>> good_names = await test_named.filter_rows(
...     filters=[Filter("name", FilterOp.EQ, "a_good_name")]
... )
"""

from .. import db_oper
from . import funcs
from .test_classes import (
    TestNamedLocalOperations,
    TestRefLocalOperations,
    TestListPairLocalOperations,
)

# Create local operations - each has all methods via dynamic binding
test_named = TestNamedLocalOperations(db_oper.test_named)
test_ref = TestRefLocalOperations(db_oper.test_ref)
test_list_pair = TestListPairLocalOperations(db_oper.catalog_band_assoc)

__all__ = [
    "LocalOperations",
    "TestNamedLocalOperations",
    "TestRefLocalOperations",
    "TestListPairLocalOperations",
]
