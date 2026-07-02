"""Remote operations for database tables.

This module provides pre-configured AsyncRemoteOperations instances
for each database table. Use these for making async API calls to the
remote service.

Examples
--------
>>> async with algorithm as ops:
...     result = await ops.get_row(1)

>>> # Or for single operations (less efficient):
>>> result = await algorithm.get_row(1)

>>> # Using extended dataset operations:
>>> async with dataset as ops:
...     loaded = await ops.load(path="/data/file.hdf5", load_type=LoadType.link)
...     data = await ops.read_slice(row_id=loaded.id, start=0, stop=100)
"""

from .. import models
from ..config import config as global_config
from .base import (
    AsyncRemoteOperations,
)

BASE_URL = global_config.client.service_url

test_named: AsyncRemoteOperations[models.TestNamed, models.TestNamedCreate] = AsyncRemoteOperations(
    BASE_URL, "test_named", models.TestNamed, models.TestNamedCreate
)

test_ref: AsyncRemoteOperations[models.TestRef, models.TestRefCreate] = AsyncRemoteOperations(
    BASE_URL, "test_ref", models.TestRef, models.TestRefCreate
)

test_list_pair: AsyncRemoteOperations[models.TestListPair, models.TestListPairCreate] = AsyncRemoteOperations(
    BASE_URL, "test_list_pair", models.TestListPair, models.TestListPairCreate
)


__all__ = [
    "test_named",
    "test_ref",
    "test_list_pair",
    "AsyncRemoteOperations",
]
