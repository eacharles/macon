"""Database row reading functions for rail-svc.

This module provides functions for retrieving database rows with
different access patterns and performance characteristics:

- get_row: Retrieve single row by primary key
- get_row_by_name: Retrieve single row by name field
- get_rows: Retrieve multiple rows with pagination
- get_rows_streaming: Memory-efficient streaming of large result sets
- get_row_or_none: Retrieve single row by primary key or None
- count_rows: Count total number of rows in a table
"""

from collections.abc import AsyncIterator, Sequence

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from rail_svc.db.base import T, ensure_base_inheritance

from ..common import unexpected

logger = structlog.get_logger(__name__)


async def get_row(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
) -> T:
    """Get a single row by primary key.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    row_id
        Primary key of the row to return

    Returns
    -------
    T
        The matching row

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    KeyError
        If row with given ID does not exist

    Examples
    --------
    >>> user = await get_row(User, session, 123)
    >>> print(user.username)
    """
    ensure_base_inheritance(the_class)

    logger.debug("Getting row by ID", table=the_class.__name__, row_id=row_id)
    result = await session.get(the_class, row_id)

    if result is None:
        logger.warning("Row not found", table=the_class.__name__, row_id=row_id)
        raise KeyError(f"{the_class.__name__} {row_id} not found")

    return result


async def get_row_by_name(
    the_class: type[T],
    session: AsyncSession,
    name: str,
) -> T:
    """Get a single row by name field.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    name
        Name value to search for

    Returns
    -------
    T
        Matching row

    Raises
    ------
    TypeError
        If the_class does not inherit from Base
    AttributeError
        If the_class does not have a 'name' attribute
    KeyError
        If row with given name does not exist

    Notes
    -----
    This function requires the model to have a 'name' attribute.
    For models without a name field, use get_row() or get_rows() with filters.

    Examples
    --------
    >>> user = await get_row_by_name(User, session, "alice")
    >>> print(user.id)
    """
    ensure_base_inheritance(the_class)

    if unexpected(not hasattr(the_class, "name")):
        raise AttributeError(f"{the_class.__name__} does not have a 'name' attribute")

    logger.debug("Getting row by name", table=the_class.__name__, name=name)
    query = select(the_class).where(the_class.name == name)  # type: ignore
    rows = await session.scalars(query)
    row = rows.first()

    if row is None:
        logger.warning("Row not found", table=the_class.__name__, name=name)
        raise KeyError(f"{the_class.__name__} '{name}' not found")

    return row


async def get_rows(
    the_class: type[T],
    session: AsyncSession,
    skip: int = 0,
    limit: int | None = None,
) -> Sequence[T]:
    """Get multiple rows with pagination.

    Note: This method loads all results into memory. For large result sets,
    consider using get_rows_streaming() instead.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    skip
        Number of rows to skip before returning results (offset)
    limit
        Maximum number of rows to return. If None, uses the table's default
        pagination limit from get_pagination_limit()

    Returns
    -------
    Sequence[T]
        All matching rows within the limit

    Raises
    ------
    TypeError
        If the_class does not inherit from Base

    Examples
    --------
    >>> # Get first 10 users
    >>> users = await get_rows(User, session, skip=0, limit=10)
    >>>
    >>> # Get next 10 users
    >>> users = await get_rows(User, session, skip=10, limit=10)
    """
    ensure_base_inheritance(the_class)

    if limit is None:
        limit = the_class.get_pagination_limit()

    logger.debug(
        "Getting rows",
        table=the_class.__name__,
        skip=skip,
        limit=limit,
    )

    q = select(the_class).offset(skip).limit(limit)
    results = await session.scalars(q)
    return results.all()


async def get_rows_streaming(
    the_class: type[T],
    session: AsyncSession,
    skip: int = 0,
    limit: int | None = None,
) -> AsyncIterator[T]:
    """Get rows as an async iterator for memory-efficient processing.

    Use this for large result sets to avoid loading everything into memory.
    Rows are yielded one at a time as they're retrieved from the database.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    skip
        Number of rows to skip before returning results (offset)
    limit
        Maximum number of rows to return. If None, uses the table's default
        pagination limit from get_pagination_limit()

    Yields
    ------
    T
        Individual rows one at a time

    Raises
    ------
    TypeError
        If the_class does not inherit from Base

    Examples
    --------
    >>> # Process large dataset without loading all into memory
    >>> async for user in get_rows_streaming(User, session, limit=100000):
    ...     await process_user(user)
    """
    ensure_base_inheritance(the_class)

    if limit is None:
        limit = the_class.get_pagination_limit()

    logger.debug(
        "Streaming rows",
        table=the_class.__name__,
        skip=skip,
        limit=limit,
    )

    q = select(the_class).offset(skip).limit(limit)
    result = await session.stream_scalars(q)

    async for row in result:
        yield row


async def get_row_or_none(
    the_class: type[T],
    session: AsyncSession,
    row_id: int,
) -> T | None:
    """Get a single row by ID, returning None if not found.

    Similar to get_row() but returns None instead of raising KeyError.
    Useful when you want to handle missing rows without exceptions.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager
    row_id
        Primary key of the row to return

    Returns
    -------
    T
        The matching row or None if it is not found
    """
    ensure_base_inheritance(the_class)

    logger.debug("Getting row by ID (or None)", table=the_class.__name__, row_id=row_id)
    result = await session.get(the_class, row_id)

    if result is None:
        logger.debug("Row not found", table=the_class.__name__, row_id=row_id)

    return result


async def count_rows(
    the_class: type[T],
    session: AsyncSession,
) -> int:
    """Count total number of rows in a table.

    Useful for pagination metadata.

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to query
    session
        DB session manager

    Returns
    -------
    int
        Total number of rows in the table
    """
    ensure_base_inheritance(the_class)

    logger.debug("Counting rows", table=the_class.__name__)
    q = select(func.count()).select_from(the_class)  # pylint: disable=not-callable
    result = await session.execute(q)
    count = result.scalar_one()

    logger.debug("Row count", table=the_class.__name__, count=count)
    return count


async def lookup_by_id_or_name(
    the_class: type[T],
    session: AsyncSession,
    row_id: int | None,
    name: str | None,
    *,
    need_object: bool = False,
) -> tuple[int, T | None]:
    """Look up a database record by ID or name.

    This is a generic helper function for resolving foreign keys. It handles
    the common pattern of accepting either an ID (fast) or a name (lookup required).

    Parameters
    ----------
    the_class
        The SQLAlchemy model class to look up
    session
        Database session
    row_id
        Primary key ID if known (provide this OR name)
    name
        Record name to look up (provide this OR id_)
    need_object
        Whether to fetch and return the full object.
        - If True: Always fetches the object and returns (id, object)
        - If False and id_ provided: Returns (id, None) without database query
        - If False and name provided: Must fetch to get ID, returns (id, object)

    Returns
    -------
    tuple[int, T | None]
        A tuple of (id, object) where:
        - id: The primary key (always present)
        - object: The database object (present if need_object=True or if looked up by name)

    Raises
    ------
    ValueError
        If neither id_ nor name provided, or if lookup fails

    Examples
    --------
    Lookup by ID without fetching object:

    >>> algo_id, algo_obj = await lookup_by_id_or_name(
    ...     Algorithm,
    ...     session,
    ...     row_id=123,
    ...     name=None,
    ...     need_object=False
    ... )
    >>> assert algo_id == 123
    >>> assert algo_obj is None  # Not fetched

    Lookup by ID with object:

    >>> algo_id, algo_obj = await lookup_by_id_or_name(
    ...     Algorithm,
    ...     session,
    ...     row_id=123,
    ...     name=None,
    ...     need_object=True
    ... )
    >>> assert algo_id == 123
    >>> assert algo_obj.name == "RandomForest"  # Object fetched

    Lookup by name (always returns object):

    >>> algo_id, algo_obj = await lookup_by_id_or_name(
    ...     Algorithm,
    ...     session,
    ...     row_id=None,
    ...     name="RandomForest",
    ...     need_object=False  # Ignored - must fetch to get ID
    ... )
    >>> assert algo_id == 123
    >>> assert algo_obj is not None  # Always fetched when lookup by name

    Notes
    -----
    When looking up by name, the object is always fetched (regardless of
    need_object) because we need to get the ID. When looking up by ID and
    need_object=False, no database query is made.
    """
    if row_id is None:
        if name is None:
            logger.error(
                "Missing identifier for lookup",
                table=the_class.__name__,
            )
            raise ValueError(f"Either 'id_' or 'name' must be provided for {the_class.__name__}")

        # Look up by name - must fetch object to get ID
        try:
            the_object = await get_row_by_name(the_class, session, name)
            logger.debug(
                "Record found by name",
                table=the_class.__name__,
                name=name,
                id=the_object.id_,
            )
            return the_object.id_, the_object  # type: ignore
        except NoResultFound as uexc:
            logger.error(
                "Record not found by name",
                table=the_class.__name__,
                name=name,
                error=uexc,
            )
            raise ValueError(f"{the_class.__name__} with name '{name}' not found") from None
    else:
        # Have ID - fetch object only if needed
        if need_object:
            try:
                the_object = await get_row(the_class, session, row_id)
                logger.debug(
                    "Record found by ID",
                    table=the_class.__name__,
                    id=row_id,
                )
                return row_id, the_object
            except NoResultFound as uexc:
                logger.error(
                    "Record not found by ID",
                    table=the_class.__name__,
                    id=row_id,
                    error=uexc,
                )
                raise ValueError(f"{the_class.__name__} with ID {row_id} not found") from None
        else:
            # Have ID and don't need object - return immediately
            logger.debug(
                "Using provided ID without fetching",
                table=the_class.__name__,
                id=row_id,
            )
            return row_id, None
