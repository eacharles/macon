"""Tests for macon.db_funcs.read."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import read


class TestGetRow:
    async def test_happy_path(self, db_session, seed_named_rows):
        rows = seed_named_rows
        result = await read.get_row(TestNamed, db_session, rows[0].id_)
        assert result.name == "alpha"

    async def test_not_found(self, db_session):
        with pytest.raises(KeyError):
            await read.get_row(TestNamed, db_session, 99999)


class TestGetRowByName:
    async def test_happy_path(self, db_session, seed_named_rows):
        result = await read.get_row_by_name(TestNamed, db_session, "beta")
        assert result.name == "beta"

    async def test_not_found(self, db_session, seed_named_rows):
        with pytest.raises(KeyError):
            await read.get_row_by_name(TestNamed, db_session, "nonexistent")


class TestGetRows:
    async def test_returns_all(self, db_session, seed_named_rows):
        results = await read.get_rows(TestNamed, db_session, limit=100)
        assert len(results) == 5

    async def test_skip(self, db_session, seed_named_rows):
        results = await read.get_rows(TestNamed, db_session, skip=3, limit=100)
        assert len(results) == 2

    async def test_limit(self, db_session, seed_named_rows):
        results = await read.get_rows(TestNamed, db_session, limit=2)
        assert len(results) == 2

    async def test_empty_table(self, db_session):
        results = await read.get_rows(TestNamed, db_session, limit=100)
        assert len(results) == 0


class TestGetRowsStreaming:
    async def test_yields_rows(self, db_session, seed_named_rows):
        rows = []
        async for row in read.get_rows_streaming(TestNamed, db_session, limit=100):
            rows.append(row)
        assert len(rows) == 5

    async def test_respects_limit(self, db_session, seed_named_rows):
        rows = []
        async for row in read.get_rows_streaming(TestNamed, db_session, limit=2):
            rows.append(row)
        assert len(rows) == 2


class TestGetRowOrNone:
    async def test_found(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        result = await read.get_row_or_none(TestNamed, db_session, row.id_)
        assert result is not None
        assert result.name == "alpha"

    async def test_not_found(self, db_session):
        result = await read.get_row_or_none(TestNamed, db_session, 99999)
        assert result is None


class TestCountRows:
    async def test_count(self, db_session, seed_named_rows):
        count = await read.count_rows(TestNamed, db_session)
        assert count == 5

    async def test_empty(self, db_session):
        count = await read.count_rows(TestNamed, db_session)
        assert count == 0


class TestLookupByIdOrName:
    async def test_by_id_no_object(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        row_id, obj = await read.lookup_by_id_or_name(TestNamed, db_session, row.id_, None, need_object=False)
        assert row_id == row.id_
        assert obj is None

    async def test_by_id_with_object(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        row_id, obj = await read.lookup_by_id_or_name(TestNamed, db_session, row.id_, None, need_object=True)
        assert row_id == row.id_
        assert obj is not None
        assert obj.name == "alpha"

    async def test_by_name(self, db_session, seed_named_rows):
        row_id, obj = await read.lookup_by_id_or_name(TestNamed, db_session, None, "gamma", need_object=False)
        assert obj is not None
        assert obj.name == "gamma"

    async def test_neither_raises(self, db_session):
        with pytest.raises(ValueError):
            await read.lookup_by_id_or_name(TestNamed, db_session, None, None)
