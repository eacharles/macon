from __future__ import annotations

import logging
from types import TracebackType
from typing import Final

from pydantic import BaseModel

from .. import models
from .base import (
    RemoteAPI,
    RemoteTableOperations,
)

# Configure logging
logger = logging.getLogger(__name__)


# Define table configuration with optional custom client class
TABLE_CONFIGS: Final[
    dict[str, tuple[type[BaseModel], type[BaseModel], type[RemoteTableOperations] | None]]
] = {
    "test_named": (models.TestNamed, models.TestNamedCreate, None),
    "test_ref": (models.TestRef, models.TestRefCreate, None),
    "test_list_pair": (models.TestListPair, models.TestListPairCreate, None),
    
}


class RemoteDatabase:
    """High-level interface providing access to all table clients."""

    def __init__(
        self,
        base_url: str,
        api_prefix: str = "/api/v1",
        timeout: float = 30.0,
        auth_token: str | None = None,
    ):
        self.base_url = base_url
        self.api_prefix = api_prefix
        self.timeout = timeout
        self.auth_token = auth_token
        self._api: RemoteAPI | None = None

        # Type hints for specialized clients
        self.datasets: RemoteDatasetOperations
        self.estimates: RemoteEstimatesOperations
        self.models: RemoteModelOperations
        self.funcs: RemoteFuncsOperations

    async def __aenter__(self) -> RemoteDatabase:
        self._api = RemoteAPI(
            base_url=self.base_url,
            api_prefix=self.api_prefix,
            timeout=self.timeout,
            auth_token=self.auth_token,
        )
        await self._api.__aenter__()
        self._setup_clients()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._api:
            await self._api.__aexit__(exc_type, exc_val, exc_tb)

    def _setup_clients(self) -> None:
        """Setup all table clients dynamically."""
        assert self._api is not None, "API not initialized"

        for table_name, (response_model, create_model, custom_class) in TABLE_CONFIGS.items():
            if custom_class:
                # Use custom client class
                endpoint = f"{self.base_url}{self.api_prefix}/{table_name}"
                assert self._api.client
                client = custom_class(
                    client=self._api.client,
                    endpoint=endpoint,
                    response_model=response_model,
                    create_model=create_model,
                )
            else:
                # Use standard client
                client = self._api.table(table_name, response_model, create_model)

            setattr(self, table_name, client)

        # Setup funcs client
        funcs_endpoint = f"{self.base_url}{self.api_prefix}/funcs"
        assert self._api.client
        self.funcs = RemoteFuncsOperations(
            client=self._api.client,
            endpoint=funcs_endpoint,
        )

    def list_tables(self) -> list[str]:
        """List all available table names."""
        return list(TABLE_CONFIGS.keys())

    def get_client(self, table_name: str) -> RemoteTableOperations | None:
        """Get a client by table name."""
        return getattr(self, table_name, None)
