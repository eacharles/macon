"""Sync wrappers for local_async.funcs — auto-generated via __getattr__."""

import asyncio
from typing import Any

from .. import local_async


def __getattr__(name: str) -> Any:
    """Auto-generate sync wrappers for any function in local_async.funcs."""
    async_func = getattr(local_async.funcs, name, None)
    if async_func is None:
        raise AttributeError(f"module 'rail_svc.local_sync.funcs' has no attribute {name!r}")

    def sync_func(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(async_func(*args, **kwargs))

    sync_func.__name__ = name
    sync_func.__doc__ = async_func.__doc__
    sync_func.__module__ = __name__
    return sync_func
