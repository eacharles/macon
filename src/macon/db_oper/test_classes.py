"""Test table operations."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .. import db, db_funcs, models
from .base import TableContext, TableOperations

logger = logging.getLogger(__name__)

__all__ = ["test_named", "test_ref", "test_list_pair"]


class TestNamedOperations(TableOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations for TestNamed table."""


class TestRefOperations(TableOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations for TestRef table with FK lookup."""

    async def get_create_kwargs(
        self,
        session: AsyncSession,
        ref_id: int | None = None,
        ref_name: str | None = None,
        **extra_kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare kwargs, resolving FK by name if needed."""
        ref_id, _ = await db_funcs.read.lookup_by_id_or_name(
            db.TestNamed,
            session,
            ref_id,
            ref_name,
        )

        return {
            "ref_id": ref_id,
            **extra_kwargs,
        }


class TestListPairOperations(
    TableOperations[db.TestListPair, models.TestListPair, models.TestListPairCreate]
):
    """Operations for TestListPair table."""


test_named: TestNamedOperations = TestNamedOperations(TableContext.from_db_class(db.TestNamed))
test_ref: TestRefOperations = TestRefOperations(TableContext.from_db_class(db.TestRef))
test_list_pair: TestListPairOperations = TestListPairOperations(TableContext.from_db_class(db.TestListPair))
