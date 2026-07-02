"""Sync wrapper for remote funcs operations — auto-delegates via __getattr__."""

from __future__ import annotations

import asyncio
from typing import Any

from ..remote_async.funcs import AsyncRemoteFuncs


class SyncRemoteFuncs:
    """Synchronous wrapper for AsyncRemoteFuncs.

    Provides blocking synchronous methods that wrap async remote funcs operations
    using asyncio.run(). Methods are generated dynamically — any method available
    on AsyncRemoteFuncs is automatically available here as a sync version.

    Warning
    -------
    Cannot be used from async code (will raise RuntimeError).

    Examples
    --------
    >>> funcs = SyncRemoteFuncs(async_funcs)
    >>> result = funcs.estimate_pdf(estimator_id=1, dataset_id=2, row=0)
    """

    def __init__(self, async_ops: AsyncRemoteFuncs) -> None:
        self.async_ops = async_ops

    def __getattr__(self, name: str) -> Any:
        async_method = getattr(self.async_ops, name)
        if not callable(async_method):
            return async_method

        def sync_method(*args: Any, **kwargs: Any) -> Any:
            return asyncio.run(async_method(*args, **kwargs))

        sync_method.__name__ = name
        sync_method.__doc__ = async_method.__doc__
        return sync_method
