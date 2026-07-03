"""Tests for macon.db_funcs.filter."""

from macon.db.test_classes import TestNamed
from macon.db_funcs import filter as db_filter
from macon.models import Filter, FilterOp, OrderBy


class TestFilterRows:
    async def test_eq(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
        )
        assert len(results) == 1
        assert results[0].name == "alpha"

    async def test_ne(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.NE, value="alpha")],
            limit=100,
        )
        assert len(results) == 4

    async def test_in(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IN, value=["alpha", "beta"])],
            limit=100,
        )
        assert len(results) == 2

    async def test_not_in(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.NOT_IN, value=["alpha", "beta"])],
            limit=100,
        )
        assert len(results) == 3

    async def test_like(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.LIKE, value="a%")],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "alpha"

    async def test_starts_with(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="e")],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "epsilon"

    async def test_ends_with(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.ENDS_WITH, value="ta")],
            limit=100,
        )
        assert len(results) == 2  # beta, delta

    async def test_gt_lt_on_id(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.GT, value=first_id)],
            limit=100,
        )
        assert len(results) == 4

    async def test_logical_or(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="beta"),
            ],
            logical_op="or",
            limit=100,
        )
        assert len(results) == 2

    async def test_logical_and(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="id_", op=FilterOp.EQ, value=first_id),
            ],
            logical_op="and",
            limit=100,
        )
        assert len(results) == 1

    async def test_no_filters_returns_all(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(TestNamed, db_session, filters=None, limit=100)
        assert len(results) == 5

    async def test_order_by_ascending(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name", descending=False),
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names)

    async def test_order_by_descending(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name", descending=True),
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names, reverse=True)

    async def test_pagination(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(TestNamed, db_session, skip=2, limit=2)
        assert len(results) == 2


class TestFilterRowsStreaming:
    async def test_yields_filtered(self, db_session, seed_named_rows):
        rows = []
        async for row in db_filter.filter_rows_streaming(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="a")],
            limit=100,
        ):
            rows.append(row)
        assert len(rows) == 1


class TestCountFilteredRows:
    async def test_count(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="a")],
        )
        assert count == 1

    async def test_no_filters(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(TestNamed, db_session)
        assert count == 5


class TestFilterOne:
    async def test_found(self, db_session, seed_named_rows):
        result = await db_filter.filter_one(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
        )
        assert result.name == "alpha"


class TestFilterOneOrNone:
    async def test_found(self, db_session, seed_named_rows):
        result = await db_filter.filter_one_or_none(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
        )
        assert result is not None
        assert result.name == "alpha"

    async def test_not_found(self, db_session, seed_named_rows):
        result = await db_filter.filter_one_or_none(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.EQ, value="nonexistent")],
        )
        assert result is None


class TestFindBy:
    async def test_find_by_name(self, db_session, seed_named_rows):
        results = await db_filter.find_by(TestNamed, db_session, name="alpha")
        assert len(results) == 1
        assert results[0].name == "alpha"

    async def test_find_by_no_match(self, db_session, seed_named_rows):
        results = await db_filter.find_by(TestNamed, db_session, name="nonexistent")
        assert len(results) == 0


class TestFindOneBy:
    async def test_found(self, db_session, seed_named_rows):
        result = await db_filter.find_one_by(TestNamed, db_session, name="beta")
        assert result.name == "beta"
