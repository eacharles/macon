"""Database row deletion functions for rail-svc.

This module provides functions for deleting database rows with
pre and post-deletion hook support.
"""

from typing import Any

import structlog
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rail_svc.db.base import T, ensure_base_inheritance

logger = structlog.get_logger(__name__)


async def delete_row(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
    *,
    capture_data: bool = True,
) -> dict[str, Any] | None:
    """Delete a single row by primary key.

    The deletion is automatically committed. Pre and post-delete hooks
    are called within the transaction - if either hook raises an exception,
    the deletion is rolled back.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to delete from
    session
        DB session manager
    row_id
        Primary key of the row to delete
    capture_data
        If True, capture row data before deletion and pass to after-hook.
        Set to False for performance if after-hook doesn't need the data.

    Returns
    -------
    dict[str, Any] | None
        Dictionary of deleted row data if capture_data=True, else None

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    KeyError
        If row with given ID does not exist
    IntegrityError
        If deletion violates database constraints (e.g., foreign key)
    Exception
        If pre or post-delete hooks raise an exception

    Notes
    -----
    - Pre-delete hook is called before deletion with access to the row object
    - Post-delete hook is called after deletion but before commit
    - If any hook raises an exception, the deletion is rolled back

    Examples
    --------
    >>> # Delete with data capture
    >>> deleted_data = await delete_row(User, session, 123)
    >>> print(f"Deleted user: {deleted_data['username']}")
    >>>
    >>> # Delete without data capture (faster)
    >>> await delete_row(User, session, 123, capture_data=False)
    """
    ensure_base_inheritance(the_class)

    logger.debug("Deleting row", table=the_class.__name__, row_id=row_id)

    # First verify the row exists and get the full object
    row = await session.get(the_class, row_id)
    if row is None:
        logger.warning("Cannot delete - row not found", table=the_class.__name__, row_id=row_id)
        raise KeyError(f"{the_class.__name__} {row_id} not found")

    # Capture row data before deletion if requested
    row_data: dict[str, Any] | None = None
    if capture_data:
        row_data = {column.name: getattr(row, column.name) for column in the_class.__table__.columns}

    try:
        # Call the pre-delete hook BEFORE deletion so it has access to row
        await the_class.pre_delete_hook(session, row)

        # Delete the row
        await session.delete(row)

        # Flush to catch integrity errors
        await session.flush()

        # Call the after-delete hook AFTER deletion but before commit
        await the_class.after_delete_hook(session, row)

        # Commit the transaction
        await session.commit()

    except IntegrityError as uexc:
        await session.rollback()
        logger.error(
            "Integrity error during delete",
            table=the_class.__name__,
            row_id=row_id,
            error=str(uexc),
        )
        raise
    except Exception as uexc:
        # Catch any errors from hooks or other operations
        await session.rollback()
        logger.error(
            "Error during delete operation",
            table=the_class.__name__,
            row_id=row_id,
            error=str(uexc),
        )
        raise

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

    All rows are deleted in a single transaction - if any deletion fails,
    all deletions are rolled back.

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

    Returns
    -------
    list[dict[str, Any]] | None
        List of deleted row data dicts if capture_data=True, else None

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    ValueError
        If row_ids is empty
    KeyError
        If any row ID is not found
    IntegrityError
        If any deletion violates constraints

    Examples
    --------
    >>> deleted = await delete_rows(User, session, [1, 2, 3], capture_data=True)
    >>> print(f"Deleted {len(deleted)} users")
    """
    ensure_base_inheritance(the_class)

    if not row_ids:
        raise ValueError("row_ids cannot be empty")

    logger.debug("Deleting multiple rows", table=the_class.__name__, count=len(row_ids))

    all_data: list[dict[str, Any]] = [] if capture_data else []
    rows_to_delete: list[T] = []

    try:
        # Phase 1: Fetch all rows and capture data
        for row_id in row_ids:
            row = await session.get(the_class, row_id)
            if row is None:
                logger.warning(
                    "Cannot delete - row not found",
                    table=the_class.__name__,
                    row_id=row_id,
                )
                raise KeyError(f"{the_class.__name__} {row_id} not found")

            # Capture data if requested
            if capture_data:
                row_data = {column.name: getattr(row, column.name) for column in the_class.__table__.columns}
                all_data.append(row_data)

            rows_to_delete.append(row)

        # Phase 2: Call pre-delete hooks
        for row in rows_to_delete:
            await the_class.pre_delete_hook(session, row)

        # Phase 3: Delete all rows
        for row in rows_to_delete:
            await session.delete(row)

        # Flush to catch integrity errors
        await session.flush()

        # Phase 4: Call after-delete hooks
        for row in rows_to_delete:
            await the_class.after_delete_hook(session, row)

        # Commit the transaction
        await session.commit()

        logger.info(
            "Multiple rows deleted successfully",
            table=the_class.__name__,
            count=len(row_ids),
        )

        return all_data if capture_data else None

    except IntegrityError as uexc:
        await session.rollback()
        logger.error(
            "Integrity error during bulk delete",
            table=the_class.__name__,
            row_count=len(row_ids),
            error=str(uexc),
        )
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            "Error during bulk delete",
            table=the_class.__name__,
            row_count=len(row_ids),
            error=str(e),
        )
        raise


async def bulk_delete_rows(
    the_class: type[T],
    session: AsyncSession,
    row_ids: list[int],
) -> int:
    """Delete multiple rows using bulk SQL operation.

    This is much faster than delete_rows() but does NOT call hooks
    and does NOT return deleted row data.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to delete from
    session
        DB session manager
    row_ids
        List of primary keys to delete

    Returns
    -------
    int
        Number of rows actually deleted

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    ValueError
        If row_ids is empty
    IntegrityError
        If deletion violates constraints

    Notes
    -----
    - Does NOT call pre/post-delete hooks
    - Does NOT verify rows exist before deleting
    - Does NOT capture deleted row data
    - Much faster for large deletions

    Examples
    --------
    >>> # Delete 10,000 rows efficiently
    >>> count = await bulk_delete_rows(User, session, list(range(1, 10001)))
    >>> print(f"Deleted {count} users")
    """
    ensure_base_inheritance(the_class)

    if not row_ids:
        raise ValueError("row_ids cannot be empty")

    logger.debug("Bulk deleting rows", table=the_class.__name__, count=len(row_ids))

    try:
        # Use SQL DELETE statement for maximum performance

        stmt = delete(the_class).where(the_class.id_.in_(row_ids))  # type: ignore
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount  # type: ignore

        logger.info(
            "Bulk delete completed",
            table=the_class.__name__,
            requested=len(row_ids),
            deleted=deleted_count,
        )

        return deleted_count

    except IntegrityError as uexc:
        await session.rollback()
        logger.error(
            "Integrity error during bulk delete",
            table=the_class.__name__,
            error=str(uexc),
        )
        raise
