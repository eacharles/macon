"""Sync wrapper for remote table operations."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from pydantic import BaseModel

from ..remote_async.base import (
    AsyncRemoteOperations,
)


def _make_sync_method(method_name: str) -> Any:
    """Create a sync method that delegates to self.async_ops.<method_name>."""

    def sync_method(self: Any, *args: Any, **kwargs: Any) -> Any:
        coro = getattr(self.async_ops, method_name)(*args, **kwargs)

        async def _run() -> Any:
            async with self.async_ops:
                return await coro

        return asyncio.run(_run())

    sync_method.__name__ = method_name
    return sync_method


_BASE_METHODS = [
    "create_row",
    "create_rows",
    "create_rows_batched",
    "bulk_insert_rows",
    "get_row",
    "get_row_by_name",
    "get_rows",
    "get_row_or_none",
    "count_rows",
    "lookup_by_id_or_name",
    "update_row",
    "update_rows",
    "delete_row",
    "delete_rows",
    "bulk_delete_rows",
    "filter_rows",
    "count_filtered_rows",
    "filter_one",
    "filter_one_or_none",
    "find_by",
    "find_one_by",
]


class SyncRemoteOperations[ResponseT: BaseModel, CreateT: BaseModel]:
    """Synchronous wrapper for AsyncRemoteOperations.

    Provides blocking synchronous methods that wrap async remote operations
    using asyncio.run(). Each method call opens and closes the async context.

    Warning
    -------
    Cannot be used from async code (will raise RuntimeError).
    """

    _extra_methods: ClassVar[list[str]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for method_name in cls._extra_methods:
            if not hasattr(cls, method_name) or method_name not in cls.__dict__:
                setattr(cls, method_name, _make_sync_method(method_name))

    def __init__(self, async_ops: AsyncRemoteOperations[ResponseT, CreateT]) -> None:
        self.async_ops = async_ops


# Generate base CRUD methods on SyncRemoteOperations
for _name in _BASE_METHODS:
    setattr(SyncRemoteOperations, _name, _make_sync_method(_name))
