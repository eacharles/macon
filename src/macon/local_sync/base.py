"""Base class for table-specific local operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

import numpy as np
import qp
from pydantic import BaseModel

from .. import db, models
from ..db.base import Base
from ..local_async.base import (
    LocalOperations,
)

F = TypeVar("F", bound=Callable[..., Any])


def sync_wrapper(async_method: Callable[..., Any]) -> Callable[[F], F]:
    """Decorator that wraps an async method call with asyncio.run and copies its docstring.

    This decorator is designed for creating synchronous wrappers around async methods.
    It automatically calls asyncio.run() on the async method and copies the docstring
    from the async method to the sync wrapper.

    Parameters
    ----------
    async_method : Callable
        The async method to wrap (unbound method reference)

    Returns
    -------
    Callable
        Decorator function that creates a sync wrapper

    Examples
    --------
    >>> class AsyncOps:
    ...     async def get_data(self, x: int) -> int:
    ...         '''Fetch data asynchronously.'''
    ...         return x * 2
    >>>
    >>> class SyncOps:
    ...     def __init__(self, async_ops: AsyncOps):
    ...         self.async_ops = async_ops
    ...
    ...     @sync_wrapper(AsyncOps.get_data)
    ...     def get_data(self, *args, **kwargs):
    ...         return self.async_ops.get_data(*args, **kwargs)
    >>>
    >>> sync_ops = SyncOps(AsyncOps())
    >>> sync_ops.get_data(5)  # Automatically runs in asyncio.run()
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Call the original function to get the coroutine
            coro = func(self, *args, **kwargs)
            # Run it with asyncio.run
            return asyncio.run(coro)

        wrapped.__doc__ = async_method.__doc__
        return wrapped  # type: ignore

    return decorator


class SyncOperations[T: Base, ResponseT: BaseModel, CreateT: BaseModel]:
    """Synchronous wrapper for local operations.

    Wraps async LocalOperations methods to provide synchronous versions
    for use in non-async contexts like CLI commands or scripts.

    WARNING: These methods use asyncio.run() internally and cannot be
    called from within an already-running event loop. Use the async
    LocalOperations directly in async contexts.

    Parameters
    ----------
    async_ops : LocalOperations[T, ResponseT, CreateT]
        The async local operations instance to wrap

    Examples
    --------
    >>> from rail_svc.local import algorithm  # Async version
    >>> from rail_svc.local.base import SyncLocalOperations
    >>>
    >>> # Create sync wrapper for CLI
    >>> algo_sync = SyncLocalOperations(algorithm)
    >>>
    >>> # Use without await (in sync context only)
    >>> result = algo_sync.get_row(row_id=1)  # No await needed
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


class AlgorithmSyncOperations(SyncOperations[db.Algorithm, models.Algorithm, models.AlgorithmCreate]):
    """Operations on local DB for Algorithm table."""


class BandSyncOperations(SyncOperations[db.Band, models.Band, models.BandCreate]):
    """Operations on local DB for Band table."""


class CatalogBandAssocOperations(
    SyncOperations[db.CatalogBandAssoc, models.CatalogBandAssoc, models.CatalogBandAssocCreate]
):
    """Operations on local DB for CatalogBandAssoc table."""


class CatalogTagSyncOperations(SyncOperations[db.CatalogTag, models.CatalogTag, models.CatalogTagCreate]):
    """Operations on local DB for CatalogTag table."""


class DatasetSyncOperations(SyncOperations[db.Dataset, models.Dataset, models.DatasetCreate]):
    """Operations on local DB for Dataset table."""

    @sync_wrapper(DatasetLocalOperations.load)
    def load(self, *args: Any, **kwargs: Any) -> models.Dataset:
        return cast(DatasetLocalOperations, self.async_ops).load(*args, **kwargs)  # type: ignore

    @sync_wrapper(DatasetLocalOperations.read_slice)
    def read_slice(self, *args: Any, **kwargs: Any) -> dict[str, np.ndarray]:
        return cast(DatasetLocalOperations, self.async_ops).read_slice(*args, **kwargs)  # type: ignore


class DatasetAssocSyncOperations(
    SyncOperations[db.DatasetAssoc, models.DatasetAssoc, models.DatasetAssocCreate]
):
    """Operations on local DB for DatasetAssoc table."""


class EstimatesSyncOperations(SyncOperations[db.Estimates, models.Estimates, models.EstimatesCreate]):
    """Operations on local DB for Estimates table."""

    @sync_wrapper(EstimatesLocalOperations.load)
    def load(self, *args: Any, **kwargs: Any) -> models.Estimates:
        return cast(EstimatesLocalOperations, self.async_ops).load(*args, **kwargs)  # type: ignore

    @sync_wrapper(EstimatesLocalOperations.read_slice)
    def read_slice(self, *args: Any, **kwargs: Any) -> qp.Ensemble:
        return cast(EstimatesLocalOperations, self.async_ops).read_slice(*args, **kwargs)


class EstimatorSyncOperations(SyncOperations[db.Estimator, models.Estimator, models.EstimatorCreate]):
    """Operations on local DB for Estimator table."""


class ModelSyncOperations(SyncOperations[db.Model, models.Model, models.ModelCreate]):
    """Operations on local DB for Model table."""

    @sync_wrapper(ModelLocalOperations.load)
    def load(self, *args: Any, **kwargs: Any) -> models.Model:
        return cast(ModelLocalOperations, self.async_ops).load(*args, **kwargs)  # type: ignore


class FilterABSyncOperations(SyncOperations[db.FilterAB, models.FilterAB, models.FilterABCreate]):
    """Operations on local DB for FilterAB table."""


class SedSyncOperations(SyncOperations[db.Sed, models.Sed, models.SedCreate]):
    """Operations on local DB for Sed table."""
