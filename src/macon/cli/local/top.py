"""CLI entry point for rail-svc-client."""

import asyncio
from typing import TypeVar

import click
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema

from ... import __version__, db
from ...config import config
from ...db.base import Base
from .test_classes import test_named_group, test_ref_group, test_list_pair_group

T = TypeVar("T", bound=Base)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
CreateT = TypeVar("CreateT", bound=BaseModel)


@click.command(name="init")
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
def init(*, reset: bool) -> None:
    """Initialize the DB"""

    def _init_db_sync() -> None:  # pragma: no cover
        """Synchronous wrapper for async init."""

        async def _init_db() -> None:
            engine = create_async_engine(config.db.url)
            try:
                conn = engine.connect()
            except Exception as msg:
                await engine.dispose()
                raise RuntimeError(f"{msg}") from msg
            try:
                await conn.start()

                if db.Base.metadata.schema is not None:
                    await conn.execute(CreateSchema(db.Base.metadata.schema, if_not_exists=True))
                if reset:
                    await conn.run_sync(db.Base.metadata.drop_all)
                await conn.run_sync(db.Base.metadata.create_all)
            except Exception as msg:
                await conn.rollback()
                await conn.close()
                await engine.dispose()
                raise RuntimeError(f"{msg}") from msg

            await conn.close()
            await engine.dispose()

        asyncio.run(_init_db())

    _init_db_sync()


@click.group(name="macon-local", commands=[init] + [test_named_group, test_ref_group, test_list_pair_group])
@click.version_option(version=__version__)
def cli() -> None:
    """Administrative CLI for rail-svc."""


if __name__ == "__main__":
    cli()
