"""Database row update functions for rail-svc.

This module provides functions for updating existing database rows.
"""

from collections.abc import Sequence
from typing import Any, cast

import structlog
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from rail_svc.db.base import T, ensure_base_inheritance

from ..common import unexpected

logger = structlog.get_logger(__name__)


async def update_row(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
    **kwargs: Any,
) -> T:
    """Update a single row by primary key.

    The update is committed automatically. If the update fails, the
    transaction is rolled back.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to update
    session
        DB session manager
    row_id
        Primary key of the row to update
    **kwargs
        Column names and their new values

    Returns
    -------
    T
        Updated row with refreshed database values

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    ValueError
        If attempting to change the row's ID
    KeyError
        If row with given ID does not exist
    StatementError
        If update statement is invalid (e.g., invalid column or type)

    Notes
    -----
    - The row's ID cannot be changed
    - The update is automatically committed
    - Row is refreshed after update to load any DB-generated values

    Examples
    --------
    >>> user = await update_row(
    ...     User,
    ...     session,
    ...     row_id=123,
    ...     username="new_username",
    ...     email="newemail@example.com"
    ... )
    >>> print(user.updated_at)  # Shows new timestamp
    """
    ensure_base_inheritance(the_class)

    # Prevent ID changes
    if "id" in kwargs and kwargs["id"] != row_id:
        raise ValueError(f"Cannot change row ID: row_id={row_id}, kwargs['id']={kwargs['id']}")

    # Remove ID from update data (don't try to update primary key)
    update_data = {k: v for k, v in kwargs.items() if k != "id"}

    if not update_data:
        logger.warning("No fields to update", table=the_class.__name__, row_id=row_id)
        # Just return existing row
        row = await session.get(the_class, row_id)
        if unexpected(row is None):
            raise KeyError(f"{the_class.__name__} {row_id} not found")
        return cast(T, row)

    logger.debug(
        "Updating row",
        table=the_class.__name__,
        row_id=row_id,
        fields=list(update_data.keys()),
    )

    # Get existing row
    row = await session.get(the_class, row_id)
    if row is None:
        logger.warning("Cannot update - row not found", table=the_class.__name__, row_id=row_id)
        raise KeyError(f"{the_class.__name__} {row_id} not found")

    try:
        # Apply updates
        for var, value in update_data.items():
            setattr(row, var, value)

        # Flush to catch any statement errors
        await session.flush()
        await session.commit()

    except StatementError as err:
        await session.rollback()
        logger.error(
            "Statement error during update",
            table=the_class.__name__,
            row_id=row_id,
            error=str(err),
        )
        raise

    # Refresh to get any database-generated values (e.g., updated_at timestamps)
    await session.refresh(row)
    logger.info("Row updated successfully", table=the_class.__name__, row_id=row_id)
    return row


async def update_rows(
    the_class: type[T],
    session: AsyncSession,
    updates: Sequence[dict[str, Any]],
) -> list[T]:
    """Update multiple rows atomically.

    Each dict in updates must contain an 'id' key specifying which row to update.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to update
    session
        DB session manager
    updates
        Sequence of dicts, each containing 'id' and fields to update

    Returns
    -------
    list[T]
        List of updated rows

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    ValueError
        If any update dict is missing 'id' key
    KeyError
        If any row ID is not found
    StatementError
        If any update is invalid

    Examples
    --------
    >>> users = await update_rows(
    ...     User,
    ...     session,
    ...     [
    ...         {"id": 1, "status": "active"},
    ...         {"id": 2, "status": "active"},
    ...         {"id": 3, "status": "inactive"},
    ...     ]
    ... )
    """
    ensure_base_inheritance(the_class)

    if not updates:
        raise ValueError("updates cannot be empty")

    logger.debug("Updating multiple rows", table=the_class.__name__, count=len(updates))

    updated_rows = []

    try:
        for update_data in updates:
            if "id" not in update_data:
                raise ValueError("Each update must contain 'id' key")

            row_id = update_data["id"]
            fields = {k: v for k, v in update_data.items() if k != "id"}

            row = await session.get(the_class, row_id)
            if row is None:
                raise KeyError(f"{the_class.__name__} {row_id} not found")

            for var, value in fields.items():
                setattr(row, var, value)

            updated_rows.append(row)

        await session.flush()
        await session.commit()

        # Refresh all
        for row in updated_rows:
            await session.refresh(row)

        logger.info(
            "Rows updated successfully",
            table=the_class.__name__,
            count=len(updated_rows),
        )

        return updated_rows

    except Exception as err:
        await session.rollback()
        logger.error("Error during bulk update", table=the_class.__name__, error=str(err))
        raise
