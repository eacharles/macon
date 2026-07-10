from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import aiofiles
import httpx
from pydantic import BaseModel, ValidationError

from ..config import config as global_config
from ..common import RowId, unexpected, LoadType
from ..models import CountResponse, Filter, FilterRequest, LookupResponse, OrderBy, RemoteAPIError

# Configure logging
logger = logging.getLogger(__name__)


class RemoteTableOperations[ResponseT: BaseModel, CreateT: BaseModel]:
    """Remote client for table operations via HTTP API.

    This class provides the same interface as LocalOperations but executes
    operations against a remote FastAPI server via HTTP requests.

    Parameters
    ----------
    client
        Shared HTTP client instance
    endpoint
        Full endpoint URL for this table
    response_model
        Pydantic model class for response data
    create_model
        Pydantic model class for create data

    Note
    ----
    This class expects to receive an already initialized httpx.AsyncClient.
    Use RemoteAPI context manager to manage the client lifecycle.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        response_model: type[ResponseT],
        create_model: type[CreateT],
    ):
        """Initialize the remote table operations client."""
        self.client = client
        self.endpoint = endpoint
        self.response_model = response_model
        self.create_model = create_model

    def _handle_response(
        self, response: httpx.Response, expected_status: int = 200
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Handle HTTP response and raise appropriate errors.

        Parameters
        ----------
        response
            The HTTP response object
        expected_status
            Expected status code (default: 200)

        Returns
        -------
            Parsed JSON response

        Raises
        ------
        RemoteAPIError
            If the response indicates an error
        """
        if response.status_code == expected_status:
            return response.json()

        # Try to parse error details
        try:
            error_data = response.json()
            error_msg = error_data.get("error", "Unknown error")
            details = error_data.get("details", "")
            if details:
                error_msg = f"{error_msg}: {details}"
        except Exception:
            error_msg = response.text or f"HTTP {response.status_code}"

        raise RemoteAPIError(f"API request failed with status {response.status_code}: {error_msg}")

    # CREATE operations

    async def create_row(self, *, validate: bool = True, **data: Any) -> ResponseT:
        """Create a single row.

        Parameters
        ----------
        validate
            Whether to validate data on the server (default: True)
        **data
            Row data as keyword arguments

        Returns
        -------
            Created row

        Raises
        ------
        RemoteAPIError
            If the API request fails
        ValidationError
            If the response data is invalid
        """
        response = await self.client.post(
            f"{self.endpoint}/create_row",
            json=data,
            params={"validate": validate},
        )

        result = cast(dict[str, Any], self._handle_response(response, expected_status=201))
        return self.response_model(**result)

    async def create_rows(self, data: list[dict], *, validate: bool = True) -> list[ResponseT]:
        """Create multiple rows.

        Parameters
        ----------
        data
            List of row data dictionaries
        validate
            Whether to validate data on the server (default: True)

        Returns
        -------
            List of created rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        ValidationError
            If the response data is invalid
        """
        response = await self.client.post(
            f"{self.endpoint}/create_rows",
            json=data,
            params={"validate": validate},
        )

        result = cast(list[dict[str, Any]], self._handle_response(response, expected_status=201))
        return [self.response_model(**item) for item in result]

    async def create_rows_batched(
        self,
        data: list[dict],
        *,
        validate: bool = True,
        batch_size: int = 1000,
    ) -> list[ResponseT]:
        """Create multiple rows in batches.

        Parameters
        ----------
        data
            List of row data dictionaries
        validate
            Whether to validate data on the server (default: True)
        batch_size
            Size of each batch (default: 1000)

        Returns
        -------
            List of created rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        ValidationError
            If the response data is invalid
        """
        response = await self.client.post(
            f"{self.endpoint}/create_rows_batched",
            json=data,
            params={"validate": validate, "batch_size": batch_size},
        )

        result = cast(list[dict[str, Any]], self._handle_response(response, expected_status=201))
        return [self.response_model(**item) for item in result]

    async def bulk_insert_rows(self, data: list[dict], *, validate: bool = True) -> int:
        """Bulk insert rows (returns count only).

        Parameters
        ----------
        data
            List of row data dictionaries
        validate
            Whether to validate data on the server (default: True)

        Returns
        -------
            Number of rows inserted

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        response = await self.client.post(
            f"{self.endpoint}/bulk_insert_rows",
            json=data,
            params={"validate": validate},
        )

        result = cast(dict[str, Any], self._handle_response(response, expected_status=201))
        return CountResponse(**result).count

    # READ operations

    async def get_row(self, row_id: RowId) -> ResponseT:
        """Get a single row by ID.

        Parameters
        ----------
        row_id
            Row ID

        Returns
        -------
            Row data

        Raises
        ------
        RemoteAPIError
            If the row is not found or the API request fails
        """
        response = await self.client.get(f"{self.endpoint}/get_row/{row_id}")

        result = cast(dict[str, Any], self._handle_response(response))
        return self.response_model(**result)

    async def get_row_or_none(self, row_id: RowId) -> ResponseT | None:
        """Get a single row by ID or None if not found.

        Parameters
        ----------
        row_id
            Row ID

        Returns
        -------
            Row data or None if not found

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        response = await self.client.get(f"{self.endpoint}/get_row_or_none/{row_id}")

        result = cast(dict[str, Any] | None, self._handle_response(response))
        if result is None:
            return None
        return self.response_model(**result)

    async def get_row_by_name(self, name: str) -> ResponseT:
        """Get a single row by name.

        Parameters
        ----------
        name
            Row name

        Returns
        -------
            Row data

        Raises
        ------
        RemoteAPIError
            If the row is not found or the API request fails
        """
        response = await self.client.get(f"{self.endpoint}/get_row_by_name/{name}")

        result = cast(dict[str, Any], self._handle_response(response))
        return self.response_model(**result)

    async def get_rows(self, skip: int = 0, limit: int | None = None) -> list[ResponseT]:
        """Get multiple rows with pagination.

        Parameters
        ----------
        skip
            Number of rows to skip (default: 0)
        limit
            Maximum rows to return (default: None for all)

        Returns
        -------
            List of rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        params = {"skip": skip}
        if limit is not None:
            params["limit"] = limit

        response = await self.client.get(
            f"{self.endpoint}/get_rows",
            params=params,
        )

        result = cast(list[dict[str, Any]], self._handle_response(response))
        return [self.response_model(**item) for item in result]

    async def get_rows_streaming(
        self,
        skip: int = 0,
        limit: int | None = None,
    ) -> AsyncGenerator[ResponseT]:
        """Get rows as a streaming response (NDJSON format).

        Parameters
        ----------
        skip
            Number of rows to skip (default: 0)
        limit
            Maximum rows to return (default: None for all)

        Yields
        ------
            Row data objects

        Raises
        ------
        RemoteAPIError
            If the API request fails

        Example
        -------
        >>> async for row in client.get_rows_streaming(limit=100):
        ...     print(row.id, row.name)
        """
        params = {"skip": skip}
        if limit is not None:
            params["limit"] = limit

        async with self.client.stream(
            "GET",
            f"{self.endpoint}/get_rows_streaming",
            params=params,
        ) as response:
            if response.status_code != 200:
                content = await response.aread()
                raise RemoteAPIError(
                    f"API request failed with status {response.status_code}: {content.decode()}"
                )

            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = self.response_model.model_validate_json(line)
                        yield data
                    except ValidationError as uexc:
                        logger.error(f"Failed to parse streaming response: {uexc}")
                        # Check if it's an error message
                        try:
                            error_data = json.loads(line)
                            if "error" in error_data:
                                raise RemoteAPIError(f"Stream error: {error_data['error']}") from uexc
                        except json.JSONDecodeError:
                            pass
                        raise

    async def count_rows(self) -> int:
        """Get total count of rows.

        Returns
        -------
            Total number of rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        response = await self.client.get(f"{self.endpoint}/count_rows")

        result = cast(dict[str, Any], self._handle_response(response))
        return CountResponse(**result).count

    async def lookup_by_id_or_name(
        self,
        id_: RowId | None = None,
        name: str | None = None,
    ) -> tuple[RowId, ResponseT]:
        """Lookup by ID or name.

        Parameters
        ----------
        id_
            Row ID (optional)
        name
            Row name (optional)

        Returns
        -------
            Tuple of (resolved_id, row_data)

        Raises
        ------
        RemoteAPIError
            If neither id nor name is provided or the API request fails
        """
        params: dict[str, Any] = {}
        if id_ is not None:
            params["id"] = id_
        if name is not None:
            params["name"] = name

        response = await self.client.get(
            f"{self.endpoint}/lookup_by_id_or_name",
            params=params,
        )

        result = cast(dict[str, Any], self._handle_response(response))
        lookup_response = LookupResponse[ResponseT](**result)
        return lookup_response.id, self.response_model(**result["data"])

    # UPDATE operations

    async def update_row(self, row_id: RowId, **data: Any) -> ResponseT:
        """Update a single row.

        Parameters
        ----------
        row_id
            Row ID
        **data
            Fields to update as keyword arguments

        Returns
        -------
            Updated row

        Raises
        ------
        RemoteAPIError
            If the row is not found or the API request fails
        """
        response = await self.client.put(
            f"{self.endpoint}/update_row/{row_id}",
            json=data,
        )

        result = cast(dict[str, Any], self._handle_response(response))
        return self.response_model(**result)

    async def update_rows(self, data: list[dict]) -> list[ResponseT]:
        """Update multiple rows.

        Parameters
        ----------
        data
            List of row data dictionaries, each must contain an 'id' field

        Returns
        -------
            List of updated rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        ValidationError
            If any row data is invalid
        """
        response = await self.client.put(
            f"{self.endpoint}/update_rows",
            json=data,
        )

        result = cast(list[dict[str, Any]], self._handle_response(response))
        return [self.response_model(**item) for item in result]

    # DELETE operations

    async def delete_row(self, row_id: RowId, *, capture_data: bool = True) -> ResponseT | None:
        """Delete a single row.

        Parameters
        ----------
        row_id
            Row ID
        capture_data
            Whether to return deleted row data (default: True)

        Returns
        -------
            Deleted row data if capture_data=True, otherwise None

        Raises
        ------
        RemoteAPIError
            If the row is not found or the API request fails
        """
        response = await self.client.delete(
            f"{self.endpoint}/delete_row/{row_id}",
            params={"capture_data": capture_data},
        )

        result = cast(dict[str, Any], self._handle_response(response))

        if not capture_data:
            return None

        return self.response_model(**result)

    async def delete_rows(
        self,
        ids: list[RowId],
        *,
        capture_data: bool = False,
    ) -> list[ResponseT] | int:
        """Delete multiple rows.

        Parameters
        ----------
        ids
            List of row IDs to delete
        capture_data
            Whether to return deleted row data (default: False)

        Returns
        -------
            List of deleted rows if capture_data=True, otherwise count

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        serialized_ids = [str(id_) if not isinstance(id_, int) else id_ for id_ in ids]
        response = await self.client.request(
            "DELETE",
            f"{self.endpoint}/delete_rows",
            json=serialized_ids,
            params={"capture_data": capture_data},
        )

        result = cast(list[dict[str, Any]] | dict[str, Any], self._handle_response(response))

        if capture_data:
            return [self.response_model(**item) for item in cast(list[dict[str, Any]], result)]
        return CountResponse(**cast(dict[str, Any], result)).count

    async def bulk_delete_rows(self, ids: list[RowId]) -> int:
        """Bulk delete rows (returns count only).

        Parameters
        ----------
        ids
            List of row IDs to delete

        Returns
        -------
            Number of rows deleted

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        serialized_ids = [str(id_) if not isinstance(id_, int) else id_ for id_ in ids]
        response = await self.client.request(
            "DELETE",
            f"{self.endpoint}/bulk_delete_rows",
            json=serialized_ids,
        )

        result = cast(dict[str, Any], self._handle_response(response))
        return CountResponse(**result).count

    # FILTER/QUERY operations

    async def filter_rows(
        self,
        filters: list[Filter] | None = None,
        logical_op: str = "and",
        order_by: OrderBy | list[OrderBy] | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[ResponseT]:
        """Filter rows with complex criteria.

        Parameters
        ----------
        filters
            List of filter conditions (default: None)
        logical_op
            Logical operator for combining filters: "and" or "or" (default: "and")
        order_by
            Ordering specification (default: None)
        skip
            Number of rows to skip (default: 0)
        limit
            Maximum rows to return (default: None)

        Returns
        -------
            List of filtered rows

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        request_data = FilterRequest(
            filters=filters or [],
            logical_op=logical_op,
            order_by=order_by,
            skip=skip,
            limit=limit,
        )

        response = await self.client.post(
            f"{self.endpoint}/filter_rows",
            json=request_data.model_dump(mode="json"),
        )

        result = cast(list[dict[str, Any]], self._handle_response(response))
        return [self.response_model(**item) for item in result]

    async def filter_rows_streaming(
        self,
        filters: list[Filter] | None = None,
        logical_op: str = "and",
        order_by: OrderBy | list[OrderBy] | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> AsyncGenerator[ResponseT]:
        """Filter rows with streaming response (NDJSON format).

        Parameters
        ----------
        filters
            List of filter conditions (default: None)
        logical_op
            Logical operator for combining filters: "and" or "or" (default: "and")
        order_by
            Ordering specification (default: None)
        skip
            Number of rows to skip (default: 0)
        limit
            Maximum rows to return (default: None)

        Yields
        ------
            Filtered row data objects

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        request_data = FilterRequest(
            filters=filters or [],
            logical_op=logical_op,
            order_by=order_by,
            skip=skip,
            limit=limit,
        )

        async with self.client.stream(
            "POST",
            f"{self.endpoint}/filter_rows_streaming",
            json=request_data.model_dump(mode="json"),
        ) as response:
            if unexpected(response.status_code != 200):
                content = await response.aread()
                raise RemoteAPIError(
                    f"API request failed with status {response.status_code}: {content.decode()}"
                )

            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = self.response_model.model_validate_json(line)
                        yield data
                    except ValidationError as uexc:
                        logger.error(f"Failed to parse streaming response: {uexc}")
                        # Check if it's an error message
                        try:
                            error_data = json.loads(line)
                            if "error" in error_data:
                                raise RemoteAPIError(f"Stream error: {error_data['error']}") from uexc
                        except json.JSONDecodeError:
                            pass
                        raise

    async def count_filtered_rows(
        self,
        filters: list[Filter] | None = None,
        logical_op: str = "and",
    ) -> int:
        """Count filtered rows.

        Parameters
        ----------
        filters
            List of filter conditions (default: None)
        logical_op
            Logical operator for combining filters: "and" or "or" (default: "and")

        Returns
        -------
            Number of rows matching the filter

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        request_data = FilterRequest(
            filters=filters or [],
            logical_op=logical_op,
        )

        response = await self.client.post(
            f"{self.endpoint}/count_filtered_rows",
            json=request_data.model_dump(mode="json"),
        )

        result = cast(dict[str, Any], self._handle_response(response))
        return CountResponse(**result).count

    async def filter_one(
        self,
        filters: list[Filter],
        logical_op: str = "and",
    ) -> ResponseT:
        """Filter to get exactly one row.

        Parameters
        ----------
        filters
            List of filter conditions (required)
        logical_op
            Logical operator for combining filters: "and" or "or" (default: "and")

        Returns
        -------
            Single matching row

        Raises
        ------
        RemoteAPIError
            If no rows match or multiple rows match
        """
        request_data = FilterRequest(
            filters=filters,
            logical_op=logical_op,
        )

        response = await self.client.post(
            f"{self.endpoint}/filter_one",
            json=request_data.model_dump(mode="json"),
        )

        result = cast(dict[str, Any], self._handle_response(response))
        return self.response_model(**result)

    async def filter_one_or_none(
        self,
        filters: list[Filter],
        logical_op: str = "and",
    ) -> ResponseT | None:
        """Filter to get one row or None.

        Parameters
        ----------
        filters
            List of filter conditions (required)
        logical_op
            Logical operator for combining filters: "and" or "or" (default: "and")

        Returns
        -------
            Single matching row or None if no match

        Raises
        ------
        RemoteAPIError
            If multiple rows match or the API request fails
        """
        request_data = FilterRequest(
            filters=filters,
            logical_op=logical_op,
        )

        response = await self.client.post(
            f"{self.endpoint}/filter_one_or_none",
            json=request_data.model_dump(mode="json"),
        )

        result = cast(dict[str, Any] | None, self._handle_response(response))
        if result is None:
            return None
        return self.response_model(**result)

    async def find_by(
        self,
        order_by: OrderBy | list[OrderBy] | None = None,
        skip: int = 0,
        limit: int | None = None,
        **query_params: Any,
    ) -> list[ResponseT]:
        """Find rows by field values.

        Parameters
        ----------
        order_by
            Ordering specification (default: None)
        skip
            Number of rows to skip (default: 0)
        limit
            Maximum rows to return (default: None)
        **query_params
            Field values to match (equality filters)

        Returns
        -------
            List of matching rows

        Raises
        ------
        RemoteAPIError
            If the API request fails

        Example
        -------
        >>> results = await client.find_by(
        ...     name="test",
        ...     status="active",
        ...     order_by=OrderBy(field="created_at", direction="desc"),
        ...     limit=10
        ... )
        """
        request_body = {**query_params}
        if order_by is not None:
            if isinstance(order_by, list):  # pragma: no cover
                request_body["order_by"] = [o.model_dump() for o in order_by]
            else:
                request_body["order_by"] = order_by.model_dump()
        request_body["skip"] = skip
        if limit is not None:
            request_body["limit"] = limit

        response = await self.client.post(
            f"{self.endpoint}/find_by",
            json=request_body,
        )

        result = cast(list[dict[str, Any]], self._handle_response(response))
        return [self.response_model(**item) for item in result]

    async def find_one_by(self, **query_params: Any) -> ResponseT:
        """Find exactly one row by field values.

        Parameters
        ----------
        **query_params
            Field values to match (equality filters)

        Returns
        -------
            Single matching row

        Raises
        ------
        RemoteAPIError
            If no rows match or multiple rows match

        Example
        -------
        >>> result = await client.find_one_by(name="unique_name")
        """
        response = await self.client.post(
            f"{self.endpoint}/find_one_by",
            json=query_params,
        )

        result = cast(dict[str, Any], self._handle_response(response))
        return self.response_model(**result)


class RemoteAPI:
    """High-level client for managing multiple table operations.

    This class provides a convenient way to create and manage multiple
    RemoteTableOperations instances sharing a single HTTP client.

    Parameters
    ----------
    base_url
        Base URL of the API server (e.g., "http://localhost:8000")
    api_prefix
        API route prefix (default: "/api/v1")
    timeout
        Request timeout in seconds (default: 30.0)
    auth_token
        Optional Bearer token for authentication

    Example
    -------
    >>> from pydantic import BaseModel
    >>>
    >>> class AlgorithmResponse(BaseModel):
    ...     id: int
    ...     name: str
    >>>
    >>> class AlgorithmCreate(BaseModel):
    ...     name: str
    >>>
    >>> class DatasetResponse(BaseModel):
    ...     id: int
    ...     name: str
    >>>
    >>> class DatasetCreate(BaseModel):
    ...     name: str
    >>>
    >>> async with RemoteAPI("http://localhost:8000", auth_token="token") as api:
    ...     # Get table clients - no nested async with!
    ...     algo_client = api.table("algorithms", AlgorithmResponse, AlgorithmCreate)
    ...     data_client = api.table("datasets", DatasetResponse, DatasetCreate)
    ...
    ...     # Use both clients
    ...     algo = await algo_client.create_row(name="Test")
    ...     dataset = await data_client.create_row(name="Dataset 1")
    """

    def __init__(
        self,
        base_url: str,
        api_prefix: str = "/api/v1",
        timeout: float = 30.0,
        auth_token: str | None = None,
    ):
        """Initialize the remote API client."""
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token

        # Headers
        self.headers = {}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"

        # Client will be initialized in __aenter__
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> RemoteAPI:
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self.headers,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    def _check_client(self) -> None:
        """Ensure client is initialized."""
        if self.client is None:
            raise RemoteAPIError("Client not initialized. Use 'async with RemoteAPI(...)' context manager.")

    # mypy doesn't fully support PEP 695 method-level generics yet
    def table[ResponseT, CreateT](
        self,
        table_name: str,
        response_model: type[ResponseT],
        create_model: type[CreateT],
    ) -> RemoteTableOperations[ResponseT, CreateT]:  # type: ignore[type-var]
        """Create a table operations client for a specific table.

        Parameters
        ----------
        table_name
            Name of the table endpoint
        response_model
            Pydantic model class for response data
        create_model
            Pydantic model class for create data

        Returns
        -------
            Table operations client for the specified table

        Note
        ----
        The returned client shares the HTTP client from this RemoteAPI instance.
        No need for nested async with statements!

        Example
        -------
        >>> async with RemoteAPI("http://localhost:8000") as api:
        ...     algo_client = api.table("algorithms", AlgorithmResponse, AlgorithmCreate)
        ...     data_client = api.table("datasets", DatasetResponse, DatasetCreate)
        ...
        ...     # Both clients work independently
        ...     algos = await algo_client.get_rows()
        ...     datasets = await data_client.get_rows()
        """
        self._check_client()

        endpoint = f"{self.base_url}{self.api_prefix}/{table_name}"

        # mypy doesn't fully support PEP 695 method-level generics yet
        return RemoteTableOperations[ResponseT, CreateT](  # type: ignore[type-var]
            client=cast(httpx.AsyncClient, self.client),
            endpoint=endpoint,
            response_model=response_model,
            create_model=create_model,
        )


class RemoteFileOperations[ResponseT: BaseModel, CreateT: BaseModel](
    RemoteTableOperations[ResponseT, CreateT]
):
    """Mixin for tables that support load and download operations."""

    _default_filename_prefix: str = "file"

    async def load(
        self,
        path: Path | str,
        load_type: LoadType = LoadType.in_place,
        *,
        validate: bool = True,
        **data: Any,
    ) -> ResponseT:
        """Load a file and create a record.

        Parameters
        ----------
        path
            Path to the data file
        load_type
            How to handle the file (in_place, link, or copy)
        validate
            Whether to validate data on the server (default: True)
        **data
            Additional fields for the record

        Returns
        -------
            Created row

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        request_body = {
            "path": str(path),
            "load_type": load_type.value,
            "data": data,
        }

        response = await self.client.post(
            f"{self.endpoint}/load",
            json=request_body,
            params={"validate": validate},
        )

        result = cast(dict[str, Any], self._handle_response(response, expected_status=201))
        return self.response_model(**result)

    async def download(
        self,
        row_id: RowId,
        output_path: Path | str | None = None,
    ) -> Path:
        """Download a file.

        Parameters
        ----------
        row_id
            Row ID
        output_path
            Optional output path relative to download area.

        Returns
        -------
            Path to the downloaded file

        Raises
        ------
        RemoteAPIError
            If the API request fails
        """
        download_dir = Path(global_config.storage.download_area)

        params = {}
        if output_path is not None:
            params["output_path"] = str(output_path)

        response = await self.client.get(
            f"{self.endpoint}/download/{row_id}",
            params=params,
        )

        if unexpected(response.status_code != 200):
            self._handle_response(response, expected_status=200)

        content_disposition = response.headers.get("content-disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
        else:  # pragma: no cover
            filename = f"{self._default_filename_prefix}_{row_id}"

        if output_path is not None:
            file_path = download_dir / Path(output_path)
        else:
            file_path = download_dir / Path(filename)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(response.content)

        return file_path
