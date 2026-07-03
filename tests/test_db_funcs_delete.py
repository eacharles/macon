"""Tests for macon.db_funcs.delete."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import delete, read


class TestDeleteRow:
    async def test_with_capture(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        result = await delete.delete_row(TestNamed, db_session, row.id_, capture_data=True)
        assert result is not None
        assert result["name"] == "alpha"
        # Verify row is gone
        remaining = await read.get_row_or_none(TestNamed, db_session, row.id_)
        assert remaining is None

    async def test_without_capture(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        result = await delete.delete_row(TestNamed, db_session, row.id_, capture_data=False)
        assert result is None

    async def test_not_found(self, db_session):
        with pytest.raises(KeyError):
            await delete.delete_row(TestNamed, db_session, 99999)


class TestDeleteRows:
    async def test_multiple_with_capture(self, db_session, seed_named_rows):
        ids = [seed_named_rows[0].id_, seed_named_rows[1].id_]
        result = await delete.delete_rows(TestNamed, db_session, ids, capture_data=True)
        assert result is not None
        assert len(result) == 2

    async def test_multiple_without_capture(self, db_session, seed_named_rows):
        ids = [seed_named_rows[0].id_, seed_named_rows[1].id_]
        result = await delete.delete_rows(TestNamed, db_session, ids, capture_data=False)
        assert result is None


class TestBulkDeleteRows:
    async def test_returns_count(self, db_session, seed_named_rows):
        ids = [r.id_ for r in seed_named_rows]
        count = await delete.bulk_delete_rows(TestNamed, db_session, ids)
        assert count == 5
        # Verify all gone
        remaining = await read.count_rows(TestNamed, db_session)
        assert remaining == 0
