from typing import TYPE_CHECKING, Any

from .. import db, models
from ..common import RowId
from .base import LocalOperations, with_session

if TYPE_CHECKING:
    from ..db_oper.test_classes import TestTableOperations


class TestNamedLocalOperations(LocalOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations on local DB for TestNamed table."""


class TestRefLocalOperations(LocalOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations on local DB for TestRef table."""


class TestListPairLocalOperations(
    LocalOperations[db.TestListPair, models.TestListPair, models.TestListPairCreate]
):
    """Operations on local DB for TestListPair table."""


class TestTableLocalOperations(LocalOperations[db.TestTable, models.TestTable, models.TestTableCreate]):
    """Operations on local DB for TestTable (file-backed) table."""

    @property
    def _typed_ops(self) -> "TestTableOperations":
        return self._table_ops  # type: ignore[return-value]

    @with_session
    async def read_slice(
        self,
        session: Any,
        row_id: RowId,
        the_slice: slice | int | None = None,
    ) -> dict[str, Any]:
        return await self._typed_ops.read_slice(session, row_id, the_slice)
