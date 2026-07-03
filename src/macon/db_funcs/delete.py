"""Database row deletion functions."""

from typing import Any

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import T, ensure_base_inheritance

logger = structlog.get_logger(__name__)


async def delete_row(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
    *,
    capture_data: bool = True,
) -> dict[str, Any] | None:
    """Delete a single row by primary key.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to delete from
    session
        DB session manager
    row_id
        Primary key of the row to delete
    capture_data
        If True, capture row data before deletion and return it.

    Raises
    ------
    KeyError
        If row with given ID does not exist
    """
    ensure_base_inheritance(the_class)

    logger.debug("Deleting row", table=the_class.__name__, row_id=row_id)

    row = await session.get(the_class, row_id)
    if row is None:
        logger.warning("Cannot delete - row not found", table=the_class.__name__, row_id=row_id)
        raise KeyError(f"{the_class.__name__} {row_id} not found")

    row_data: dict[str, Any] | None = None
    if capture_data:
        row_data = {column.name: getattr(row, column.name) for column in the_class.__table__.columns}

    await the_class.pre_delete_hook(session, row)

    await session.delete(row)
    await session.flush()

    await the_class.after_delete_hook(session, row)

    logger.info("Row deleted successfully", table=the_class.__name__, row_id=row_id)
    return row_data


async def delete_rows(
    the_class: type[T],
    session: AsyncSession,
    row_ids: list[int],
    *,
    capture_data: bool = False,
) -> list[dict[str, Any]] | None:
    """Delete multiple rows atomically.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to delete from
    session
        DB session manager
    row_ids
        List of primary keys to delete
    capture_data
        If True, capture data for all deleted rows

    Raises
    ------
    ValueError
        If row_ids is empty
    KeyError
        If any row ID is not found
    """
    ensure_base_inheritance(the_class)

    if not row_ids:
        raise ValueError("row_ids cannot be empty")

    logger.debug("Deleting multiple rows", table=the_class.__name__, count=len(row_ids))

    all_data: list[dict[str, Any]] = []
    rows_to_delete: list[T] = []

    for row_id in row_ids:
        row = await session.get(the_class, row_id)
        if row is None:
            raise KeyError(f"{the_class.__name__} {row_id} not found")

        if capture_data:
            row_data = {column.name: getattr(row, column.name) for column in the_class.__table__.columns}
            all_data.append(row_data)

        rows_to_delete.append(row)

    for row in rows_to_delete:
        await the_class.pre_delete_hook(session, row)

    for row in rows_to_delete:
        await session.delete(row)

    await session.flush()

    for row in rows_to_delete:
        await the_class.after_delete_hook(session, row)

    logger.info("Multiple rows deleted successfully", table=the_class.__name__, count=len(row_ids))

    return all_data if capture_data else None


async def bulk_delete_rows(
    the_class: type[T],
    session: AsyncSession,
    row_ids: list[int],
) -> int:
    """Delete multiple rows using bulk SQL operation.

    Does NOT call hooks and does NOT return deleted row data.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to delete from
    session
        DB session manager
    row_ids
        List of primary keys to delete

    Raises
    ------
    ValueError
        If row_ids is empty
    """
    ensure_base_inheritance(the_class)

    if not row_ids:
        raise ValueError("row_ids cannot be empty")

    logger.debug("Bulk deleting rows", table=the_class.__name__, count=len(row_ids))

    stmt = delete(the_class).where(the_class.id_.in_(row_ids))  # type: ignore
    result = await session.execute(stmt)
    deleted_count = result.rowcount  # type: ignore

    logger.info(
        "Bulk delete completed",
        table=the_class.__name__,
        requested=len(row_ids),
        deleted=deleted_count,
    )

    return deleted_count
