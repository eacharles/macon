from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, Body, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse, FileResponse
import tables_io
from pydantic import BaseModel, ValidationError

from .. import local_async, models
from ..config import config as global_config
from ..common import LoadType, unexpected, str_to_slice
from ..db.base import Base
from ..local_async import LocalOperations
from ..models import CountResponse, DeleteResponse, FilterRequest, LookupResponse, OrderBy

# Configure logging
logger = logging.getLogger(__name__)


def require_auth(authorization: str = Header(None)) -> str:
    """Dependency to require authentication.

    Parameters
    ----------
    authorization : str
        Authorization header value

    Raises
    ------
    HTTPException
        If authorization is invalid

    Returns
    -------
    str
        The validated token

    Example
    -------
    >>> @router.get("/protected")
    >>> async def protected_route(token: str = Depends(require_auth)):
    ...     return {"message": "authenticated"}
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header format"
        )

    token = authorization[7:]  # Remove 'Bearer ' prefix

    # TODO: Implement proper token validation
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return token


def validate_pagination_params(skip: int, limit: int | None) -> tuple[int, int | None]:
    """Validate pagination parameters.

    Parameters
    ----------
    skip : int
        Number of rows to skip
    limit : int | None
        Maximum rows to return

    Returns
    -------
    tuple[int, int | None]
        Validated params

    Raises
    ------
    HTTPException
        If validation fails
    """
    if skip < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="skip must be non-negative")

    if limit is not None:
        if limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be positive")
        if limit > 10000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit cannot exceed 10000")

    return skip, limit


def validate_batch_size(batch_size: int) -> int:
    """Validate batch size parameter.

    Parameters
    ----------
    batch_size : int
        Batch size to validate

    Returns
    -------
    int
        Validated batch size

    Raises
    ------
    HTTPException
        If validation fails
    """
    if not 1 <= batch_size <= 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="batch_size must be between 1 and 10000"
        )
    return batch_size


def create_table_router[T: Base, ResponseT: BaseModel, CreateT: BaseModel](
    name: str,
    operations: LocalOperations[T, ResponseT, CreateT],
) -> APIRouter:
    """Create a FastAPI router with CRUD endpoints for a table.

    Parameters
    ----------
    name : str
        Name of the table (used for router prefix and tags)
    operations : LocalOperations
        The local operations instance for this table

    Returns
    -------
    APIRouter
        FastAPI router with all CRUD endpoints
    """
    router = APIRouter(prefix=f"/{name}", tags=[name])

    # Extract the response model type from operations
    # This gets the actual Pydantic model class at runtime
    response_model = operations.table_ops.ctx.response_class

    # CREATE endpoints
    @router.post("/create_row", status_code=status.HTTP_201_CREATED, response_model=response_model)
    async def create_row(
        data: dict = Body(...),
        *,
        validate: bool = Query(default=True, description="Whether to validate data"),
    ) -> ResponseT:
        """Create a single row.

        Request Body:
            JSON object with row data

        Query Parameters:
            validate (bool): Whether to validate data (default: true)

        Returns:
            201: Created row
            400: Validation error
            500: Internal server error
        """
        try:
            result = await operations.create_row(validate=validate, **data)
            return result
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": exc.errors()},
            ) from exc
        except Exception as exc:
            logger.exception("Error creating row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/create_rows", status_code=status.HTTP_201_CREATED, response_model=list[ResponseT])
    async def create_rows(
        data: list[dict] = Body(...),
        *,
        validate: bool = Query(default=True, description="Whether to validate data"),
    ) -> list[ResponseT]:
        """Create multiple rows.

        Request Body:
            JSON array of objects

        Query Parameters:
            validate (bool): Whether to validate data (default: true)

        Returns:
            201: Array of created rows
            400: Validation error or invalid input
            500: Internal server error
        """
        if len(data) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create more than 10000 rows at once"
            )

        try:
            results = await operations.create_rows(data, validate=validate)
            return results
        except ValidationError as uexc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": uexc.errors()},
            ) from uexc
        except Exception as exc:
            logger.exception("Error creating rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/create_rows_batched", status_code=status.HTTP_201_CREATED, response_model=list[ResponseT])
    async def create_rows_batched(
        data: list[dict] = Body(...),
        *,
        validate: bool = Query(default=True, description="Whether to validate data"),
        batch_size: int = Query(1000, ge=1, le=10000, description="Size of each batch"),
    ) -> list[ResponseT]:
        """Create multiple rows in batches.

        Request Body:
            JSON array of objects

        Query Parameters:
            validate (bool): Whether to validate data (default: true)
            batch_size (int): Size of each batch (default: 1000, max: 10000)

        Returns:
            201: Array of created rows
            400: Validation error or invalid input
            500: Internal server error
        """
        try:
            results = await operations.create_rows_batched(data, validate=validate, batch_size=batch_size)
            return results
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": exc.errors()},
            ) from exc
        except Exception as exc:
            logger.exception("Error creating rows batched")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/bulk_insert_rows", status_code=status.HTTP_201_CREATED, response_model=CountResponse)
    async def bulk_insert_rows(
        data: list[dict] = Body(...),
        *,
        validate: bool = Query(default=True, description="Whether to validate data"),
    ) -> CountResponse:
        """Bulk insert rows (returns count only).

        Request Body:
            JSON array of objects

        Query Parameters:
            validate (bool): Whether to validate data (default: true)

        Returns:
            201: Object with count of inserted rows
            400: Validation error or invalid input
            500: Internal server error
        """
        if len(data) > 100000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot bulk insert more than 100000 rows at once",
            )

        try:
            count = await operations.bulk_insert_rows(data, validate=validate)
            return CountResponse(count=count)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": exc.errors()},
            ) from exc
        except Exception as exc:
            logger.exception("Error bulk inserting rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    # READ endpoints
    @router.get("/get_row/{row_id}", response_model=response_model)
    async def get_row(
        row_id: int,
    ) -> ResponseT:
        """Get a single row by ID.

        Path Parameters:
            row_id (int): Row ID

        Returns:
            200: Row data
            404: Row not found
            500: Internal server error
        """
        try:
            result = await operations.get_row(row_id)
            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error getting row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.get("/get_row_or_none/{row_id}", response_model=response_model | None)
    async def get_row_or_none(
        row_id: int,
    ) -> ResponseT | None:
        """Get a single row by ID or None if not found.

        Path Parameters:
            row_id (int): Row ID

        Returns:
            200: Row data or null
            500: Internal server error
        """
        try:
            result = await operations.get_row_or_none(row_id)
            return result
        except Exception as exc:
            logger.exception("Error getting row or none")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.get("/get_row_by_name/{name}", response_model=response_model)
    async def get_row_by_name(name: str) -> ResponseT:
        """Get a single row by name.

        Path Parameters:
            name (str): Row name

        Returns:
            200: Row data
            404: Row not found
            500: Internal server error
        """
        try:
            result = await operations.get_row_by_name(name)
            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error getting row by name")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.get("/get_rows", response_model=list[ResponseT])
    async def get_rows(
        skip: int = Query(0, ge=0, description="Number of rows to skip"),
        limit: int | None = Query(None, ge=1, le=10000, description="Maximum rows to return"),
    ) -> list[ResponseT]:
        """Get multiple rows with pagination.

        Query Parameters:
            skip (int): Number of rows to skip (default: 0, min: 0)
            limit (int): Maximum rows to return (default: unlimited, max: 10000)

        Returns:
            200: Array of rows
            400: Invalid pagination parameters
            500: Internal server error
        """
        try:
            results = await operations.get_rows(skip=skip, limit=limit)  # type: ignore
            return results
        except Exception as exc:
            logger.exception("Error getting rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.get("/get_rows_streaming")
    async def get_rows_streaming(
        skip: int = Query(0, ge=0, description="Number of rows to skip"),
        limit: int | None = Query(None, ge=1, le=10000, description="Maximum rows to return"),
    ) -> StreamingResponse:
        """Get rows as a streaming response (NDJSON format).

        Query Parameters:
            skip (int): Number of rows to skip (default: 0, min: 0)
            limit (int): Maximum rows to return (default: unlimited, max: 10000)

        Returns:
            200: Stream of newline-delimited JSON objects
            400: Invalid pagination parameters
            500: Internal server error

        Note:
            Response format is NDJSON (newline-delimited JSON), not a JSON array.
            Each line is a complete JSON object representing one row.
        """

        async def generate() -> AsyncGenerator:
            try:
                async for row in operations.get_rows_streaming(skip=skip, limit=limit):
                    yield row.model_dump_json() + "\n"
            except Exception as e:
                logger.exception("Error in streaming rows")
                # In streaming, we can't raise HTTP exceptions after starting
                yield f'{{"error": "{str(e)}"}}\n'

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    @router.get("/count_rows", response_model=CountResponse)
    async def count_rows() -> CountResponse:
        """Get total count of rows.

        Returns:
            200: Object with count
            500: Internal server error
        """
        try:
            count = await operations.count_rows()  # type: ignore
            return CountResponse(count=count)
        except Exception as e:
            logger.exception("Error counting rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    @router.get("/lookup_by_id_or_name", response_model=LookupResponse[ResponseT])
    async def lookup_by_id_or_name(
        id_: int | None = Query(None, description="Row ID"),
        name: str | None = Query(None, description="Row name"),
    ) -> LookupResponse[ResponseT]:
        """Lookup by ID or name.

        Query Parameters:
            id_ (int): Row ID (optional)
            name (str): Row name (optional)

        Note:
            At least one of id or name must be provided.

        Returns:
            200: Object with resolved ID and row data
            400: Neither id nor name provided
            404: Row not found
            500: Internal server error
        """
        if id_ is None and name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'id_' or 'name' parameter",
            )

        try:
            resolved_id, result = await operations.lookup_by_id_or_name(id_, name)  # type: ignore

            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

            return LookupResponse(id=resolved_id, data=result)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error in lookup")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    # UPDATE endpoints
    @router.put("/update_row/{row_id}", response_model=response_model)
    @router.patch("/update_row/{row_id}", response_model=response_model)
    async def update_row(
        row_id: int,
        data: dict = Body(...),
    ) -> ResponseT:
        """Update a single row.

        Path Parameters:
            row_id (int): Row ID

        Request Body:
            JSON object with fields to update

        Returns:
            200: Updated row
            400: Validation error
            404: Row not found
            500: Internal server error
        """
        try:
            result = await operations.update_row(row_id, **data)
            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return result
        except HTTPException:
            raise
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": e.errors()},
            ) from e
        except Exception as exc:
            logger.exception("Error updating row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.put("/update_rows", response_model=list[ResponseT])
    @router.patch("/update_rows", response_model=list[ResponseT])
    async def update_rows(data: list[dict] = Body(...)) -> list[ResponseT]:
        """Update multiple rows.

        Request Body:
            JSON array of objects, each containing an 'id' field

        Returns:
            200: Array of updated rows
            400: Validation error or invalid input
            404: One or more rows not found
            500: Internal server error
        """
        if len(data) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update more than 10000 rows at once"
            )

        # Validate that all items have an 'id' field
        for i, item in enumerate(data):
            if unexpected(not isinstance(item, dict)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item at index {i} is not an object"
                )
            if "id" not in item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item at index {i} missing 'id' field"
                )

        try:
            results = await operations.update_rows(data)
            return results
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Validation error", "details": e.errors()},
            ) from e
        except Exception as e:
            logger.exception("Error updating rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e

    # DELETE endpoints
    @router.delete("/delete_row/{row_id}", response_model=response_model | DeleteResponse)
    async def delete_row(
        row_id: int,
        *,
        capture_data: bool = Query(default=True, description="Whether to return deleted row data"),
    ) -> ResponseT | DeleteResponse:
        """Delete a single row.

        Path Parameters:
            id (int): Row ID

        Query Parameters:
            capture_data (bool): Whether to return deleted row data (default: true)

        Returns:
            200: Deleted row data (if capture_data=true) or success message
            404: Row not found
            500: Internal server error
        """
        try:
            result = await operations.delete_row(row_id, capture_data=capture_data)

            if result is None and capture_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

            if result is None:
                return DeleteResponse()
            return response_model(**result)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error deleting row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.delete("/delete_rows", response_model=list[ResponseT] | CountResponse)
    async def delete_rows(
        data: list[int] = Body(...),
        *,
        capture_data: bool = Query(default=False, description="Whether to return deleted row data"),
    ) -> list[ResponseT] | CountResponse:
        """Delete multiple rows.

        Request Body:
            JSON array of row IDs

        Query Parameters:
            capture_data (bool): Whether to return deleted row data (default: false)

        Returns:
            200: Array of deleted rows (if capture_data=true) or count
            400: Invalid input
            500: Internal server error
        """
        if len(data) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete more than 10000 rows at once"
            )

        # Validate all IDs are integers
        for i, item in enumerate(data):
            if unexpected(not isinstance(item, int)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item at index {i} is not an integer"
                )

        try:
            result = await operations.delete_rows(data, capture_data=capture_data)
            if capture_data:
                assert result is not None
                return [response_model(**item_) for item_ in result]
            return CountResponse(count=len(data))
        except Exception as exc:
            logger.exception("Error deleting rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.delete("/bulk_delete_rows", response_model=CountResponse)
    async def bulk_delete_rows(data: list[int] = Body(...)) -> CountResponse:
        """Bulk delete rows (returns count only).

        Request Body:
            JSON array of row IDs

        Returns:
            200: Object with count of deleted rows
            400: Invalid input
            500: Internal server error
        """
        if len(data) > 100000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot bulk delete more than 100000 rows at once",
            )

        # Validate all IDs are integers
        for i, item in enumerate(data):
            if unexpected(not isinstance(item, int)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item at index {i} is not an integer"
                )

        try:
            count = await operations.bulk_delete_rows(data)
            return CountResponse(count=count)
        except Exception as exc:
            logger.exception("Error bulk deleting rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    # FILTER/QUERY endpoints
    @router.post("/filter_rows", response_model=list[ResponseT])
    async def filter_rows(request: FilterRequest) -> list[ResponseT]:
        """Filter rows with complex criteria.

        Request Body:
            {
                "filters": [{"field": "name", "op": "eq", "value": "test"}],
                "logical_op": "and",  // "and" or "or"
                "order_by": {"field": "created_at", "direction": "desc"},  // or array
                "skip": 0,
                "limit": 100
            }

        Returns:
            200: Array of filtered rows
            400: Invalid filter syntax
            500: Internal server error
        """
        if request.logical_op not in ("and", "or"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="logical_op must be 'and' or 'or'"
            )

        # Validate pagination
        validate_pagination_params(request.skip, request.limit)

        try:
            results = await operations.filter_rows(  # type: ignore
                filters=request.filters if request.filters else None,
                logical_op=request.logical_op,
                order_by=request.order_by,
                skip=request.skip,
                limit=request.limit,
            )
            return results
        except ValidationError as uexc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid filter syntax", "details": uexc.errors()},
            ) from uexc
        except Exception as exc:
            logger.exception("Error filtering rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/filter_rows_streaming")
    async def filter_rows_streaming(request: FilterRequest) -> StreamingResponse:
        """Filter rows with streaming response (NDJSON format).

        Request Body:
            Same as /filter endpoint

        Returns:
            200: Stream of newline-delimited JSON objects
            400: Invalid filter syntax
            500: Internal server error

        Note:
            Response format is NDJSON (newline-delimited JSON), not a JSON array.
        """
        if unexpected(request.logical_op not in ("and", "or")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="logical_op must be 'and' or 'or'"
            )

        # Validate pagination
        validate_pagination_params(request.skip, request.limit)

        async def generate() -> AsyncGenerator:
            try:
                async for row in operations.filter_rows_streaming(
                    filters=request.filters if request.filters else None,
                    logical_op=request.logical_op,
                    order_by=request.order_by,
                    skip=request.skip,
                    limit=request.limit,
                ):
                    yield row.model_dump_json() + "\n"
            except Exception as e:
                logger.exception("Error in streaming filtered rows")
                yield f'{{"error": "{str(e)}"}}\n'

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    @router.post("/count_filtered_rows", response_model=CountResponse)
    async def count_filtered_rows(request: FilterRequest) -> CountResponse:
        """Count filtered rows.

        Request Body:
            {
                "filters": [{"field": "name", "op": "eq", "value": "test"}],
                "logical_op": "and"
            }

        Returns:
            200: Object with count
            400: Invalid filter syntax
            500: Internal server error
        """
        if unexpected(request.logical_op not in ("and", "or")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="logical_op must be 'and' or 'or'"
            )

        try:
            count = await operations.count_filtered_rows(  # type: ignore
                filters=request.filters if request.filters else None,
                logical_op=request.logical_op,
            )
            return CountResponse(count=count)
        except ValidationError as uexc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid filter syntax", "details": uexc.errors()},
            ) from uexc
        except Exception as exc:
            logger.exception("Error counting filtered rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/filter_one", response_model=response_model)
    async def filter_one(request: FilterRequest) -> ResponseT:
        """Filter to get exactly one row.

        Request Body:
            {
                "filters": [{"field": "name", "op": "eq", "value": "test"}],
                "logical_op": "and"
            }

        Returns:
            200: Single row
            400: Invalid filter syntax or filter returned != 1 row
            404: No rows matched filter
            500: Internal server error
        """
        if not request.filters:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'filters' array is required")

        if unexpected(request.logical_op not in ("and", "or")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="logical_op must be 'and' or 'or'"
            )

        try:
            result = await operations.filter_one(filters=request.filters, logical_op=request.logical_op)  # type: ignore
            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return result
        except HTTPException:
            raise
        except ValidationError as uexc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid filter syntax", "details": uexc.errors()},
            ) from uexc
        except Exception as exc:
            logger.exception("Error filtering one row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/filter_one_or_none", response_model=response_model | None)
    async def filter_one_or_none(request: FilterRequest) -> ResponseT | None:
        """Filter to get one row or None.

        Request Body:
            {
                "filters": [{"field": "name", "op": "eq", "value": "test"}],
                "logical_op": "and"
            }

        Returns:
            200: Single row or null
            400: Invalid filter syntax or filter returned > 1 row
            500: Internal server error
        """
        if not request.filters:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'filters' array is required")

        if unexpected(request.logical_op not in ("and", "or")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="logical_op must be 'and' or 'or'"
            )

        try:
            result = await operations.filter_one_or_none(  # type: ignore
                filters=request.filters, logical_op=request.logical_op
            )
            return result
        except ValidationError as uexc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid filter syntax", "details": uexc.errors()},
            ) from uexc
        except Exception as exc:
            logger.exception("Error filtering one or none row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/find_by", response_model=list[ResponseT])
    async def find_by(request: dict = Body(...)) -> list[ResponseT]:
        """Find rows by field values.

        Request Body:
            {
                "field1": "value1",
                "field2": "value2",
                "order_by": {"field": "created_at", "direction": "desc"},
                "skip": 0,
                "limit": 100
            }

        Note:
            All fields except order_by, skip, and limit are treated as equality filters.

        Returns:
            200: Array of matching rows
            400: Invalid input
            500: Internal server error
        """
        # Extract special parameters
        order_by_data = request.pop("order_by", None)
        skip = request.pop("skip", 0)
        limit = request.pop("limit", None)

        # Remaining fields are query parameters
        query_params = request

        if not query_params:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one query field is required"
            )

        # Validate pagination
        validate_pagination_params(skip, limit)

        # Parse order_by if provided
        order_by: list[OrderBy] | OrderBy | None = None
        if order_by_data:
            try:
                if isinstance(order_by_data, list):
                    order_by = [OrderBy(**o) for o in order_by_data]
                else:
                    order_by = OrderBy(**order_by_data)
            except (TypeError, ValidationError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid order_by syntax", "details": str(e)},
                ) from e

        try:
            results = await operations.find_by(
                order_by=order_by,
                skip=skip,
                limit=limit,
                **query_params,
            )
            return results
        except Exception as exc:
            logger.exception("Error finding rows")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @router.post("/find_one_by", response_model=response_model)
    async def find_one_by(data: dict = Body(...)) -> ResponseT:
        """Find exactly one row by field values.

        Request Body:
            {
                "field1": "value1",
                "field2": "value2"
            }

        Returns:
            200: Single matching row
            400: Invalid input or query returned != 1 row
            404: No rows matched
            500: Internal server error
        """
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one query field is required"
            )

        try:
            result = await operations.find_one_by(**data)
            if result is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error finding one row")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return router
