"""Tests for macon.db_funcs.update."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import update


class TestUpdateRow:
    async def test_happy_path(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        updated = await update.update_row(TestNamed, db_session, row.id_, name="alpha_updated")
        assert updated.name == "alpha_updated"
        assert updated.id_ == row.id_

    async def test_not_found(self, db_session):
        with pytest.raises(KeyError):
            await update.update_row(TestNamed, db_session, 99999, name="x")


class TestUpdateRows:
    async def test_multiple(self, db_session, seed_named_rows):
        updates = [
            {"id": seed_named_rows[0].id_, "name": "first_updated"},
            {"id": seed_named_rows[1].id_, "name": "second_updated"},
        ]
        results = await update.update_rows(TestNamed, db_session, updates)
        assert len(results) == 2
        assert results[0].name == "first_updated"
        assert results[1].name == "second_updated"
