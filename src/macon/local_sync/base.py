"""Base class for table-specific local operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pydantic import BaseModel

from ..db.base import Base
from ..local_async.base import (
    LocalOperations,
)

F = TypeVar("F", bound=Callable[..., Any])


def sync_wrapper(async_method: Callable[..., Any]) -> Callable[[F], F]:
    """Decorator that wraps an async method call with asyncio.run.

    Parameters
    ----------
    async_method
        The async method to wrap (unbound method reference)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            coro = func(self, *args, **kwargs)
            return asyncio.run(coro)

        wrapped.__doc__ = async_method.__doc__
        return wrapped  # type: ignore

    return decorator


class SyncOperations[T: Base, ResponseT: BaseModel, CreateT: BaseModel]:
    """Synchronous wrapper for local operations.

    Wraps async LocalOperations methods to provide synchronous versions
    for use in non-async contexts like CLI commands or scripts.

    WARNING: These methods use asyncio.run() internally and cannot be
    called from within an already-running event loop.
    """

    def __init__(self, async_ops: LocalOperations[T, ResponseT, CreateT]) -> None:
        self.async_ops = async_ops

    @sync_wrapper(LocalOperations.create_row)
    def create_row(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.create_row(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.create_rows)
    def create_rows(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.create_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.create_rows_batched)
    def create_rows_batched(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.create_rows_batched(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.bulk_insert_rows)
    def bulk_insert_rows(self, *args: Any, **kwargs: Any) -> int:
        return self.async_ops.bulk_insert_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.get_row)
    def get_row(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.get_row(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.get_row_by_name)
    def get_row_by_name(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.get_row_by_name(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.get_rows)
    def get_rows(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.get_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.get_row_or_none)
    def get_row_or_none(self, *args: Any, **kwargs: Any) -> ResponseT | None:
        return self.async_ops.get_row_or_none(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.count_rows)
    def count_rows(self, *args: Any, **kwargs: Any) -> int:
        return self.async_ops.count_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.lookup_by_id_or_name)
    def lookup_by_id_or_name(self, *args: Any, **kwargs: Any) -> tuple[int, ResponseT | None]:
        return self.async_ops.lookup_by_id_or_name(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.update_row)
    def update_row(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.update_row(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.update_rows)
    def update_rows(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.update_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.delete_row)
    def delete_row(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return self.async_ops.delete_row(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.delete_rows)
    def delete_rows(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]] | None:
        return self.async_ops.delete_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.bulk_delete_rows)
    def bulk_delete_rows(self, *args: Any, **kwargs: Any) -> int:
        return self.async_ops.bulk_delete_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.filter_rows)
    def filter_rows(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.filter_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.count_filtered_rows)
    def count_filtered_rows(self, *args: Any, **kwargs: Any) -> int:
        return self.async_ops.count_filtered_rows(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.filter_one)
    def filter_one(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.filter_one(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.filter_one_or_none)
    def filter_one_or_none(self, *args: Any, **kwargs: Any) -> ResponseT | None:
        return self.async_ops.filter_one_or_none(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.find_by)
    def find_by(self, *args: Any, **kwargs: Any) -> list[ResponseT]:
        return self.async_ops.find_by(*args, **kwargs)  # type: ignore

    @sync_wrapper(LocalOperations.find_one_by)
    def find_one_by(self, *args: Any, **kwargs: Any) -> ResponseT:
        return self.async_ops.find_one_by(*args, **kwargs)  # type: ignore
