"""Shared CLI command factories for load, read_slice, and download operations.

These factories generate Click commands that are identical in structure but
operate on different entity types (dataset, estimates, model) and backends
(local or remote).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from ..common import LoadType
from ..models.utils import OutputEnum, output_pydantic
from . import common_options

logger = logging.getLogger(__name__)


def _parse_load_input(from_json: str | None, fields: tuple[str, ...]) -> dict[str, Any]:
    """Parse input for load commands — either from JSON file or KEY=VALUE pairs."""
    if from_json:
        try:
            with open(from_json, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            click.echo(f"Error: Invalid JSON: {exc}", err=True)
            raise click.Abort()
        except OSError as exc:
            click.echo(f"Error: Cannot read file: {exc}", err=True)
            raise click.Abort()

    row_data: dict[str, Any] = {}
    for field in fields:
        if "=" not in field:
            click.echo(f"Error: Invalid field format '{field}'. Use KEY=VALUE format.", err=True)
            raise click.Abort()

        key, value = field.split("=", 1)
        try:
            row_data[key] = json.loads(value)
        except json.JSONDecodeError:
            row_data[key] = value

    return row_data


def make_load_command(
    group: click.Group,
    entity_name: str,
    ops_getter: Callable[[], Any],
    error_handler: Callable[[Exception, str], None],
    *,
    init_hook: Callable[[], None] | None = None,
) -> None:
    """Register a 'load' command on the given Click group."""

    @group.command(name="load")
    @common_options.path()
    @common_options.load_type()
    @common_options.output()
    @click.option("--from-json", type=click.Path(exists=True), help="Path to JSON file containing row data")
    @click.option("--no-validate", is_flag=True, help="Skip Pydantic validation")
    @click.argument("fields", nargs=-1)
    def load(
        path: Path | str,
        load_type: LoadType,
        output: OutputEnum,
        from_json: str | None,
        *,
        no_validate: bool,
        fields: tuple[str, ...],
    ) -> None:
        if init_hook:
            init_hook()

        row_data = _parse_load_input(from_json, fields)
        ops = ops_getter()

        try:
            row = ops.load(
                path=path,
                load_type=load_type,
                validate=not no_validate,
                **row_data,
            )
            click.echo(f"Successfully loaded {entity_name} from {path}")
            print(output_pydantic([row], output, ops.ctx.response_class.col_names_for_table))
        except Exception as exc:
            logger.error(f"Error loading {entity_name}", exc_info=True)
            click.echo(f"Error loading {entity_name}: {exc}", err=True)
            raise click.Abort()


def make_read_slice_command(
    group: click.Group,
    entity_name: str,
    ops_getter: Callable[[], Any],
    error_handler: Callable[[Exception, str], None],
    *,
    init_hook: Callable[[], None] | None = None,
    output_json: bool = True,
) -> None:
    """Register a 'read-slice' command on the given Click group."""

    @group.command(name="read-slice")
    @common_options.slice_option()
    @common_options.output()
    @click.argument("row_id", type=int)
    def read_slice(
        row_id: int,
        output: OutputEnum,
        slice_option: slice | None,
    ) -> None:
        if init_hook:
            init_hook()

        ops = ops_getter()
        try:
            data = ops.read_slice(row_id=row_id, the_slice=slice_option)
            if output == OutputEnum.json:
                click.echo(json.dumps(data, indent=2, default=str))
            else:
                click.echo(data)
        except Exception as exc:
            logger.error(f"Error reading slice from {entity_name} {row_id}", exc_info=True)
            click.echo(f"Error reading slice from {entity_name}: {exc}", err=True)
            raise click.Abort()


def make_download_command(
    group: click.Group,
    entity_name: str,
    ops_getter: Callable[[], Any],
    error_handler: Callable[[Exception, str], None],
) -> None:
    """Register a 'download' command on the given Click group."""

    @group.command(name="download")
    @click.argument("row_id", type=int)
    @click.option("--output-path", type=click.Path(), help="Optional output path for downloaded file")
    def download(
        row_id: int,
        output_path: str | None,
    ) -> None:
        ops = ops_getter()
        try:
            file_path = ops.download(row_id=row_id, output_path=output_path)
            click.echo(f"Successfully downloaded {entity_name} {row_id} to {file_path}")
        except Exception as exc:
            logger.error(f"Error downloading {entity_name} {row_id}", exc_info=True)
            click.echo(f"Error downloading {entity_name}: {exc}", err=True)
            raise click.Abort()
