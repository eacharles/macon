"""Extended tests for macon.db_funcs.update — input validation and edge cases."""

import pytest

from macon.db.test_classes import TestNamed
from macon.db_funcs import update


class TestUpdateRowEdgeCases:
    async def test_no_fields_to_update(self, db_session, seed_named_rows):
        """Updating with no actual changes returns the existing row."""
        row = seed_named_rows[0]
        result = await update.update_row(TestNamed, db_session, row.id_)
        assert result.id_ == row.id_
        assert result.name == "alpha"

    async def test_cannot_change_id(self, db_session, seed_named_rows):
        row = seed_named_rows[0]
        with pytest.raises(ValueError, match="Cannot change row ID"):
            await update.update_row(TestNamed, db_session, row.id_, id=9999)

    async def test_id_same_as_row_id_is_ok(self, db_session, seed_named_rows):
        """Passing id=row_id is allowed (it's a no-op for the id field)."""
        row = seed_named_rows[0]
        result = await update.update_row(TestNamed, db_session, row.id_, id=row.id_, name="updated_alpha")
        assert result.name == "updated_alpha"


class TestUpdateRowsEdgeCases:
    async def test_empty_updates_raises(self, db_session):
        with pytest.raises(ValueError, match="cannot be empty"):
            await update.update_rows(TestNamed, db_session, [])

    async def test_missing_id_key_raises(self, db_session, seed_named_rows):
        with pytest.raises(ValueError, match="must contain 'id' key"):
            await update.update_rows(TestNamed, db_session, [{"name": "no_id"}])

    async def test_nonexistent_id_raises(self, db_session, seed_named_rows):
        with pytest.raises(KeyError):
            await update.update_rows(TestNamed, db_session, [{"id": 99999, "name": "ghost"}])
