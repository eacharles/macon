"""Additional unit tests for macon.db_funcs.filter — covering remaining functional paths."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import filter as db_filter
from macon.models import Filter, FilterOp, OrderBy


class TestFilterRowsOrLogic:
    async def test_or_matches_either_condition(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="gamma"),
            ],
            logical_op="or",
            limit=100,
        )
        names = {r.name for r in results}
        assert names == {"alpha", "gamma"}

    async def test_or_with_no_matches(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="zzz"),
                Filter(field="name", op=FilterOp.EQ, value="yyy"),
            ],
            logical_op="or",
            limit=100,
        )
        assert results == []

    async def test_or_with_overlapping_conditions(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.STARTS_WITH, value="a"),
                Filter(field="name", op=FilterOp.ENDS_WITH, value="a"),
            ],
            logical_op="or",
            limit=100,
        )
        names = {r.name for r in results}
        assert "alpha" in names
        assert "delta" in names
        assert "gamma" in names


class TestFilterRowsMultipleAndFilters:
    async def test_and_narrows_results(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="id_", op=FilterOp.GE, value=first_id),
                Filter(field="name", op=FilterOp.STARTS_WITH, value="a"),
            ],
            logical_op="and",
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "alpha"

    async def test_and_with_contradictory_filters(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="beta"),
            ],
            logical_op="and",
            limit=100,
        )
        assert results == []


class TestFilterRowsPagination:
    async def test_skip_with_filter(self, db_session, seed_named_rows):
        all_results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            limit=100,
        )
        skipped = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            skip=2,
            limit=100,
        )
        assert skipped == all_results[2:]

    async def test_limit_with_filter(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            limit=2,
        )
        assert len(results) == 2

    async def test_skip_and_limit_combined(self, db_session, seed_named_rows):
        all_sorted = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            limit=100,
        )
        page = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            skip=1,
            limit=2,
        )
        assert page == all_sorted[1:3]


class TestFilterRowsStreamingOrLogic:
    async def test_streaming_or_logic(self, db_session, seed_named_rows):
        rows = []
        async for row in db_filter.filter_rows_streaming(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="beta"),
            ],
            logical_op="or",
            limit=100,
        ):
            rows.append(row)
        names = {r.name for r in rows}
        assert names == {"alpha", "beta"}

    async def test_streaming_with_skip(self, db_session, seed_named_rows):
        all_rows = []
        async for row in db_filter.filter_rows_streaming(TestNamed, db_session, limit=100):
            all_rows.append(row)

        skipped_rows = []
        async for row in db_filter.filter_rows_streaming(TestNamed, db_session, skip=3, limit=100):
            skipped_rows.append(row)
        assert len(skipped_rows) == len(all_rows) - 3

    async def test_streaming_respects_limit(self, db_session, seed_named_rows):
        rows = []
        async for row in db_filter.filter_rows_streaming(TestNamed, db_session, limit=2):
            rows.append(row)
        assert len(rows) == 2


class TestCountFilteredRows:
    async def test_count_with_or_logic(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="beta"),
            ],
            logical_op="or",
        )
        assert count == 2

    async def test_count_with_multiple_and_filters(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        count = await db_filter.count_filtered_rows(
            TestNamed,
            db_session,
            filters=[
                Filter(field="id_", op=FilterOp.GE, value=first_id),
                Filter(field="id_", op=FilterOp.LE, value=first_id + 2),
            ],
            logical_op="and",
        )
        assert count == 3

    async def test_count_all_rows_no_filters(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(TestNamed, db_session)
        assert count == 5


class TestFilterOneWithOrLogic:
    async def test_filter_one_or_logic_single_match(self, db_session, seed_named_rows):
        result = await db_filter.filter_one(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="alpha"),
                Filter(field="name", op=FilterOp.EQ, value="nonexistent"),
            ],
            logical_op="or",
        )
        assert result.name == "alpha"


class TestFilterOneOrNoneWithOrLogic:
    async def test_or_logic_single_match(self, db_session, seed_named_rows):
        result = await db_filter.filter_one_or_none(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="beta"),
                Filter(field="name", op=FilterOp.EQ, value="nonexistent"),
            ],
            logical_op="or",
        )
        assert result is not None
        assert result.name == "beta"

    async def test_or_logic_no_match(self, db_session, seed_named_rows):
        result = await db_filter.filter_one_or_none(
            TestNamed,
            db_session,
            filters=[
                Filter(field="name", op=FilterOp.EQ, value="xxx"),
                Filter(field="name", op=FilterOp.EQ, value="yyy"),
            ],
            logical_op="or",
        )
        assert result is None


class TestFindBy:
    async def test_find_by_with_order(self, db_session, seed_named_rows):
        results = await db_filter.find_by(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name", descending=True),
        )
        names = [r.name for r in results]
        assert names == sorted(names, reverse=True)

    async def test_find_by_with_skip_and_limit(self, db_session, seed_named_rows):
        all_results = await db_filter.find_by(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
        )
        page = await db_filter.find_by(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name"),
            skip=1,
            limit=2,
        )
        assert len(page) == 2
        assert page[0].name == all_results[1].name
        assert page[1].name == all_results[2].name

    async def test_find_by_multiple_kwargs(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        results = await db_filter.find_by(TestNamed, db_session, name="alpha", id_=row.id_)
        assert len(results) == 1
        assert results[0].name == "alpha"

    async def test_find_by_no_kwargs_returns_all(self, db_session, seed_named_rows):
        results = await db_filter.find_by(TestNamed, db_session)
        assert len(results) == 5


class TestFindOneBy:
    async def test_find_one_by_not_found(self, db_session, seed_named_rows):
        with pytest.raises(KeyError, match="No TestNamed found"):
            await db_filter.find_one_by(TestNamed, db_session, name="nonexistent")

    async def test_find_one_by_multiple_matches(self, db_session, seed_named_rows):
        # find_one_by uses EQ on kwargs, so we can't easily get multiple matches
        # with the unique name field. Instead test with id_ filter that matches > 1
        # This test verifies the error path through filter_one
        first_id = seed_named_rows[0].id_
        # Use filter_one directly with a filter that matches multiple
        with pytest.raises(KeyError, match="Multiple TestNamed rows"):
            await db_filter.filter_one(
                TestNamed,
                db_session,
                filters=[Filter(field="id_", op=FilterOp.GE, value=first_id)],
            )


class TestMultipleOrderBy:
    async def test_multiple_order_by_list(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=[
                OrderBy(field="name", descending=False),
            ],
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names)

    async def test_order_by_single_object(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            order_by=OrderBy(field="name", descending=True),
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names, reverse=True)


class TestFilterOperators:
    async def test_le_operator(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.LE, value=first_id + 1)],
            limit=100,
        )
        assert len(results) == 2

    async def test_ge_operator(self, db_session, seed_named_rows):
        last_id = seed_named_rows[-1].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.GE, value=last_id)],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == seed_named_rows[-1].name

    async def test_ne_operator(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.NE, value="alpha")],
            limit=100,
        )
        assert len(results) == 4
        assert all(r.name != "alpha" for r in results)

    async def test_not_in_operator(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.NOT_IN, value=["alpha", "beta"])],
            limit=100,
        )
        assert len(results) == 3
        names = {r.name for r in results}
        assert "alpha" not in names
        assert "beta" not in names

    async def test_in_with_tuple(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IN, value=("alpha", "epsilon"))],
            limit=100,
        )
        assert len(results) == 2

    async def test_in_with_set(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IN, value={"gamma"})],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "gamma"

    async def test_in_with_empty_list(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IN, value=[])],
            limit=100,
        )
        assert results == []

    async def test_like_pattern_percent(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.LIKE, value="%ta")],
            limit=100,
        )
        names = {r.name for r in results}
        assert "beta" in names
        assert "delta" in names

    async def test_ilike_pattern(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.ILIKE, value="BETA")],
            limit=100,
        )
        assert len(results) == 1
        assert results[0].name == "beta"

    async def test_between_inclusive(self, db_session, seed_named_rows):
        first_id = seed_named_rows[0].id_
        last_id = seed_named_rows[-1].id_
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="id_", op=FilterOp.BETWEEN, value=[first_id, last_id])],
            limit=100,
        )
        assert len(results) == 5

    async def test_is_not_null_on_name(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(
            TestNamed,
            db_session,
            filters=[Filter(field="name", op=FilterOp.IS_NOT_NULL)],
            limit=100,
        )
        assert len(results) == 5


class TestHelperFunctions:
    def test_and_filters(self):
        f1 = Filter(field="a", op=FilterOp.EQ, value=1)
        f2 = Filter(field="b", op=FilterOp.GT, value=2)
        result = db_filter.and_filters(f1, f2)
        assert result == [f1, f2]

    def test_and_filters_empty(self):
        result = db_filter.and_filters()
        assert result == []

    def test_or_filters(self):
        f1 = Filter(field="x", op=FilterOp.EQ, value="a")
        f2 = Filter(field="y", op=FilterOp.EQ, value="b")
        result = db_filter.or_filters(f1, f2)
        assert result == [f1, f2]

    def test_or_filters_single(self):
        f1 = Filter(field="x", op=FilterOp.EQ, value="a")
        result = db_filter.or_filters(f1)
        assert result == [f1]


class TestNoFiltersReturnsAll:
    async def test_filter_rows_none_filters(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(TestNamed, db_session, filters=None, limit=100)
        assert len(results) == 5

    async def test_filter_rows_empty_filter_list(self, db_session, seed_named_rows):
        results = await db_filter.filter_rows(TestNamed, db_session, filters=[], limit=100)
        assert len(results) == 5

    async def test_streaming_none_filters(self, db_session, seed_named_rows):
        rows = []
        async for row in db_filter.filter_rows_streaming(TestNamed, db_session, filters=None, limit=100):
            rows.append(row)
        assert len(rows) == 5

    async def test_count_none_filters(self, db_session, seed_named_rows):
        count = await db_filter.count_filtered_rows(TestNamed, db_session, filters=None)
        assert count == 5
