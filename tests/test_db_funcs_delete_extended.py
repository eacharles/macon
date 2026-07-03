"""Extended tests for macon.db_funcs.delete — input validation."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import delete


class TestDeleteRowsEdgeCases:
    async def test_empty_list_raises(self, db_session):
        with pytest.raises(ValueError, match="cannot be empty"):
            await delete.delete_rows(TestNamed, db_session, [])

    async def test_nonexistent_id_raises(self, db_session, seed_named_rows):
        with pytest.raises(KeyError):
            await delete.delete_rows(TestNamed, db_session, [99999])


class TestBulkDeleteEdgeCases:
    async def test_empty_list_raises(self, db_session):
        with pytest.raises(ValueError, match="cannot be empty"):
            await delete.bulk_delete_rows(TestNamed, db_session, [])

    async def test_nonexistent_ids_returns_zero(self, db_session):
        count = await delete.bulk_delete_rows(TestNamed, db_session, [99999, 99998])
        assert count == 0
