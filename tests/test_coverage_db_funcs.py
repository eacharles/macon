"""Coverage tests for db_funcs — filter.py line 64 (LT), read.py line 218 (streaming limit fallback)."""

from macon.db.test_classes import TestNamed
from macon.db_funcs import filter as db_filter
from macon.db_funcs import read as db_read
from macon.models import Filter, FilterOp


class TestLtOperator:
    async def test_lt_filters_correctly(self, db_session, seed_named_rows):
        third_id = seed_named_rows[2].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.LT, value=third_id)],
            limit=100,
        )
        assert len(results) == 2
        assert all(r.id_ < third_id for r in results)


class TestContainsOperator:
    async def test_contains_on_sqlite_string(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.CONTAINS, value="lph")],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "alpha"


class TestGetRowsStreamingLimitFallback:
    async def test_streaming_without_limit_uses_default(self, db_session, seed_named_rows):
        rows = []
        async for row in db_read.get_rows_streaming(TestNamed, db_session, limit=None):
            rows.append(row)
        assert len(rows) == 5
