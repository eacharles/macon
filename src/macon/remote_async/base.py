from __future__ import annotations

import types
import warnings
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pydantic import BaseModel

from ..client.base import (
    RemoteAPI,
    RemoteTableOperations,
)
from ..common import RowId

# Type variables
ResponseT = TypeVar("ResponseT", bound=BaseModel)
CreateT = TypeVar("CreateT", bound=BaseModel)


def with_client[F: Callable[..., Any]](func: F) -> F:
    """Decorator that injects the remote client into async methods.

    Gets or creates a RemoteTableOperations client and passes the call through.
    The decorated method should accept `client` as its first argument after `self`.

    Parameters
    ----------
    func
        Async method that operates on a RemoteTableOperations client

    Returns
    -------
        Wrapped method that automatically gets the client

    Examples
    --------
    >>> @with_client
    >>> async def get_row(self, client: RemoteTableOperations, row_id: int) -> ResponseT:
    ...     return await client.get_row(row_id)
    """

    @wraps(func)
    async def wrapper(self: AsyncRemoteOperations, *args: Any, **kwargs: Any) -> Any:
        client = await self.get_client()
        return await func(self, client, *args, **kwargs)

    return wrapper  # type: ignore


class AsyncRemoteOperations[ResponseT: BaseModel, CreateT: BaseModel]:
    """Async wrapper for remote table operations with connection management.

    Provides async methods for CRUD operations on remote database tables via HTTP API.
    Can be used as an async context manager for efficient connection reuse across
    multiple operations, or as a regular class for single operations.

    Type Parameters
    ---------------
    ResponseT : BaseModel
        Pydantic model type for API responses
    CreateT : BaseModel
        Pydantic model type for create/input operations

    Examples
    --------
    Using as async context manager (recommended for multiple operations):

    >>> async with AsyncRemoteOperations(
    ...     base_url="http://api.example.com",
    ...     table_name="users",
    ...     response_model=UserResponse,
    ...     create_model=UserCreate,
    ... ) as ops:
    ...     user = await ops.create_row(name="Alice", email="alice@example.com")
    ...     users = await ops.get_rows(limit=10)
    ...     await ops.delete_row(user.id)

    Using for single operations:

    >>> ops = AsyncRemoteOperations(...)
    >>> user = await ops.get_row(123)
    """

    def __init__(
        self,
        base_url: str,
        table_name: str,
        response_model: type[ResponseT],
        create_model: type[CreateT],
        api_prefix: str = "/api/v1",
        timeout: float = 30.0,
        auth_token: str | None = None,
        client_class: type[RemoteTableOperations] | None = None,
    ) -> None:
        """Initialize the async remote table operations.

        Parameters
        ----------
        base_url
            The base URL of the remote API server
        table_name
            The name of the table to operate on
        response_model
            Pydantic model for response data
        create_model
            Pydantic model for create/input data
        api_prefix
            API version prefix, by default "/api/v1"
        timeout
            Request timeout in seconds, by default 30.0
        auth_token
            Authentication token for API requests, by default None
        client_class
            Custom client class to use instead of default RemoteTableOperations
        """
        self.base_url = base_url
        self.table_name = table_name
        self.response_model = response_model
        self.create_model = create_model
        self.api_prefix = api_prefix
        self.timeout = timeout
        self.auth_token = auth_token
        self._api: RemoteAPI | None = None
        self._client: RemoteTableOperations[ResponseT, CreateT] | None = None
        self._owns_api = False
        self._has_warned = False
        self.client_class = client_class

    async def __aenter__(self) -> AsyncRemoteOperations:
        """Enter async context manager.

        Creates and initializes the RemoteAPI client for reuse across operations.

        Returns
        -------
            Self for context manager use
        """
        self._api = RemoteAPI(
            base_url=self.base_url,
            api_prefix=self.api_prefix,
            timeout=self.timeout,
            auth_token=self.auth_token,
        )
        await self._api.__aenter__()

        # Use custom client class if provided
        if self.client_class:
            endpoint = f"{self.base_url}{self.api_prefix}/{self.table_name}"
            assert self._api.client
            self._client = self.client_class(
                client=self._api.client,
                endpoint=endpoint,
                response_model=self.response_model,
                create_model=self.create_model,
            )
        else:
            self._client = self._api.table(
                self.table_name,
                self.response_model,
                self.create_model,
            )
        self._owns_api = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """
        Properly closes the RemoteAPI client connection.
        """
        if self._api and self._owns_api:
            await self._api.__aexit__(exc_type, exc_val, exc_tb)
            self._api = None
            self._client = None
            self._owns_api = False

    async def get_client(self) -> RemoteTableOperations[ResponseT, CreateT]:
        """Get or create the table operations client.

        If used within a context manager, returns the existing client.
        Otherwise, creates a temporary client for single-use operations.

        Returns
        -------
            The table operations client

        Warnings
        --------
        If creating a temporary client (not using context manager), a warning
        is issued the first time. This is inefficient for multiple operations.

        Notes
        -----
        For best performance with multiple operations, use this class as an
        async context manager to reuse connections:

        >>> async with AsyncRemoteTableOperations(...) as ops:
        ...     await ops.create_row(...)
        ...     await ops.get_rows(...)
        """
        if self._client is not None:
            return self._client

        # Warn on first temporary client creation
        if not self._has_warned:
            warnings.warn(
                f"Creating temporary client for {self.__class__.__name__}. "
                "For better performance with multiple operations, use as async context manager: "
                "'async with AsyncRemoteTableOperations(...) as ops:'",
                ResourceWarning,
                stacklevel=3,
            )
            self._has_warned = True

        # Create temporary API and client for single operation
        api = RemoteAPI(
            base_url=self.base_url,
            api_prefix=self.api_prefix,
            timeout=self.timeout,
            auth_token=self.auth_token,
        )

        # Use custom client class if provided
        if self.client_class:
            endpoint = f"{self.base_url}{self.api_prefix}/{self.table_name}"
            assert api.client

            return self.client_class(
                client=api.client,
                endpoint=endpoint,
                response_model=self.response_model,
                create_model=self.create_model,
            )

        return api.table(
            self.table_name,
            self.response_model,
            self.create_model,
        )

    # CREATE operations

    @with_client
    async def create_row(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.create_row(*args, **kwargs)

    @with_client
    async def create_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.create_rows(*args, **kwargs)

    @with_client
    async def create_rows_batched(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.create_rows_batched(*args, **kwargs)

    @with_client
    async def bulk_insert_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> int:
        return await client.bulk_insert_rows(*args, **kwargs)

    # READ operations

    @with_client
    async def get_row(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.get_row(*args, **kwargs)

    @with_client
    async def get_row_or_none(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT | None:
        return await client.get_row_or_none(*args, **kwargs)

    @with_client
    async def get_row_by_name(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.get_row_by_name(*args, **kwargs)

    @with_client
    async def get_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.get_rows(*args, **kwargs)

    @with_client
    async def count_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> int:
        return await client.count_rows(*args, **kwargs)

    @with_client
    async def lookup_by_id_or_name(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[RowId, ResponseT]:
        return await client.lookup_by_id_or_name(*args, **kwargs)

    # UPDATE operations

    @with_client
    async def update_row(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.update_row(*args, **kwargs)

    @with_client
    async def update_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.update_rows(*args, **kwargs)

    # DELETE operations

    @with_client
    async def delete_row(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT | None:
        return await client.delete_row(*args, **kwargs)

    @with_client
    async def delete_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT] | int:
        return await client.delete_rows(*args, **kwargs)

    @with_client
    async def bulk_delete_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> int:
        return await client.bulk_delete_rows(*args, **kwargs)

    # FILTER/QUERY operations

    @with_client
    async def filter_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.filter_rows(*args, **kwargs)

    @with_client
    async def count_filtered_rows(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> int:
        return await client.count_filtered_rows(*args, **kwargs)

    @with_client
    async def filter_one(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.filter_one(*args, **kwargs)

    @with_client
    async def filter_one_or_none(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT | None:
        return await client.filter_one_or_none(*args, **kwargs)

    @with_client
    async def find_by(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> list[ResponseT]:
        return await client.find_by(*args, **kwargs)

    @with_client
    async def find_one_by(
        self,
        client: RemoteTableOperations[ResponseT, CreateT],
        *args: Any,
        **kwargs: Any,
    ) -> ResponseT:
        return await client.find_one_by(*args, **kwargs)
