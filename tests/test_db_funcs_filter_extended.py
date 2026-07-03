"""Extended tests for macon.db_funcs.filter — covering more operators and edge cases."""

from macon.db.test_classes import TestNamed
from macon.db_funcs import filter as db_filter
from macon.models import Filter, FilterOp, OrderBy


class TestFilterOpBetween:
    async def test_between_ids(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.BETWEEN, value=[first_id, first_id + 2])],
            limit=100,
        )
        assert len(results) == 3


class TestFilterOpIsNull:
    async def test_is_not_null(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IS_NOT_NULL)],
            limit=100,
        )
        assert len(results) == 5


class TestFilterOpIlike:
    async def test_ilike_case_insensitive(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.ILIKE, value="ALPHA")],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "alpha"


class TestFilterMultipleOrderBy:
    async def test_list_order_by(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=[
                OrderBy(field="name", descending=True),
            ],
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names, reverse=True)


class TestFilterNoResults:
    async def test_filter_one_or_none_no_match(self, db_session, seed_named_rows):
        result = await db_filter.filter_one_or_none(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="zzz_nonexistent")],
        )
        assert result is None

    async def test_find_by_no_results(self, db_session, seed_named_rows):
        results = await db_filter.find_by(
            TestNamed,
            db_session,
            name="zzz_nonexistent",
        )
        assert results == []

    async def test_count_filtered_no_match(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="zzz_nonexistent")],
        )
        assert count == 0


class TestFilterStreaming:
    async def test_streaming_with_order(self, db_session, seed_named_rows):
        rows = []
        async for row in db_filter.filter_rows_streaming(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name", descending=False),
            limit=3,
        ):
            rows.append(row)
        assert len(rows) == 3
        names = [r.name for r in rows]
        assert names == sorted(names)

    async def test_streaming_empty(self, db_session):
        rows = []
        async for row in db_filter.filter_rows_streaming(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="nonexistent")],
            limit=100,
        ):
            rows.append(row)
        assert rows == []
