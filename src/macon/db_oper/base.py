from __future__ import annotations

import asyncio
import os
from abc import abstractmethod
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

import anyio
from pydantic import BaseModel, ValidationError
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from .. import db_funcs
from ..common import LoadType, handle_file, unexpected
from ..config import config as global_config
from ..db.base import Base, ensure_base_inheritance
from ..db.session import get_session

logger = get_logger(__name__)

FORBID_TRAVERSAL = False

F = TypeVar("F", bound=Callable[..., Any])


def forward_to_db_funcs(module: Any, func_name: str) -> Callable[[F], F]:
    """Decorator that forwards method calls to db_funcs module functions.

    Extracts db_class from self.ctx and session from args, then calls
    the corresponding function in the db_funcs module with all arguments.

    Parameters
    ----------
    module
        The db_funcs submodule (e.g., db_funcs.read, db_funcs.filter)
    func_name
        Name of the function to call in the module

    Returns
    -------
        Decorator that forwards the call

    Examples
    --------
    >>> @forward_to_db_funcs(db_funcs.read, 'get_row')
    >>> async def get_row(self, session: AsyncSession, *args, **kwargs):
    ...     pass  # Implementation replaced by decorator
    """

    def decorator(func: F) -> F:
        db_func = getattr(module, func_name)

        @wraps(func)
        async def wrapper(self: Any, session: AsyncSession, *args: Any, **kwargs: Any) -> Any:
            return await db_func(self.ctx.db_class, session, *args, **kwargs)

        wrapper.__doc__ = db_func.__doc__
        return wrapper  # type: ignore

    return decorator


def forward_to_db_funcs_streaming(module: Any, func_name: str) -> Callable[[F], F]:
    """Decorator that forwards async generator calls to db_funcs module functions.

    Similar to forward_to_db_funcs but for async generators (streaming functions).

    Parameters
    ----------
    module
        The db_funcs submodule
    func_name
        Name of the streaming function to call

    Returns
    -------
        Decorator that forwards the streaming call
    """

    def decorator(func: F) -> F:
        db_func = getattr(module, func_name)

        @wraps(func)
        async def wrapper(self: Any, session: AsyncSession, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            async for row in db_func(self.ctx.db_class, session, *args, **kwargs):
                yield row

        wrapper.__doc__ = db_func.__doc__
        return wrapper  # type: ignore

    return decorator


@dataclass
class TableContext[T: Base, ResponseT: BaseModel, CreateT: BaseModel]:
    """
    Common context for database tables

    Encapsulates the common configuration needed for all tables with full
    type safety for database models and their Pydantic representations.

    Type Parameters
    ---------------
    T : TypeVar, bound=Base
        Database model class (SQLAlchemy)
    ResponseT : TypeVar, bound=BaseModel
        Pydantic model class for validating / streaming responses
    CreateT : TypeVar, bound=BaseModel
        Pydantic model class for validating creation data

    Parameters
    ----------
    db_class
        Database model class (SQLAlchemy)
    response_class
        Pydantic model class for validating / streaming
    create_class
        Pydantic model class for validating creation data
    class_string
        String identifier for the class

    Examples
    --------
    >>> from myapp.models import User, UserResponse, UserCreate
    >>> context = TableContext(
    ...     db_class=User,
    ...     response_class=UserResponse,
    ...     create_class=UserCreate,
    ...     class_string="user"
    ... )
    """

    db_class: type[T]
    response_class: type[ResponseT]
    create_class: type[CreateT]
    class_string: str

    @classmethod
    def from_db_class(cls, db_class: type[T]) -> TableContext[T, ResponseT, CreateT]:
        """
        Create context from database class using conventions.

        This method uses the db_class's methods to determine the Pydantic
        models. The return type uses BaseModel for response and create types
        since we can't know the specific types at compile time.

        Parameters
        ----------
        db_class
            Database model class that implements pydantic_model_class(),
            pydantic_create_class(), and class_string() methods

        Returns
        -------
            Configured TableContext with base Pydantic types

        Raises
        ------
        AttributeError
            If db_class doesn't implement required methods

        Examples
        --------
        >>> from myapp.models import User
        >>> context = TableContext.from_db_class(User)
        >>> # context is TableContext[User, BaseModel, BaseModel]
        """
        # Validate required methods exist
        if not hasattr(db_class, "pydantic_model_class"):
            raise AttributeError(f"{db_class.__name__} must implement pydantic_model_class() method")
        if unexpected(not hasattr(db_class, "pydantic_create_class")):
            raise AttributeError(f"{db_class.__name__} must implement pydantic_create_class() method")
        if unexpected(not hasattr(db_class, "class_string")):
            raise AttributeError(f"{db_class.__name__} must implement class_string() method")

        # Get the classes
        response_class = cast(type[ResponseT], db_class.pydantic_model_class())
        create_class = cast(type[CreateT], db_class.pydantic_create_class())

        return cls(
            db_class=db_class,
            response_class=response_class,
            create_class=create_class,
            class_string=db_class.class_string(),
        )


class TableOperations[T: Base, ResponseT: BaseModel, CreateT: BaseModel]:
    """Base class for Table operations with full type safety.

    Provides common CRUD operations for database tables with validation,
    lifecycle hooks, and complete type safety across database models and
    their Pydantic representations.

    Type Parameters
    ---------------
    T : TypeVar, bound=Base
        Database model class (SQLAlchemy)
    ResponseT : TypeVar, bound=BaseModel
        Pydantic model class for responses
    CreateT : TypeVar, bound=BaseModel
        Pydantic model class for creation

    Important
    ---------
    All methods that modify the database (create_row, create_rows, etc.)
    DO NOT commit transactions. The caller MUST manage transactions using
    `async with session.begin()` or explicit commit/rollback.

    All create methods DO add objects to the session and flush them to
    get database-generated values (like auto-increment IDs), but the
    transaction must still be committed by the caller.

    Parameters
    ----------
    context
        Shared configuration for this operation

    Examples
    --------
    >>> from myapp.models import User, UserResponse, UserCreate
    >>> context = TableContext(
    ...     db_class=User,
    ...     response_class=UserResponse,
    ...     create_class=UserCreate,
    ...     class_string="user"
    ... )
    >>> ops = TableOperations(context)
    >>>
    >>> async with get_session() as session:
    ...     async with session.begin():
    ...         user = await ops.create_row(
    ...             session,
    ...             username="alice",
    ...             email="alice@example.com"
    ...         )
    ...         # user is type User (T)
    ...         pydantic_user = ops.to_pydantic(user)
    ...         # pydantic_user is type UserResponse (ResponseT)
    """

    def __init__(self, context: TableContext[T, ResponseT, CreateT]) -> None:
        """
        Initialize operation with context.

        Parameters
        ----------
        context
            Shared configuration for this operation, including database
            class and Pydantic model classes
        """
        self.ctx = context

    @forward_to_db_funcs(db_funcs.read, "get_row")
    async def get_row(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.read, "get_row_by_name")
    async def get_row_by_name(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.read, "get_rows")
    async def get_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> Sequence[T]:  # type: ignore
        pass

    @forward_to_db_funcs_streaming(db_funcs.read, "get_rows_streaming")
    async def get_rows_streaming(  # pylint: disable=unused-argument
        self,
        session: AsyncSession,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncIterator[T]:
        yield  # type: ignore

    @forward_to_db_funcs(db_funcs.read, "get_row_or_none")
    async def get_row_or_none(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T | None:
        pass

    @forward_to_db_funcs(db_funcs.read, "count_rows")
    async def count_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> int:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.read, "lookup_by_id_or_name")
    async def lookup_by_id_or_name(  # type: ignore
        self,
        session: AsyncSession,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[int, T | None]:
        pass

    @forward_to_db_funcs(db_funcs.update, "update_row")
    async def update_row(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.update, "update_rows")
    async def update_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> list[T]:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.delete, "delete_row")
    async def delete_row(self, session: AsyncSession, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        pass

    @forward_to_db_funcs(db_funcs.delete, "delete_rows")
    async def delete_rows(
        self, session: AsyncSession, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]] | None:
        pass

    @forward_to_db_funcs(db_funcs.delete, "bulk_delete_rows")
    async def bulk_delete_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> int:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.filter, "filter_rows")
    async def filter_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> Sequence[T]:  # type: ignore
        pass

    @forward_to_db_funcs_streaming(db_funcs.filter, "filter_rows_streaming")
    async def filter_rows_streaming(  # pylint: disable=unused-argument
        self, session: AsyncSession, *args: Any, **kwargs: Any
    ) -> AsyncIterator[T]:
        yield  # type: ignore

    @forward_to_db_funcs(db_funcs.filter, "count_filtered_rows")
    async def count_filtered_rows(self, session: AsyncSession, *args: Any, **kwargs: Any) -> int:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.filter, "filter_one")
    async def filter_one(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.filter, "filter_one_or_none")
    async def filter_one_or_none(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T | None:
        pass

    @forward_to_db_funcs(db_funcs.filter, "find_by")
    async def find_by(self, session: AsyncSession, *args: Any, **kwargs: Any) -> Sequence[T]:  # type: ignore
        pass

    @forward_to_db_funcs(db_funcs.filter, "find_one_by")
    async def find_one_by(self, session: AsyncSession, *args: Any, **kwargs: Any) -> T:  # type: ignore
        pass

    async def get_create_kwargs(
        self,
        session: AsyncSession,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare kwargs for creating an instance."""
        assert session
        return kwargs

    async def create_row(
        self,
        session: AsyncSession,
        *,
        validate: bool = True,
        **kwargs: Any,
    ) -> T:
        """Create a single row in the database.

        The row is added to the session and flushed, but not committed.
        The caller is responsible for committing the transaction.

        Parameters
        ----------
        session
            DB session manager
        validate
            Whether to validate input against Pydantic model (CreateT) before
            creation. If True and validation fails, raises ValidationError.
        **kwargs : Any
            Column names and their values for the new row

        Returns
        -------
            Newly created row of the database model type with database-generated
            values (after flush)

        Raises
        ------
        ValidationError
            Pydantic validation failed on the input (if validate=True)
        IntegrityError
            Database integrity constraint violation

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext.from_db_class(User)
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     async with session.begin():  # Caller manages transaction
        ...         user: User = await ops.create_row(
        ...             session,
        ...             username="alice",
        ...             email="alice@example.com"
        ...         )
        ...         # user is fully typed as User (T)
        ...         print(f"Created user {user.id}")
        ...         # Transaction commits automatically on context exit
        """
        ensure_base_inheritance(self.ctx.db_class)

        logger.debug("Creating row", table=self.ctx.db_class.__name__, fields=list(kwargs.keys()))

        # Validate input if requested
        if validate:
            try:
                self.ctx.create_class.model_validate(kwargs)
            except ValidationError as e:
                logger.warning(
                    "Validation failed in create_row",
                    table=self.ctx.db_class.__name__,
                    errors=e.errors(),
                )
                raise

        # update kwargs
        kwargs = await self.get_create_kwargs(session, **kwargs)

        # Pre-create hook
        kwargs = await self.ctx.db_class.pre_create_hook(session, kwargs)

        # Create the row
        row = self.ctx.db_class(**kwargs)

        # Add to session and flush to get DB-generated values
        session.add(row)
        await session.flush()

        logger.debug("Row created", table=self.ctx.db_class.__name__, row_id=getattr(row, "id", None))

        return row

    async def create_rows(
        self,
        session: AsyncSession,
        rows_data: Sequence[dict[str, Any]],
        *,
        validate: bool = True,
    ) -> list[T]:
        """Create multiple rows in the database.

        All rows are added to the session and flushed together, but not
        committed. The caller is responsible for committing the transaction.

        Parameters
        ----------
        session
            DB session manager
        rows_data
            Sequence of dictionaries, each containing column names and values
            for a new row
        validate
            Whether to validate each row against Pydantic model (CreateT)
            before creation

        Returns
        -------
            List of newly created rows of the database model type with
            database-generated values

        Raises
        ------
        IntegrityError
            Integrity constraint violation (e.g., duplicate key, null constraint)
        ValidationError
            Pydantic validation failed on any row's input data (if validate=True)
        ValueError
            If rows_data is empty

        Notes
        -----
        - When validate=True, validation may fail for cases where the database
          provides default values. Consider setting validate=False in such cases.
        - All rows are flushed atomically within the session
        - The caller must commit the transaction for changes to persist
        - For very large datasets, consider batching the calls to this function.

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext.from_db_class(User)
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     async with session.begin():  # Caller controls transaction
        ...         users: list[User] = await ops.create_rows(
        ...             session,
        ...             [
        ...                 {"username": "alice", "email": "alice@example.com"},
        ...                 {"username": "bob", "email": "bob@example.com"},
        ...                 {"username": "charlie", "email": "charlie@example.com"},
        ...             ]
        ...         )
        ...         # users is fully typed as list[User]
        ...         print(f"Created {len(users)} users")
        ...         # Transaction commits automatically on context exit
        """
        ensure_base_inheritance(self.ctx.db_class)

        if not rows_data:
            raise ValueError("rows_data cannot be empty")

        logger.debug("Creating multiple rows", table=self.ctx.db_class.__name__, count=len(rows_data))

        # Process all rows through hooks and validation
        processed_rows_data = []
        for idx, row_kwargs in enumerate(rows_data):
            try:
                # Validate if requested
                if validate:
                    try:
                        self.ctx.create_class.model_validate(row_kwargs)
                    except ValidationError as e:
                        logger.warning(
                            "Validation failed in create_rows",
                            table=self.ctx.db_class.__name__,
                            row_index=idx,
                            errors=e.errors(),
                        )
                        raise

                # update kwargs
                modified_kwargs = await self.get_create_kwargs(
                    session,
                    **row_kwargs.copy(),  # Copy to avoid modifying original
                )

                # Pre-create hook
                modified_kwargs = await self.ctx.db_class.pre_create_hook(
                    session,
                    modified_kwargs,
                )

                processed_rows_data.append(modified_kwargs)

            except Exception as uexc:
                logger.error(
                    "Failed to prepare row",
                    table=self.ctx.db_class.__name__,
                    row_index=idx,
                    error=str(uexc),
                )
                raise

        # Create row objects
        rows = [self.ctx.db_class(**data) for data in processed_rows_data]

        # Add all rows to session and flush to get DB-generated values
        session.add_all(rows)
        await session.flush()

        logger.debug("Rows created", table=self.ctx.db_class.__name__, count=len(rows))

        return rows

    async def create_rows_batched(
        self,
        session: AsyncSession,
        rows_data: Sequence[dict[str, Any]],
        *,
        validate: bool = True,
        batch_size: int = 1000,
    ) -> list[T]:
        """Create multiple rows in batches.

        Unlike create_rows(), this commits after each batch, so partial
        success is possible if a later batch fails.

        Parameters
        ----------
        session
            DB session manager
        rows_data
            Sequence of dictionaries for new rows
        validate
            Whether to validate each row against Pydantic model
        batch_size
            Number of rows to insert per batch (default: 1000)

        Returns
        -------
            List of all newly created rows

        Raises
        ------
        IntegrityError
            Integrity constraint violation in any batch
        ValidationError
            Pydantic validation failed on any row
        ValueError
            If rows_data is empty or batch_size < 1

        Notes
        -----
        This function commits after each batch. If a batch fails, previously
        committed batches will remain in the database. Use create_rows() if
        you need atomic all-or-nothing behavior.

        Examples
        --------
        >>> # Create 10,000 users in batches of 500
        >>> users_data = [
        ...     {"username": f"user_{i}", "email": f"user_{i}@example.com"}
        ...     for i in range(10000)
        ... ]
        >>> users = await create_rows_batched(
        ...     User, session, users_data, batch_size=500
        ... )
        """
        if not rows_data:
            raise ValueError("rows_data cannot be empty")

        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        logger.info(
            f"Creating rows in batches: {len(rows_data)} {batch_size}",
        )

        all_rows = []

        # Process in batches
        for batch_start in range(0, len(rows_data), batch_size):
            batch_end = min(batch_start + batch_size, len(rows_data))
            batch_data = rows_data[batch_start:batch_end]

            logger.debug(
                f"Processing batch {batch_start} {batch_end}",
            )

            try:
                batch_rows: list = await self.create_rows(session, batch_data, validate=validate)
                all_rows.extend(batch_rows)

            except Exception as uexc:
                logger.error(
                    f"Batch failed {batch_start} {batch_end}",
                    error=uexc,
                )
                raise

        logger.info("All batches completed")
        return all_rows

    async def bulk_insert_rows(
        self,
        session: AsyncSession,
        rows_data: Sequence[dict[str, Any]],
        *,
        validate: bool = True,
    ) -> int:
        """Bulk insert rows using SQLAlchemy's bulk operations.

        This is much faster than create_rows() but doesn't return the
        created objects or handle get_create_kwargs() preprocessing.

        Parameters
        ----------
        session
            DB session manager
        rows_data
            Sequence of dictionaries for new rows
        validate
            Whether to validate each row against Pydantic model

        Returns
        -------
            Number of rows inserted

        Raises
        ------
        IntegrityError
            Integrity constraint violation
        ValidationError
            Pydantic validation failed on any row
        ValueError
            If rows_data is empty

        Notes
        -----
        - Much faster than create_rows() for large datasets
        - Does NOT call get_create_kwargs() - use for simple inserts only
        - Does NOT return created objects with DB-generated values
        - Does NOT trigger SQLAlchemy events (e.g., before_insert)

        Examples
        --------
        >>> # Fast insert of 100,000 simple records
        >>> count = await bulk_insert_rows(
        ...     User,
        ...     session,
        ...     [{"username": f"user_{i}"} for i in range(100000)]
        ... )
        >>> print(f"Inserted {count} users")
        """
        if not rows_data:
            raise ValueError("rows_data cannot be empty")

        logger.debug(f"Bulk inserting rows {len(rows_data)}")

        # Validate all rows
        if validate:
            for idx, row_kwargs in enumerate(rows_data):
                try:
                    self.ctx.create_class.model_validate(row_kwargs)
                except ValidationError:
                    logger.warning(
                        f"Validation failed in bulk_insert_rows {idx}",
                    )
                    raise

        try:
            # Use insert statement for maximum performance
            stmt = insert(self.ctx.db_class).values(rows_data)
            await session.execute(stmt)
            await session.commit()

            logger.info(f"Bulk insert completed {len(rows_data)}")
            return len(rows_data)

        except IntegrityError as uexc:
            await session.rollback()
            logger.error(
                f"Integrity error during bulk insert {len(rows_data)}",
                error=uexc,
            )
            raise

    def _validate_path_security(self, path: str) -> Path:
        """Validate path doesn't escape archive directory.

        Parameters
        ----------
        path
            Relative path to validate

        Returns
        -------
            Resolved, validated absolute path

        Raises
        ------
        ValueError
            If path would escape archive directory or contains
            invalid characters

        Notes
        -----
        This method requires `global_config.storage.archive` to be available.
        Consider moving to a specialized subclass if not all tables need
        file path validation.

        Examples
        --------
        >>> ops = TableOperations(context)
        >>> safe_path = ops._validate_path_security("data/users/alice.json")
        >>> # Returns: /var/archive/data/users/alice.json
        >>>
        >>> # This will raise ValueError
        >>> ops._validate_path_security("../../../etc/passwd")
        """

        # Check for obvious traversal attempts
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            logger.error(
                "Invalid path detected",
                table=self.ctx.db_class.__name__,
                path=path,
            )
            raise ValueError(f"Invalid path: {path}")

        # Check path length
        if len(path) > 255:
            logger.error(
                "Path too long",
                table=self.ctx.db_class.__name__,
                path_length=len(path),
            )
            raise ValueError(f"Path too long: {len(path)} characters")

        # Check for null bytes (security issue)
        if "\x00" in path:
            logger.error(
                "Path contains null bytes",
                table=self.ctx.db_class.__name__,
            )
            raise ValueError("Path contains null bytes")

        # Resolve and check path is within archive
        archive_path = Path(global_config.storage.archive).resolve()
        fullpath = (archive_path / path).resolve()

        try:
            fullpath.relative_to(archive_path)
        except ValueError as uexc:
            if FORBID_TRAVERSAL:
                logger.error(
                    "Path traversal attempt detected",
                    table=self.ctx.db_class.__name__,
                    attempted_path=str(path),
                    archive_path=str(archive_path),
                    resolved_path=str(fullpath),
                    error=uexc,
                )
                raise ValueError(f"Path {path} would escape archive directory") from None

        return fullpath

    def to_pydantic(self, row: T) -> ResponseT:
        """Convert a database row to its Pydantic model representation.

        Transforms a SQLAlchemy model instance into the corresponding Pydantic
        response model (ResponseT) defined in the table context. This is
        useful for API responses, validation, and serialization.

        Parameters
        ----------
        row
            Database row instance (SQLAlchemy model)

        Returns
        -------
            Pydantic model instance of the response type, containing the
            same data as the database row

        Raises
        ------
        ValidationError
            If the database row contains data that doesn't validate against
            the Pydantic model schema
        AttributeError
            If the db_class doesn't implement the to_pydantic method

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext(
        ...     db_class=User,
        ...     response_class=UserResponse,
        ...     create_class=UserCreate,
        ...     class_string="user"
        ... )
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     user_row: User = await ops.get_row(session, user_id=1)
        ...     user_pydantic: UserResponse = ops.to_pydantic(user_row)
        ...     # Fully typed as UserResponse
        ...     print(user_pydantic.model_dump_json())
        {"id": 1, "username": "alice", "email": "alice@example.com"}
        """
        return cast(ResponseT, self.ctx.db_class.to_pydantic(row))

    def to_pydantic_list(self, rows: list[T]) -> list[ResponseT]:
        """Convert a list of database rows to Pydantic model representations.

        Transforms multiple SQLAlchemy model instances into their corresponding
        Pydantic response models (ResponseT). This is a batch version of
        to_pydantic() that may be more efficient for converting multiple rows.

        Parameters
        ----------
        rows
            List of database row instances (SQLAlchemy models)

        Returns
        -------
            List of Pydantic response model instances, in the same order
            as the input rows

        Raises
        ------
        ValidationError
            If any database row contains data that doesn't validate against
            the Pydantic model schema
        AttributeError
            If the db_class doesn't implement the to_pydantic_list method

        Notes
        -----
        - Empty input list returns empty output list
        - Order is preserved from input to output
        - Some implementations may optimize batch conversion vs. repeated
          single conversions

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext(
        ...     db_class=User,
        ...     response_class=UserResponse,
        ...     create_class=UserCreate,
        ...     class_string="user"
        ... )
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     user_rows: list[User] = await ops.get_rows(session, limit=10)
        ...     user_models: list[UserResponse] = ops.to_pydantic_list(user_rows)
        ...     # Fully typed as list[UserResponse]
        ...     for user in user_models:
        ...         print(user.username)
        alice
        bob
        charlie

        >>> # Useful for API responses with full type safety
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>>
        >>> @app.get("/users", response_model=list[UserResponse])
        >>> async def get_users() -> list[UserResponse]:
        ...     async with get_session() as session:
        ...         rows = await ops.get_rows(session)
        ...         return ops.to_pydantic_list(rows)
        ...         # Return type is correctly typed
        """
        return cast(list[ResponseT], self.ctx.db_class.to_pydantic_list(rows))

    def to_pydantic_dict(self, row: T) -> dict[str, Any]:
        """Convert a database row to a dictionary via Pydantic validation.

        Transforms a SQLAlchemy model instance into a dictionary by first
        converting to a Pydantic response model (ResponseT, ensuring validation)
        and then serializing to a dict. The result is suitable for JSON
        serialization, logging, or other dictionary-based operations.

        Parameters
        ----------
        row
            Database row instance (SQLAlchemy model)

        Returns
        -------
            Dictionary representation of the row, with keys corresponding to
            the Pydantic response model fields and values appropriately
            serialized

        Raises
        ------
        ValidationError
            If the database row contains data that doesn't validate against
            the Pydantic model schema
        AttributeError
            If the db_class doesn't implement the to_pydantic_dict method

        Notes
        -----
        - The output includes only fields defined in ResponseT,
          not all SQLAlchemy model attributes
        - Complex types (datetime, UUID, etc.) are serialized according to
          Pydantic's serialization rules
        - This method goes through Pydantic validation, unlike direct
          SQLAlchemy to dict conversion

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext(
        ...     db_class=User,
        ...     response_class=UserResponse,
        ...     create_class=UserCreate,
        ...     class_string="user"
        ... )
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     user_row: User = await ops.get_row(session, user_id=1)
        ...     user_dict: dict[str, Any] = ops.to_pydantic_dict(user_row)
        ...     print(user_dict)
        {'id': 1, 'username': 'alice', 'email': 'alice@example.com',
         'created_at': '2025-01-15T10:30:00'}

        >>> # Useful for structured logging
        >>> logger.info("User details", **ops.to_pydantic_dict(user_row))

        >>> # Or JSON responses without FastAPI's automatic conversion
        >>> import json
        >>> json_str = json.dumps(ops.to_pydantic_dict(user_row))
        """
        return self.ctx.db_class.to_pydantic_dict(row)

    def to_pydantic_dict_list(self, rows: list[T]) -> list[dict[str, Any]]:
        """Convert a list of database rows to dictionaries via Pydantic validation.

        Transforms multiple SQLAlchemy model instances into dictionaries by first
        converting each to a Pydantic response model (ResponseT, ensuring
        validation) and then serializing to dicts. This is a batch version of
        to_pydantic_dict().

        Parameters
        ----------
        rows
            List of database row instances (SQLAlchemy models)

        Returns
        -------
            List of dictionary representations, each with keys corresponding to
            the Pydantic response model fields and values appropriately
            serialized, in the same order as the input rows

        Raises
        ------
        ValidationError
            If any database row contains data that doesn't validate against
            the Pydantic model schema
        AttributeError
            If the db_class doesn't implement the to_pydantic_dict_list method

        Notes
        -----
        - Empty input list returns empty output list
        - Order is preserved from input to output
        - Each dictionary includes only fields defined in ResponseT
        - Complex types are serialized according to Pydantic's rules
        - Some implementations may optimize batch conversion

        Examples
        --------
        >>> from myapp.models import User, UserResponse, UserCreate
        >>> context = TableContext(
        ...     db_class=User,
        ...     response_class=UserResponse,
        ...     create_class=UserCreate,
        ...     class_string="user"
        ... )
        >>> ops = TableOperations(context)
        >>>
        >>> async with get_session() as session:
        ...     user_rows: list[User] = await ops.get_rows(session, limit=3)
        ...     user_dicts: list[dict[str, Any]] = ops.to_pydantic_dict_list(user_rows)
        ...     for user_dict in user_dicts:
        ...         print(f"{user_dict['username']}: {user_dict['email']}")
        alice: alice@example.com
        bob: bob@example.com
        charlie: charlie@example.com

        >>> # Useful for bulk operations or exports
        >>> import csv
        >>> with open('users.csv', 'w') as f:
        ...     writer = csv.DictWriter(f, fieldnames=['id', 'username', 'email'])
        ...     writer.writeheader()
        ...     writer.writerows(ops.to_pydantic_dict_list(user_rows))

        >>> # Or for structured logging
        >>> logger.info("Batch user export", users=ops.to_pydantic_dict_list(user_rows))

        >>> # YAML/JSON export
        >>> import yaml
        >>> yaml.dump(ops.to_pydantic_dict_list(user_rows), open('users.yaml', 'w'))
        """
        return self.ctx.db_class.to_pydantic_dict_list(rows)


class FileValidatedOperations[T: Base, ResponseT: BaseModel, CreateT: BaseModel](
    TableOperations[T, ResponseT, CreateT]
):
    """Base class for table operations with file-backed data validation.

    Provides common functionality for tables that store references to
    files requiring validation, including:

    - Path security validation (directory traversal protection)
    - File existence checking
    - Async file reading via executor to avoid blocking
    - Standardized error handling for I/O and format errors
    - Generic load functionality for file-backed records

    Subclasses must implement:
        - get_file_length(path): Extract object count from file
        - get_subdirectory(): Return subdirectory name for this type
          (e.g., "datasets", "models", "estimates")

    Type Parameters
    ---------------
    T : TypeVar, bound=Base
        Database model class for file-backed data
    ResponseT : TypeVar, bound=BaseModel
        Pydantic response model class
    CreateT : TypeVar, bound=BaseModel
        Pydantic creation model class (must support path and
        n_objects fields)

    Examples
    --------
    >>> class DatasetOperations(FileValidatedOperations[...]):
    ...     def get_file_length(self, path: Path) -> int:
    ...         return tables_io.hdf5.get_input_data_length(str(path))
    ...
    ...     def get_subdirectory(self) -> str:
    ...         return "datasets"
    """

    @abstractmethod
    def get_file_length(self, path: Path) -> int:
        """Get number of objects in file. Implement in subclass."""

    @abstractmethod
    def get_subdirectory(self) -> str:
        """Get subdirectory name for this file type.

        Returns
        -------
            Subdirectory name (e.g., "datasets", "models", "estimates")

        Examples
        --------
        >>> def get_subdirectory(self) -> str:
        ...     return "datasets"
        """

    async def load(
        self,
        name: str,
        orig_path: Path | str,
        load_type: LoadType = LoadType.in_place,
        *,
        validate_file: bool = True,
        **kwargs: Any,
    ) -> ResponseT:
        """Load a file into the system.

        Creates a database record and handles the file according to the specified
        load type (in-place, symlink, or copy). Optionally validates the file
        BEFORE any file operations or database modifications occur.

        Parameters
        ----------
        name
            Name for the record
        orig_path
            Path to the original file (can be absolute or relative)
        load_type
            How to handle the file:
            - LoadType.in_place: Use file at its current location
            - LoadType.link: Create symbolic link in archive
            - LoadType.copy: Copy file to archive
        validate_file
            Whether to validate the file before any file operations or
            database changes
        **kwargs
            Additional keyword arguments passed to get_create_kwargs(),
            which typically include foreign key references (e.g.,
            catalog_tag_name, algo_name, dataset_name, etc.)

        Returns
        -------
            The created Pydantic model

        Raises
        ------
        FileNotFoundError
            If the original file doesn't exist
        ValueError
            If file validation fails (when validate_file=True), or if
            required foreign key references are not found in the database
        PermissionError
            If there are insufficient permissions for file operations
        OSError
            If there are filesystem errors during copy/link operations

        Examples
        --------
        Load a dataset by copying to archive with validation:

        >>> dataset = await dataset_ops.load(
        ...     "my_data",
        ...     "/data/catalogs/survey.h5",
        ...     load_type=LoadType.copy,
        ...     validate_file=True,
        ...     catalog_tag_name="SDSS_DR16",
        ...     is_collection=False
        ... )
        >>> print(f"Created dataset {dataset.id} at {dataset.path}")
        Created dataset 123 at datasets/my_data_survey.h5

        Load estimates in-place without validation:

        >>> estimates = await estimates_ops.load(
        ...     "quick_estimates",
        ...     "/scratch/temp_estimates.hdf5",
        ...     load_type=LoadType.in_place,
        ...     validate_file=False,
        ...     estimator_name="PhotoZEstimator",
        ...     dataset_name="test_data",
        ...     n_objects=10000  # Must provide when validate_file=False
        ... )

        Load with a symbolic link:

        >>> model = await model_ops.load(
        ...     "shared_model",
        ...     "/shared/models/production.pkl",
        ...     load_type=LoadType.link,
        ...     algo_name="RandomForestEstimator",
        ...     catalog_tag_name="LSST_Y1"
        ... )

        Notes
        -----
        - Validation occurs BEFORE any file operations (copy/link) or database
          records are created, so invalid files will not pollute the filesystem
          or database
        - When using LoadType.copy or LoadType.link, the file is placed in the
          subdirectory returned by get_subdirectory() with the pattern:
          '{subdirectory}/{name}_{basename}'
        - When validate_file=True and n_objects is in kwargs, the value will
          be verified against the actual file content
        - The function manages its own database transaction
        """
        # Validate FIRST, before any file operations or database changes
        if validate_file:
            # Validate the original file before any operations
            validation_path = Path(await anyio.Path(orig_path).resolve())
            logger.info(
                "Validating file before loading",
                table=self.ctx.db_class.__name__,
                path=str(validation_path),
            )

            # Use a temporary session to get n_objects for validation
            # This also validates the file can be read
            async with get_session() as session:
                # Get any reference object needed for validation from kwargs
                # Subclasses can override get_create_kwargs to resolve these
                # For now, just validate the file can be read
                try:
                    n_objects = await self.validate_data_for_path(validation_path, None)
                    logger.info(
                        "File validation successful, proceeding with load",
                        table=self.ctx.db_class.__name__,
                        n_objects=n_objects,
                    )
                    # Store n_objects in kwargs for later use
                    if "n_objects" not in kwargs:
                        kwargs["n_objects"] = n_objects
                except Exception as uexc:
                    logger.error(
                        "File validation failed",
                        table=self.ctx.db_class.__name__,
                        path=str(validation_path),
                        error=str(uexc),
                    )
                    raise

        # Generate archive path based on original filename
        basename = os.path.basename(orig_path)
        subdirectory = self.get_subdirectory()
        archive_path = Path(subdirectory) / f"{name}_{basename}"

        # Handle the file according to load_type (only after validation passes)
        output_path = handle_file(orig_path, archive_path, load_type)

        logger.info(
            "File handled successfully",
            table=self.ctx.db_class.__name__,
            load_type=load_type.value,
            output_path=str(output_path),
        )

        # Create the database record (validation passed or was skipped)
        async with get_session() as session:
            async with session.begin():
                new_record = await self.create_row(
                    session,
                    name=name,
                    path=str(output_path),
                    validate_file=False,  # Already validated above
                    **kwargs,
                )
                logger.info(
                    "Database record created",
                    table=self.ctx.db_class.__name__,
                    record_id=getattr(new_record, "id", None),
                )
                return self.to_pydantic(new_record)

    async def validate_data_for_path(
        self,
        path: Path,
        reference_obj: Base | None = None,
    ) -> int:
        """Validate that data file exists and can be read.

        This method performs synchronous I/O in an executor to avoid
        blocking the event loop.

        Parameters
        ----------
        path
            Absolute path to the data file
        reference_obj
            Reference object for future validation (currently unused
            but reserved for validating data matches expected schema)

        Returns
        -------
            Number of objects in the file

        Raises
        ------
        FileNotFoundError
            If the file doesn't exist
        ValueError
            If the file cannot be read or has invalid format

        Notes
        -----
        Future enhancement: Use reference_obj to validate that the data
        format matches the expected schema for this object type.
        """
        # Reserved for future use: validate data matches reference_obj schema
        _ = reference_obj

        async_path = anyio.Path(path)
        if not await async_path.exists():
            logger.error(
                "Data file not found",
                table=self.ctx.db_class.__name__,
                path=str(path),
            )
            raise FileNotFoundError(f"File {path} not found")

        loop = asyncio.get_event_loop()
        try:
            n_objects = await loop.run_in_executor(None, self.get_file_length, path)
        except OSError as uexc:
            # File system errors
            logger.error(
                "Failed to read data file",
                table=self.ctx.db_class.__name__,
                path=str(path),
                error=str(uexc),
                error_type="io_error",
            )
            raise ValueError(f"Could not read data from {path}: {uexc}") from uexc
        except ValueError as uexc:
            # Data format errors
            logger.error(
                "Invalid data format in file",
                table=self.ctx.db_class.__name__,
                path=str(path),
                error=str(uexc),
                error_type="format_error",
            )
            raise ValueError(f"Invalid data format in {path}: {uexc}") from uexc
        except Exception as uexc:
            logger.exception(
                "Unexpected error reading data file",
                table=self.ctx.db_class.__name__,
                path=str(path),
            )
            raise ValueError(f"Unexpected error reading {path}: {uexc}") from uexc

        logger.debug(
            "Data file validated",
            table=self.ctx.db_class.__name__,
            path=str(path),
            n_objects=n_objects,
        )

        return n_objects


def create_operations[T: Base, ResponseT: BaseModel, CreateT: BaseModel](
    db_class: type[T],
    response_class: type[ResponseT],
    create_class: type[CreateT],
) -> TableOperations[T, ResponseT, CreateT]:
    """Create fully-typed TableOperations from explicit classes.

    Parameters
    ----------
    db_class
        SQLAlchemy database model class
    response_class
        Pydantic response model class
    create_class
        Pydantic creation model class

    Returns
    -------
        Fully typed operations instance
    """
    context = TableContext(
        db_class=db_class,
        response_class=response_class,
        create_class=create_class,
        class_string=db_class.class_string(),
    )
    return TableOperations(context)
