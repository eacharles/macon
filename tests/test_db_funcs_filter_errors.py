"""Tests for expected error paths in macon.db_funcs.filter."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import filter as db_filter
from macon.models import Filter, FilterOp, OrderBy


class TestFilterOneErrors:
    async def test_no_matching_rows(self, db_session, seed_named_rows):
        with pytest.raises(KeyError, match="No TestNamed found"):
            await db_filter.filter_one(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.EQ, value="nonexistent")],
            )

    async def test_multiple_matching_rows(self, db_session, seed_named_rows):
        with pytest.raises(KeyError, match="Multiple TestNamed rows"):
            await db_filter.filter_one(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.LIKE, value="%a%")],
            )


class TestFilterOneOrNoneErrors:
    async def test_multiple_matching_rows(self, db_session, seed_named_rows):
        with pytest.raises(KeyError, match="Multiple TestNamed rows"):
            await db_filter.filter_one_or_none(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.LIKE, value="%a%")],
            )


class TestInvalidLogicalOp:
    async def test_filter_rows_invalid_logical_op(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="logical_op must be"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
                logical_op="xor",
                limit=100,
            )

    async def test_filter_rows_streaming_invalid_logical_op(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="logical_op must be"):
            async for _ in db_filter.filter_rows_streaming(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
                logical_op="neither",
                limit=100,
            ):
                pass

    async def test_count_filtered_rows_invalid_logical_op(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="logical_op must be"):
            await db_filter.count_filtered_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.EQ, value="alpha")],
                logical_op="bad",
            )


class TestNonExistentField:
    async def test_filter_on_missing_field(self, db_session, seed_named_rows):
        with pytest.raises(AttributeError, match="does not have field 'bogus'"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="bogus", op=FilterOp.EQ, value="x")],
                limit=100,
            )

    async def test_order_by_missing_field(self, db_session, seed_named_rows):
        with pytest.raises(AttributeError, match="does not have field 'bogus'"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                order_by=OrderBy(field="bogus", descending=False),
                limit=100,
            )

    async def test_find_by_missing_field(self, db_session, seed_named_rows):
        with pytest.raises(AttributeError, match="does not have field 'bogus'"):
            await db_filter.find_by(TestNamed, db_session, bogus="value")

    async def test_find_one_by_missing_field(self, db_session, seed_named_rows):
        with pytest.raises(AttributeError, match="does not have field 'bogus'"):
            await db_filter.find_one_by(TestNamed, db_session, bogus="value")


class TestInOperatorErrors:
    async def test_in_with_non_list_value(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="IN operator requires list/tuple/set"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.IN, value="alpha")],
                limit=100,
            )


class TestBetweenOperatorErrors:
    async def test_between_with_single_value(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="BETWEEN operator requires"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="id_", op=FilterOp.BETWEEN, value=[1])],
                limit=100,
            )

    async def test_between_with_three_values(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="BETWEEN operator requires"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="id_", op=FilterOp.BETWEEN, value=[1, 2, 3])],
                limit=100,
            )

    async def test_between_with_non_list_value(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="BETWEEN operator requires"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="id_", op=FilterOp.BETWEEN, value=5)],
                limit=100,
            )


class TestStringOperatorErrors:
    async def test_starts_with_non_string(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="STARTS_WITH operator requires string"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value=123)],
                limit=100,
            )

    async def test_ends_with_non_string(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="ENDS_WITH operator requires string"):
            await db_filter.filter_rows(
                TestNamed,
                db_session,
                filters=[Filter(field="name", op=FilterOp.ENDS_WITH, value=456)],
                limit=100,
            )
