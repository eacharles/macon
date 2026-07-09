"""Responsex model for load_catalog_yaml function."""

import uuid
from typing import TypeVar

from pydantic import BaseModel

from .filtering import Filter, OrderBy

ResponseT = TypeVar("ResponseT", bound=BaseModel)  # Response schema type


class AsyncRouteError(Exception):
    """Custom exception for async route handling errors."""


class RemoteAPIError(Exception):
    """Custom exception for remote API errors."""


class CountResponse(BaseModel):
    """Response model for count operations."""

    count: int


class LookupResponse[ResponseT](BaseModel):
    """Response model for lookup operations."""

    id: int | uuid.UUID
    data: ResponseT


class DeleteResponse(BaseModel):
    """Response model for delete operations."""

    deleted: bool = True


class FilterRequest(BaseModel):
    """Request model for filter operations."""

    filters: list[Filter] = []
    logical_op: str = "and"
    order_by: OrderBy | list[OrderBy] | None = None
    skip: int = 0
    limit: int | None = None


class FindRequest(BaseModel):
    """Request model for find operations."""

    order_by: OrderBy | list[OrderBy] | None = None
    skip: int = 0
    limit: int | None = None

    class ConfigDict:
        """pydantic config"""

        extra = "allow"  # Allow additional fields for query params
