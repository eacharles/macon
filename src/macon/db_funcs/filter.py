"""Database row filtering functions for rail-svc.

This module provides flexible filtering capabilities for database queries
with support for various comparison operators, logical operators, and
efficient streaming for large result sets.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import structlog
from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import T, ensure_base_inheritance

from ..common import unexpected
from ..models.filtering import Filter, FilterOp, OrderBy

logger = structlog.get_logger(__name__)


def _apply_filter(
    query: Select,
    the_class: type[T],
    filter_obj: Filter,
) -> Select:
    """Apply a single filter to a query.

    Parameters
    ----------
    query
        SQLAlchemy select statement
    the_class
        The model class being queried
    filter_obj
        Filter to apply

    Returns
    -------
        Modified query with filter applied

    Raises
    ------
    AttributeError
        If field doesn't exist on the model
    ValueError
        If filter operator is invalid or value is wrong type
    """
    # Verify field exists
    if not hasattr(the_class, filter_obj.field):
        raise AttributeError(f"{the_class.__name__} does not have field '{filter_obj.field}'")

    field = getattr(the_class, filter_obj.field)

    # Apply operator
    if filter_obj.op == FilterOp.EQ:
        query = query.where(field == filter_obj.value)

    elif filter_obj.op == FilterOp.NE:
        query = query.where(field != filter_obj.value)

    elif filter_obj.op == FilterOp.LT:
        query = query.where(field < filter_obj.value)

    elif filter_obj.op == FilterOp.LE:
        query = query.where(field <= filter_obj.value)

    elif filter_obj.op == FilterOp.GT:
        query = query.where(field > filter_obj.value)

    elif filter_obj.op == FilterOp.GE:
        query = query.where(field >= filter_obj.value)

    elif filter_obj.op == FilterOp.IN:
        if not isinstance(filter_obj.value, list | tuple | set):
            raise ValueError(f"IN operator requires list/tuple/set, got {type(filter_obj.value)}")
        query = query.where(field.in_(filter_obj.value))

    elif filter_obj.op == FilterOp.NOT_IN:
        if unexpected(not isinstance(filter_obj.value, list | tuple | set)):
            raise ValueError(f"NOT_IN operator requires list/tuple/set, got {type(filter_obj.value)}")
        query = query.where(field.not_in(filter_obj.value))

    elif filter_obj.op == FilterOp.LIKE:
        query = query.where(field.like(filter_obj.value))

    elif filter_obj.op == FilterOp.ILIKE:
        query = query.where(field.ilike(filter_obj.value))

    elif filter_obj.op == FilterOp.IS_NULL:  # pragma: no cover
        query = query.where(field.is_(None))

    elif filter_obj.op == FilterOp.IS_NOT_NULL:
        query = query.where(field.is_not(None))

    elif filter_obj.op == FilterOp.BETWEEN:
        if not isinstance(filter_obj.value, list | tuple) or len(filter_obj.value) != 2:
            raise ValueError("BETWEEN operator requires list/tuple of exactly 2 values")
        query = query.where(field.between(filter_obj.value[0], filter_obj.value[1]))

    elif filter_obj.op == FilterOp.CONTAINS:
        # PostgreSQL array contains
        query = query.where(field.contains(filter_obj.value))

    elif filter_obj.op == FilterOp.STARTS_WITH:
        if not isinstance(filter_obj.value, str):
            raise ValueError("STARTS_WITH operator requires string value")
        query = query.where(field.like(f"{filter_obj.value}%"))

    elif filter_obj.op == FilterOp.ENDS_WITH:
        if not isinstance(filter_obj.value, str):
            raise ValueError("ENDS_WITH operator requires string value")
        query = query.where(field.like(f"%{filter_obj.value}"))

    else:  # pragma: no cover
        raise ValueError(f"Unknown filter operator: {filter_obj.op}")

    return query


def _apply_ordering(
    query: Select,
    the_class: type[T],
    order_by: OrderBy | list[OrderBy],
) -> Select:
    """Apply ordering to a query.

    Parameters
    ----------
    query
        SQLAlchemy select statement
    the_class
        The model class being queried
    order_by
        Single OrderBy or list of OrderBy directives

    Returns
    -------
        Modified query with ordering applied

    Raises
    ------
    AttributeError
        If field doesn't exist on the model
    """
    # Normalize to list
    if not isinstance(order_by, list):
        order_by = [order_by]

    for order in order_by:
        if not hasattr(the_class, order.field):
            raise AttributeError(f"{the_class.__name__} does not have field '{order.field}'")

        field = getattr(the_class, order.field)
        query = query.order_by(desc(field) if order.descending else asc(field))

    return query


async def filter_rows(
    the_class: type[T],
    session: AsyncSession,
    filters: list[Filter] | None = None,
    logical_op: str = "and",
    order_by: OrderBy | list[OrderBy] | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> Sequence[T]:
    """Filter rows based on conditions with pagination.

    Note: This method loads all results into memory. For large result sets,
    consider using filter_rows_streaming() instead.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    filters
        List of Filter objects to apply. If None, returns all rows.
    logical_op
        How to combine multiple filters: "and" (all must match) or
        "or" (any must match). Default is "and".
    order_by
        Single OrderBy or list of OrderBy directives for sorting results
    skip
        Number of rows to skip before returning results (offset)
    limit
        Maximum number of rows to return. If None, uses table's default
        pagination limit from get_pagination_limit()

    Returns
    -------
        All matching rows within the limit

    Raises
    ------
    AttributeError
        If any filter references a non-existent field
    ValueError
        If logical_op is not "and" or "or", or filter values are invalid

    Examples
    --------
    >>> # Find all active users over 18
    >>> users = await filter_rows(
    ...     User,
    ...     session,
    ...     filters=[
    ...         Filter("status", FilterOp.EQ, "active"),
    ...         Filter("age", FilterOp.GT, 18),
    ...     ],
    ...     order_by=OrderBy("created_at", descending=True),
    ...     limit=10
    ... )
    >>>
    >>> # Find users with specific usernames (OR logic)
    >>> users = await filter_rows(
    ...     User,
    ...     session,
    ...     filters=[
    ...         Filter("username", FilterOp.EQ, "alice"),
    ...         Filter("username", FilterOp.EQ, "bob"),
    ...     ],
    ...     logical_op="or"
    ... )
    >>>
    >>> # Find users created in date range
    >>> from datetime import datetime
    >>> users = await filter_rows(
    ...     User,
    ...     session,
    ...     filters=[
    ...         Filter("created_at", FilterOp.BETWEEN, [
    ...             datetime(2024, 1, 1),
    ...             datetime(2024, 12, 31)
    ...         ])
    ...     ]
    ... )
    """
    ensure_base_inheritance(the_class)

    if logical_op not in ("and", "or"):
        raise ValueError("logical_op must be 'and' or 'or'")

    if limit is None:
        limit = the_class.get_pagination_limit()

    logger.debug(
        "Filtering rows",
        table=the_class.__name__,
        filter_count=len(filters) if filters else 0,
        logical_op=logical_op,
        skip=skip,
        limit=limit,
    )

    # Start with base query
    query = select(the_class)

    # Apply filters
    if filters:
        if logical_op == "and":
            # Apply each filter directly (implicit AND)
            for filter_obj in filters:
                query = _apply_filter(query, the_class, filter_obj)
        else:
            # OR logic - build list of conditions
            conditions = []
            for filter_obj in filters:
                # Create a temporary query to extract the condition
                temp_query = select(the_class)
                temp_query = _apply_filter(temp_query, the_class, filter_obj)
                # Extract the WHERE clause
                if temp_query.whereclause is not None:
                    conditions.append(temp_query.whereclause)

            if conditions:
                query = query.where(or_(*conditions))

    # Apply ordering
    if order_by:
        query = _apply_ordering(query, the_class, order_by)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    results = await session.scalars(query)
    rows = results.all()

    logger.debug("Filtered rows retrieved", table=the_class.__name__, result_count=len(rows))

    return rows


async def filter_rows_streaming(
    the_class: type[T],
    session: AsyncSession,
    filters: list[Filter] | None = None,
    logical_op: str = "and",
    order_by: OrderBy | list[OrderBy] | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> AsyncIterator[T]:
    """Filter rows as an async iterator for memory-efficient processing.

    Use this for large result sets to avoid loading everything into memory.
    Rows are yielded one at a time as they're retrieved from the database.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    filters
        List of Filter objects to apply. If None, returns all rows.
    logical_op
        How to combine multiple filters: "and" or "or". Default is "and".
    order_by
        Single OrderBy or list of OrderBy directives for sorting results
    skip
        Number of rows to skip before returning results (offset)
    limit
        Maximum number of rows to return. If None, uses table's default
        pagination limit from get_pagination_limit()

    Yields
    ------
        Individual rows one at a time

    Raises
    ------
    AttributeError
        If any filter references a non-existent field
    ValueError
        If logical_op is not "and" or "or", or filter values are invalid

    Examples
    --------
    >>> # Process large result set without loading all into memory
    >>> async for user in filter_rows_streaming(
    ...     User,
    ...     session,
    ...     filters=[Filter("status", FilterOp.EQ, "active")],
    ...     limit=100000
    ... ):
    ...     await process_user(user)
    """
    ensure_base_inheritance(the_class)

    if unexpected(logical_op not in ("and", "or")):
        raise ValueError("logical_op must be 'and' or 'or'")

    if limit is None:
        limit = the_class.get_pagination_limit()

    logger.debug(
        "Streaming filtered rows",
        table=the_class.__name__,
        filter_count=len(filters) if filters else 0,
        logical_op=logical_op,
        skip=skip,
        limit=limit,
    )

    # Start with base query
    query = select(the_class)

    # Apply filters
    if filters:
        if logical_op == "and":
            for filter_obj in filters:
                query = _apply_filter(query, the_class, filter_obj)
        else:
            conditions = []
            for filter_obj in filters:
                temp_query = select(the_class)
                temp_query = _apply_filter(temp_query, the_class, filter_obj)
                if temp_query.whereclause is not None:
                    conditions.append(temp_query.whereclause)

            if conditions:
                query = query.where(or_(*conditions))

    # Apply ordering
    if order_by:  # pragma: no cover
        query = _apply_ordering(query, the_class, order_by)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Stream results
    result = await session.stream_scalars(query)

    async for row in result:
        yield row


async def count_filtered_rows(
    the_class: type[T],
    session: AsyncSession,
    filters: list[Filter] | None = None,
    logical_op: str = "and",
) -> int:
    """Count rows matching filter criteria.

    Useful for pagination metadata (e.g., "showing 10 of 245 results").

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    filters
        List of Filter objects to apply. If None, counts all rows.
    logical_op
        How to combine multiple filters: "and" or "or". Default is "and".

    Returns
    -------
        Number of rows matching the filter criteria

    Raises
    ------
    AttributeError
        If any filter references a non-existent field
    ValueError
        If logical_op is not "and" or "or", or filter values are invalid

    Examples
    --------
    >>> # Count active users
    >>> count = await count_filtered_rows(
    ...     User,
    ...     session,
    ...     filters=[Filter("status", FilterOp.EQ, "active")]
    ... )
    >>> print(f"Found {count} active users")
    """
    ensure_base_inheritance(the_class)

    if unexpected(logical_op not in ("and", "or")):
        raise ValueError("logical_op must be 'and' or 'or'")

    logger.debug(
        "Counting filtered rows",
        table=the_class.__name__,
        filter_count=len(filters) if filters else 0,
        logical_op=logical_op,
    )

    # Start with count query
    query = select(func.count()).select_from(the_class)  # pylint: disable=not-callable

    # Apply filters
    if filters:
        if logical_op == "and":
            for filter_obj in filters:
                query = _apply_filter(query, the_class, filter_obj)
        else:
            conditions = []
            for filter_obj in filters:
                temp_query = select(the_class)
                temp_query = _apply_filter(temp_query, the_class, filter_obj)
                if temp_query.whereclause is not None:
                    conditions.append(temp_query.whereclause)

            if conditions:
                query = query.where(or_(*conditions))

    # Execute count
    result = await session.execute(query)
    count = result.scalar_one()

    logger.debug("Filtered row count", table=the_class.__name__, count=count)

    return count


async def filter_one(
    the_class: type[T],
    session: AsyncSession,
    filters: list[Filter],
    logical_op: str = "and",
) -> T:
    """Filter for exactly one row matching criteria.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    filters
        List of Filter objects to apply
    logical_op
        How to combine multiple filters: "and" or "or". Default is "and".

    Returns
    -------
        The single matching row

    Raises
    ------
    AttributeError
        If any filter references a non-existent field
    ValueError
        If logical_op is not "and" or "or", or filter values are invalid
    KeyError
        If no rows match the criteria or multiple rows match

    Examples
    --------
    >>> # Get user by email (should be unique)
    >>> user = await filter_one(
    ...     User,
    ...     session,
    ...     filters=[Filter("email", FilterOp.EQ, "alice@example.com")]
    ... )
    """
    ensure_base_inheritance(the_class)

    logger.debug(
        "Filtering for single row",
        table=the_class.__name__,
        filter_count=len(filters),
        logical_op=logical_op,
    )

    # Get up to 2 results to check for duplicates
    results = await filter_rows(the_class, session, filters=filters, logical_op=logical_op, skip=0, limit=2)

    if len(results) == 0:
        logger.warning("No rows found matching filters", table=the_class.__name__)
        raise KeyError(f"No {the_class.__name__} found matching filters")

    if len(results) > 1:
        logger.warning(
            "Multiple rows found matching filters",
            table=the_class.__name__,
            count=len(results),
        )
        raise KeyError(f"Multiple {the_class.__name__} rows found matching filters")

    return results[0]


async def filter_one_or_none(
    the_class: type[T],
    session: AsyncSession,
    filters: list[Filter],
    logical_op: str = "and",
) -> T | None:
    """Filter for at most one row matching criteria.

    Similar to filter_one() but returns None instead of raising KeyError
    when no rows are found.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    filters
        List of Filter objects to apply
    logical_op
        How to combine multiple filters: "and" or "or". Default is "and".

    Returns
    -------
        The single matching row, or None if no match found

    Raises
    ------
    AttributeError
        If any filter references a non-existent field
    ValueError
        If logical_op is not "and" or "or", or filter values are invalid
    KeyError
        If multiple rows match the criteria

    Examples
    --------
    >>> # Try to get user by username
    >>> user = await filter_one_or_none(
    ...     User,
    ...     session,
    ...     filters=[Filter("username", FilterOp.EQ, "alice")]
    ... )
    >>> if user is None:
    ...     print("User not found")
    """
    ensure_base_inheritance(the_class)

    logger.debug(
        "Filtering for single row (or none)",
        table=the_class.__name__,
        filter_count=len(filters),
        logical_op=logical_op,
    )

    # Get up to 2 results to check for duplicates
    results = await filter_rows(the_class, session, filters=filters, logical_op=logical_op, skip=0, limit=2)

    if len(results) == 0:
        logger.debug("No rows found matching filters", table=the_class.__name__)
        return None

    if len(results) > 1:
        logger.warning(
            "Multiple rows found matching filters",
            table=the_class.__name__,
            count=len(results),
        )
        raise KeyError(f"Multiple {the_class.__name__} rows found matching filters")

    return results[0]


# Convenience function for simple equality filters
async def find_by(
    the_class: type[T],
    session: AsyncSession,
    order_by: OrderBy | list[OrderBy] | None = None,
    skip: int = 0,
    limit: int | None = None,
    **kwargs: Any,
) -> Sequence[T]:
    """Find rows by simple equality conditions.

    This is a convenience wrapper around filter_rows() for the common case
    of filtering by exact field values.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    order_by
        Single OrderBy or list of OrderBy directives for sorting results
    skip
        Number of rows to skip before returning results (offset)
    limit
        Maximum number of rows to return
    **kwargs
        Field names and values to filter by (all must match - AND logic)

    Returns
    -------
        All matching rows

    Raises
    ------
    AttributeError
        If any field doesn't exist on the model

    Examples
    --------
    >>> # Find all active users in a specific role
    >>> users = await find_by(
    ...     User,
    ...     session,
    ...     status="active",
    ...     role="admin",
    ...     order_by=OrderBy("username")
    ... )
    >>>
    >>> # Find users created by specific user
    >>> users = await find_by(
    ...     User,
    ...     session,
    ...     created_by_id=123,
    ...     limit=10
    ... )
    """
    ensure_base_inheritance(the_class)

    # Convert kwargs to Filter objects
    filters = [Filter(field=field, op=FilterOp.EQ, value=value) for field, value in kwargs.items()]

    return await filter_rows(
        the_class,
        session,
        filters=filters,
        logical_op="and",
        order_by=order_by,
        skip=skip,
        limit=limit,
    )


async def find_one_by(
    the_class: type[T],
    session: AsyncSession,
    **kwargs: Any,
) -> T:
    """Find exactly one row by simple equality conditions.

    Convenience wrapper around filter_one() for exact field matches.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    **kwargs
        Field names and values to filter by (all must match)

    Returns
    -------
        The single matching row

    Raises
    ------
    AttributeError
        If any field doesn't exist on the model
    KeyError
        If no rows match or multiple rows match

    Examples
    --------
    >>> # Find user by email (should be unique)
    >>> user = await find_one_by(User, session, email="alice@example.com")
    >>>
    >>> # Find session by token
    >>> session_obj = await find_one_by(Session, session, token="abc123")
    """
    ensure_base_inheritance(the_class)

    filters = [Filter(field=field, op=FilterOp.EQ, value=value) for field, value in kwargs.items()]

    return await filter_one(the_class, session, filters=filters)


# Helper function to build complex filter combinations
def and_filters(*filters: Filter) -> list[Filter]:
    """Combine filters with AND logic.

    This is just a helper to make it explicit that filters will be ANDed.

    Examples
    --------
    >>> filters = and_filters(
    ...     Filter("status", FilterOp.EQ, "active"),
    ...     Filter("age", FilterOp.GT, 18),
    ... )
    >>> users = await filter_rows(User, session, filters=filters)
    """
    return list(filters)


def or_filters(*filters: Filter) -> list[Filter]:
    """Combine filters with OR logic.

    Helper to make it explicit that filters will be ORed.
    Use with logical_op="or" parameter.

    Examples
    --------
    >>> filters = or_filters(
    ...     Filter("status", FilterOp.EQ, "active"),
    ...     Filter("status", FilterOp.EQ, "pending"),
    ... )
    >>> users = await filter_rows(User, session, filters=filters, logical_op="or")
    """
    return list(filters)
