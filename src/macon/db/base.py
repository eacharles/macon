"""Database model base for rail-svc applications.

This module provides the declarative base class for all ORM models,
with consistent schema configuration and naming conventions.

Hook Execution Order
--------------------
CREATE: pre_create_hook → flush → after_create_hook → commit
DELETE: pre_delete_hook → flush → after_delete_hook → commit
UPDATE: pre_update_hook → flush → after_update_hook → commit

All hooks run within the same transaction. Exceptions will rollback everything.

Hook Best Practices
-------------------
1. Keep hooks idempotent where possible
2. For non-critical operations (logging, cache updates), use try/except internally
3. For critical operations (validation, authorization), let exceptions propagate
4. Don't start new transactions within hooks - they run in the parent transaction
5. Access the session directly; don't use `async with session()` context managers

Example Hook Implementation:
    >>> class User(Base):
    ...     @classmethod
    ...     async def after_create_hook(cls, session, row):
    ...         # Critical: let exceptions propagate
    ...         await create_user_preferences(session, row.id)
    ...
    ...         # Non-critical: catch and log
    ...         try:
    ...             await cache.set(f"user:{row.id}", row.to_dict())
    ...         except CacheError as e:
    ...             logger.warning(f"Cache update failed: {e}")
"""

from abc import abstractmethod
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped

from ..config import config

# Define TypeVar for generic typing in mixins (e.g., RowMixin)
T = TypeVar("T", bound="Base")

# Naming convention for constraints (helps with Alembic migrations)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all database models.

    Provides:
        - Schema assignment from configuration
        - Consistent constraint naming for migrations
        - Shared metadata for all models
        - Required interface for Pydantic integration
        - Lifecycle hooks for create, update, and delete operations

    Subclasses must implement the abstract methods for Pydantic model integration.
    Subclasses may override hook methods to add custom behavior at various points
    in the row lifecycle.
    """

    id_: Mapped[int] | None = None
    name: Mapped[str] | None = None

    # Default pagination limit - subclasses can override via get_pagination_limit()
    default_pagination_limit: ClassVar[int] = 100

    metadata: ClassVar[MetaData] = MetaData(
        schema=config.db.table_schema or None, naming_convention=NAMING_CONVENTION
    )

    @classmethod
    def class_string(cls) -> str:
        """Name to use for help functions and descriptions.

        Override this if you want a custom display name different from __name__.

        Returns
        -------
        str
            The class name for display purposes
        """
        return cls.__name__

    @classmethod
    @abstractmethod
    def pydantic_create_class(cls) -> type[BaseModel]:
        """Pydantic model used to create rows in this table.

        This model defines the schema for input validation when creating new rows.
        It may differ from pydantic_model_class() if creation requires different
        fields than the full model representation.

        Returns
        -------
        type[BaseModel]
            The Pydantic model class for row creation

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     def pydantic_create_class(cls) -> type[BaseModel]:
        ...         return UserCreate  # Excludes id, created_at, etc.
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement pydantic_create_class() "
            f"to return a Pydantic model for row creation"
        )

    @classmethod
    @abstractmethod
    def pydantic_model_class(cls) -> type[BaseModel]:
        """Pydantic model class for this table.

        This model defines the complete schema for serialization and validation
        of existing rows, typically including all fields.

        Returns
        -------
        type[BaseModel]
            The Pydantic model class for row serialization/validation

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     def pydantic_model_class(cls) -> type[BaseModel]:
        ...         return UserModel  # Includes all fields
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement pydantic_model_class() "
            f"to return a Pydantic model for row serialization/validation"
        )

    @classmethod
    def to_pydantic(cls: type[T], row: T) -> BaseModel:
        """Convert an ORM row instance to its Pydantic model representation.

        This method uses model_validate() with from_attributes=True to handle
        SQLAlchemy ORM objects properly, including lazy-loaded relationships.

        Parameters
        ----------
        row
            The ORM row instance to convert

        Returns
        -------
        BaseModel
            An instance of the Pydantic model class with data from the row

        Examples
        --------
        >>> user_row = await session.get(User, user_id)
        >>> user_pydantic = User.to_pydantic(user_row)
        >>> print(user_pydantic.model_dump())
        {'id': 1, 'email': 'user@example.com', 'created_at': '2024-01-01T00:00:00'}

        >>> # Works with relationships if they're loaded
        >>> user_row = await session.execute(
        ...     select(User).options(selectinload(User.preferences)).where(User.id == 1)
        ... )
        >>> user_pydantic = User.to_pydantic(user_row.scalar_one())
        >>> print(user_pydantic.preferences)  # Relationship is included

        Notes
        -----
        - Uses model_validate() with from_attributes=True (ORM mode)
        - Only includes attributes that exist in the Pydantic model schema
        - Lazy-loaded relationships will trigger additional queries if accessed
        - For better performance with relationships, use eager loading
          (selectinload, joinedload, etc.) before calling this method
        """
        pydantic_class = cls.pydantic_model_class()
        return pydantic_class.model_validate(row, from_attributes=True)

    @classmethod
    def to_pydantic_list(cls: type[T], rows: list[T]) -> list[BaseModel]:
        """Convert a list of ORM row instances to Pydantic model instances.

        Convenience method for converting multiple rows at once, commonly
        used when returning query results.

        Parameters
        ----------
        rows
            List of ORM row instances to convert

        Returns
        -------
        list[BaseModel]
            List of Pydantic model instances

        Examples
        --------
        >>> result = await session.execute(select(User).limit(10))
        >>> user_rows = result.scalars().all()
        >>> user_pydantics = User.to_pydantic_list(user_rows)
        >>> print([u.email for u in user_pydantics])
        ['user1@example.com', 'user2@example.com', ...]

        >>> # Use with pagination
        >>> result = await session.execute(
        ...     select(User)
        ...     .offset(page * page_size)
        ...     .limit(page_size)
        ... )
        >>> return User.to_pydantic_list(result.scalars().all())

        Notes
        -----
        - Applies to_pydantic() to each row in the list
        - Returns empty list if input is empty
        - For large result sets, consider generator pattern for memory efficiency
        """
        return [cls.to_pydantic(row) for row in rows]

    @classmethod
    def to_pydantic_dict(cls: type[T], row: T) -> dict[str, Any]:
        """Convert an ORM row instance to a dictionary via Pydantic model.

        This is a convenience method that combines to_pydantic() with
        model_dump(), useful for API responses and serialization.

        Parameters
        ----------
        row
            The ORM row instance to convert

        Returns
        -------
        dict[str, Any]
            Dictionary representation of the row data

        Examples
        --------
        >>> user_row = await session.get(User, user_id)
        >>> user_dict = User.to_pydantic_dict(user_row)
        >>> return JSONResponse(user_dict)

        >>> # Useful for combining multiple models
        >>> user_dict = User.to_pydantic_dict(user_row)
        >>> prefs_dict = UserPreferences.to_pydantic_dict(prefs_row)
        >>> return {**user_dict, 'preferences': prefs_dict}

        Notes
        -----
        - First converts to Pydantic model, then calls model_dump()
        - Applies Pydantic serialization rules (excludes, aliases, etc.)
        - Handles datetime serialization according to Pydantic config
        - For custom serialization, configure your Pydantic model class
        """
        pydantic_obj = cls.to_pydantic(row)
        return pydantic_obj.model_dump()

    @classmethod
    def to_pydantic_dict_list(cls: type[T], rows: list[T]) -> list[dict[str, Any]]:
        """Convert a list of ORM row instances to dictionaries via Pydantic.

        Convenience method for converting multiple rows to dictionaries,
        commonly used for JSON API responses.

        Parameters
        ----------
        rows
            List of ORM row instances to convert

        Returns
        -------
        list[dict[str, Any]]
            List of dictionary representations

        Examples
        --------
        >>> result = await session.execute(select(User).limit(10))
        >>> user_rows = result.scalars().all()
        >>> user_dicts = User.to_pydantic_dict_list(user_rows)
        >>> return JSONResponse({'users': user_dicts, 'count': len(user_dicts)})

        Notes
        -----
        - Applies to_pydantic_dict() to each row in the list
        - Returns empty list if input is empty
        - All items go through Pydantic serialization
        """
        return [cls.to_pydantic_dict(row) for row in rows]

    @classmethod
    def get_pagination_limit(cls) -> int:
        """Get the default pagination limit for this table.

        Subclasses can override this to set table-specific limits.

        Returns
        -------
        int
            Maximum number of rows to return in a single query

        Examples
        --------
        >>> class LargeTable(Base):
        ...     @classmethod
        ...     def get_pagination_limit(cls) -> int:
        ...         return 50  # Limit large table queries
        """
        return cls.default_pagination_limit

    @classmethod
    def get_hooks(cls) -> dict[str, bool]:
        """Return which lifecycle hooks are implemented by this model.

        Useful for debugging, testing, and introspection.

        Returns
        -------
        dict[str, bool]
            Map of hook names to whether they're overridden from Base

        Examples
        --------
        >>> User.get_hooks()
        {'pre_create': True, 'after_create': True, 'pre_update': False,
         'after_update': False, 'pre_delete': False, 'after_delete': True}
        """
        return {
            "pre_create": cls.pre_create_hook != Base.pre_create_hook,
            "after_create": cls.after_create_hook != Base.after_create_hook,
            "pre_update": cls.pre_update_hook != Base.pre_update_hook,
            "after_update": cls.after_update_hook != Base.after_update_hook,
            "pre_delete": cls.pre_delete_hook != Base.pre_delete_hook,
            "after_delete": cls.after_delete_hook != Base.after_delete_hook,
        }

    # ============================================================================
    # CREATE HOOKS
    # ============================================================================

    @classmethod
    async def pre_create_hook(
        cls: type[T],
        session: AsyncSession,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Hook called during create_row, BEFORE row creation.

        Subclasses can override this to:
        - Validate or transform input data
        - Add computed/derived fields
        - Perform authorization checks
        - Look up foreign key values

        This is called within the transaction but before the row is
        instantiated, so any errors raised here will prevent creation.

        Parameters
        ----------
        session
            Active database session for performing queries.
            Do NOT use `async with session()` - the session is already active.
        data
            Dictionary of field names and values for the new row.
            Can be modified before returning.

        Returns
        -------
        dict[str, Any]
            Modified or unchanged data dictionary used to create the row.
            The returned dict is what actually gets passed to the model constructor.

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     async def pre_create_hook(cls, session, data):
        ...         # Add computed field
        ...         if 'email' in data:
        ...             data['email_lower'] = data['email'].lower()
        ...
        ...         # Add timestamp
        ...         data['registered_at'] = datetime.utcnow()
        ...
        ...         # Validate business rules (critical - let exception propagate)
        ...         if data.get('age', 0) < 18:
        ...             raise ValueError("Users must be 18 or older")
        ...
        ...         return data

        Notes
        -----
        - This hook runs BEFORE row creation
        - Must return the data dictionary (possibly modified)
        - Any exceptions raised will prevent row creation and rollback the transaction
        - Runs within the parent transaction - do not start new transactions
        """
        assert session
        return data

    @classmethod
    async def after_create_hook(
        cls: type[T],
        session: AsyncSession,
        row: T,
    ) -> None:
        """Hook called during create_row, AFTER successful creation.

        Subclasses can override this to perform operations after the row
        is created and flushed to the database, such as:
        - Creating related records
        - Updating caches (use try/except for non-critical updates)
        - Sending notifications
        - Logging/auditing
        - Triggering background tasks

        This hook is called AFTER the row has been flushed to the database
        (so it has an ID and all database-generated values) but before the
        transaction commits. If this hook raises an exception, the entire
        transaction (including the create) will be rolled back.

        Parameters
        ----------
        session
            Active database session for performing additional operations.
            Do NOT use `async with session()` - the session is already active.
        row
            The newly created row object with all fields populated,
            including database-generated values like auto-increment IDs

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     async def after_create_hook(cls, session, row):
        ...         # Critical: create required related records
        ...         prefs = UserPreferences(user_id=row.id)
        ...         session.add(prefs)
        ...         await session.flush()
        ...
        ...         # Non-critical: update cache
        ...         try:
        ...             await cache.set(f"user:{row.id}", row.to_dict())
        ...         except CacheError as e:
        ...             logger.warning(f"Cache update failed: {e}")
        ...
        ...         # Non-critical: send welcome email (fire and forget)
        ...         try:
        ...             await queue.enqueue('send_welcome_email', user_id=row.id)
        ...         except QueueError as e:
        ...             logger.error(f"Failed to queue welcome email: {e}")

        Notes
        -----
        - This hook runs AFTER creation and flush, so row.id is available
        - Any exceptions raised will roll back the entire transaction
        - For non-critical operations, use try/except to prevent rollback
        - Hook implementations should be idempotent where possible
        - Runs within the parent transaction - do not start new transactions
        """
        assert session
        assert row
        return None

    # ============================================================================
    # UPDATE HOOKS
    # ============================================================================

    @classmethod
    async def pre_update_hook(
        cls: type[T],
        session: AsyncSession,
        row: T,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Hook called during update_row, BEFORE applying updates.

        Subclasses can override this to:
        - Validate or transform update data
        - Add computed fields based on changes
        - Perform authorization checks
        - Implement optimistic locking or version checks

        This is called within the transaction but before the updates are
        applied to the row object.

        Parameters
        ----------
        session
            Active database session for performing queries.
            Do NOT use `async with session()` - the session is already active.
        row
            The existing row object before updates are applied
        data
            Dictionary of field names and values to update.
            Can be modified before returning.

        Returns
        -------
        dict[str, Any]
            Modified or unchanged data dictionary used to update the row.
            The returned dict is what actually gets applied to the row.

        Examples
        --------
        >>> class Article(Base):
        ...     @classmethod
        ...     async def pre_update_hook(cls, session, row, data):
        ...         # Track content changes
        ...         if 'content' in data and data['content'] != row.content:
        ...             data['last_edited_at'] = datetime.utcnow()
        ...             data['edit_count'] = row.edit_count + 1
        ...
        ...         # Prevent status changes without approval
        ...         if 'status' in data and row.status != 'draft':
        ...             raise ValueError("Cannot modify published articles")
        ...
        ...         return data

        Notes
        -----
        - This hook runs BEFORE updates are applied
        - Must return the data dictionary (possibly modified)
        - Any exceptions raised will prevent the update and rollback the transaction
        - Runs within the parent transaction - do not start new transactions
        """
        assert session
        assert row
        return data

    @classmethod
    async def after_update_hook(
        cls: type[T],
        session: AsyncSession,
        row: T,
        updated_fields: set[str],  # pylint: disable=unused-argument
    ) -> None:
        """Hook called during update_row, AFTER successful update.

        Subclasses can override this to perform operations after the row
        is updated and flushed to the database, such as:
        - Invalidating caches
        - Creating audit trail entries
        - Sending notifications about changes
        - Updating denormalized data in related tables

        This hook is called AFTER the updates have been flushed to the database
        but before the transaction commits. If this hook raises an exception,
        the entire transaction (including the update) will be rolled back.

        Parameters
        ----------
        session
            Active database session for performing additional operations.
            Do NOT use `async with session()` - the session is already active.
        row
            The row object after updates have been applied
        updated_fields
            Set of field names that were actually changed

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     async def after_update_hook(cls, session, row, updated_fields):
        ...         # Critical: update related records if email changed
        ...         if 'email' in updated_fields:
        ...             await session.execute(
        ...                 update(UserAuth)
        ...                 .where(UserAuth.user_id == row.id)
        ...                 .values(email=row.email)
        ...             )
        ...
        ...         # Non-critical: invalidate cache
        ...         try:
        ...             await cache.delete(f"user:{row.id}")
        ...         except CacheError as e:
        ...             logger.warning(f"Cache invalidation failed: {e}")
        ...
        ...         # Non-critical: audit log
        ...         try:
        ...             await audit_log.record_update(
        ...                 "User", row.id, updated_fields
        ...             )
        ...         except Exception as e:
        ...             logger.error(f"Audit logging failed: {e}")

        Notes
        -----
        - This hook runs AFTER update and flush
        - Row contains the updated values
        - Any exceptions raised will roll back the entire transaction
        - For non-critical operations, use try/except to prevent rollback
        - Hook implementations should be idempotent where possible
        - Runs within the parent transaction - do not start new transactions
        """
        assert session
        assert row
        return None

    # ============================================================================
    # DELETE HOOKS
    # ============================================================================

    @classmethod
    async def pre_delete_hook(
        cls: type[T],
        session: AsyncSession,
        row: T,
    ) -> None:
        """Hook called during delete_row, BEFORE deletion.

        Subclasses can override this to:
        - Perform authorization checks
        - Implement soft delete logic
        - Validate that deletion is allowed
        - Capture data needed for after_delete_hook

        This is called within the transaction but before the delete is
        executed, so any errors raised here will prevent the deletion.

        Parameters
        ----------
        session
            Active database session for performing queries.
            Do NOT use `async with session()` - the session is already active.
        row
            The row object that will be deleted (with all fields accessible)

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     async def pre_delete_hook(cls, session, row):
        ...         # Prevent deletion of admin users
        ...         if row.role == 'admin':
        ...             raise ValueError("Cannot delete admin users")
        ...
        ...         # Archive user data before deletion
        ...         archive = UserArchive(
        ...             user_id=row.id,
        ...             email=row.email,
        ...             archived_at=datetime.utcnow()
        ...         )
        ...         session.add(archive)
        ...         await session.flush()

        Notes
        -----
        - This hook runs BEFORE deletion
        - Row object is still fully accessible with all field values
        - Any exceptions raised will prevent deletion and rollback the transaction
        - Runs within the parent transaction - do not start new transactions
        """
        assert session
        assert row
        return None

    @classmethod
    async def after_delete_hook(
        cls: type[T],
        session: AsyncSession,
        row: T,
    ) -> None:
        """Hook called during delete_row, AFTER successful deletion.

        Subclasses can override this to perform cleanup operations after
        the row is deleted, such as:
        - Cleaning up external resources (files, cache entries, etc.)
        - Deleting related records (cascade deletes)
        - Logging/auditing
        - Triggering notifications
        - Cleanup that shouldn't prevent deletion even if it fails

        This hook is called AFTER the deletion has been flushed to the
        database but before the transaction commits. If this hook raises
        an exception, the entire transaction (including the delete) will
        be rolled back.

        IMPORTANT: The row object is passed for convenience to access field
        values (like file paths, IDs, etc.), but it has already been deleted
        from the database. Do not attempt to modify or re-add it.

        Parameters
        ----------
        session
            Active database session for performing additional operations.
            Do NOT use `async with session()` - the session is already active.
        row
            The deleted row object. Still contains field values but is
            no longer in the database. Use for accessing data like file
            paths, foreign keys, etc. needed for cleanup.

        Examples
        --------
        >>> class User(Base):
        ...     @classmethod
        ...     async def after_delete_hook(cls, session, row):
        ...         # Critical: delete related records
        ...         await session.execute(
        ...             delete(UserPreferences).where(
        ...                 UserPreferences.user_id == row.id
        ...             )
        ...         )
        ...         await session.flush()
        ...
        ...         # Non-critical: clean up uploaded files
        ...         if row.profile_image_path:
        ...             try:
        ...                 await delete_file(row.profile_image_path)
        ...             except FileNotFoundError:
        ...                 logger.warning(
        ...                     f"Profile image already deleted for user {row.id}"
        ...                 )
        ...             except Exception as e:
        ...                 logger.error(f"Failed to delete profile image: {e}")
        ...
        ...         # Non-critical: clear cache
        ...         try:
        ...             await cache.delete(f"user:{row.id}")
        ...         except CacheError as e:
        ...             logger.warning(f"Cache deletion failed: {e}")
        ...
        ...         # Non-critical: audit log
        ...         try:
        ...             await audit_log.record_deletion("User", row.id, row.email)
        ...         except Exception as e:
        ...             logger.error(f"Audit logging failed: {e}")

        Notes
        -----
        - This hook runs AFTER deletion, so the row is no longer in the database
        - The row object still contains all field values for reference
        - Any exceptions raised will roll back the entire transaction
        - For operations that shouldn't block deletion, use try/except
        - Hook implementations should be idempotent where possible
        - Runs within the parent transaction - do not start new transactions
        - Do NOT attempt to modify or re-add the row object
        """
        assert session
        assert row
        return None


def ensure_base_inheritance(cls: type[Any]) -> None:
    """Raise TypeError if a class does not inherit from Base.

    This is a helper function for runtime validation that a class
    follows the expected inheritance pattern.

    Parameters
    ----------
    cls
        The class to check for Base inheritance

    Raises
    ------
    TypeError
        If cls does not inherit from Base

    Examples
    --------
    >>> class MyModel(Base):
    ...     pass
    >>> ensure_base_inheritance(MyModel)  # No error
    >>>
    >>> class BadModel:
    ...     pass
    >>> ensure_base_inheritance(BadModel)
    Traceback (most recent call last):
        ...
    TypeError: Class BadModel must inherit from rail_svc.db.base.Base
    """
    if not issubclass(cls, Base):
        raise TypeError(f"Class {cls.__name__} must inherit from rail_svc.db.base.Base")
