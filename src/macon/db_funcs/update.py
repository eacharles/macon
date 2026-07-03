"""Database row update functions."""

from collections.abc import Sequence
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import T, ensure_base_inheritance

from ..common import unexpected

logger = structlog.get_logger(__name__)


async def update_row(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
    **kwargs: Any,
) -> T:
    """Update a single row by primary key.

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

    Raises
    ------
    ValueError
        If attempting to change the row's ID
    KeyError
        If row with given ID does not exist
    """
    ensure_base_inheritance(the_class)

    if "id" in kwargs and kwargs["id"] != row_id:
        raise ValueError(f"Cannot change row ID: row_id={row_id}, kwargs['id']={kwargs['id']}")

    update_data = {k: v for k, v in kwargs.items() if k != "id"}

    if not update_data:
        logger.warning("No fields to update", table=the_class.__name__, row_id=row_id)
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

    row = await session.get(the_class, row_id)
    if row is None:
        logger.warning("Cannot update - row not found", table=the_class.__name__, row_id=row_id)
        raise KeyError(f"{the_class.__name__} {row_id} not found")

    for var, value in update_data.items():
        setattr(row, var, value)

    await session.flush()

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

    Raises
    ------
    ValueError
        If any update dict is missing 'id' key, or updates is empty
    KeyError
        If any row ID is not found
    """
    ensure_base_inheritance(the_class)

    if not updates:
        raise ValueError("updates cannot be empty")

    logger.debug("Updating multiple rows", table=the_class.__name__, count=len(updates))

    updated_rows = []

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

    logger.info(
        "Rows updated successfully",
        table=the_class.__name__,
        count=len(updated_rows),
    )

    return updated_rows
