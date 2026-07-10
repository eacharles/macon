"""Test table operations."""

import logging
from pathlib import Path
from typing import Any

import tables_io
import tables_io.io_utils.iterator
from sqlalchemy.ext.asyncio import AsyncSession

from .. import db, db_funcs, models
from ..common import RowId
from ..config import config as global_config
from .base import FileValidatedOperations, TableContext, TableOperations

logger = logging.getLogger(__name__)

__all__ = ["test_named", "test_ref", "test_list_pair", "test_table"]


class TestNamedOperations(TableOperations[db.TestNamed, models.TestNamed, models.TestNamedCreate]):
    """Operations for TestNamed table."""


class TestRefOperations(TableOperations[db.TestRef, models.TestRef, models.TestRefCreate]):
    """Operations for TestRef table with FK lookup."""

    async def get_create_kwargs(
        self,
        session: AsyncSession,
        ref_id: RowId | None = None,
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


class TestTableOperations(FileValidatedOperations[db.TestTable, models.TestTable, models.TestTableCreate]):
    """Operations for TestTable — a file-backed table using tables_io."""

    def get_file_length(self, path: Path) -> int:
        return tables_io.io_utils.iterator.get_input_data_length(str(path))

    def get_subdirectory(self) -> str:
        return "test_tables"

    async def get_create_kwargs(
        self,
        session: AsyncSession,
        **kwargs: Any,
    ) -> dict[str, Any]:
        kwargs.pop("validate_file", None)
        return kwargs

    async def read_slice(
        self,
        session: AsyncSession,
        row_id: RowId,
        the_slice: slice | int | None = None,
    ) -> dict[str, Any]:
        """Read a slice of data from the file associated with a row.

        Parameters
        ----------
        session
            Database session
        row_id
            ID of the row whose file to read
        the_slice
            Slice specification (slice, int, or None for all data)

        Returns
        -------
            Dictionary mapping column names to numpy arrays
        """
        row = await db_funcs.read.get_row(db.TestTable, session, row_id)
        archive_dir = Path(global_config.storage.archive)
        file_path = archive_dir / row.path
        return tables_io.read(str(file_path), slice_dict=the_slice)


test_named: TestNamedOperations = TestNamedOperations(TableContext.from_db_class(db.TestNamed))
test_ref: TestRefOperations = TestRefOperations(TableContext.from_db_class(db.TestRef))
test_list_pair: TestListPairOperations = TestListPairOperations(TableContext.from_db_class(db.TestListPair))
test_table: TestTableOperations = TestTableOperations(TableContext.from_db_class(db.TestTable))
