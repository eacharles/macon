from __future__ import annotations

import json
import logging
from typing import Any, TypeVar, cast

import click
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError

from ...common import unexpected
from ...db.base import Base
from ...db.session import init_db
from ...local_sync.base import SyncOperations
from ...models import Filter, FilterOp, OrderBy
from ...models.utils import OutputEnum, output_pydantic
from .. import common_options

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar("T", bound=Base)
ResponseT = TypeVar("ResponseT", bound=BaseModel)
CreateT = TypeVar("CreateT", bound=BaseModel)


def handle_database_error(exc: Exception, context: str = "") -> None:
    """Handle common database errors with appropriate messages.

    Parameters
    ----------
    exc
        Exception that was raised
    context
        Additional context about when the error occurred

    Raises
    ------
    click.Abort
        Always raises to terminate command
    """
    context_msg = f" {context}" if context else ""

    if isinstance(exc, ValidationError):
        click.echo(f"Error: Validation failed{context_msg}: {exc}", err=True)
    elif isinstance(exc, IntegrityError):
        logger.error(
            "Integrity constraint violation",
        )
        click.echo(
            f"Error: Integrity constraint violation{context_msg} (duplicate key, foreign key, etc.): {exc}",
            err=True,
        )
    elif isinstance(exc, ValueError):
        click.echo(f"Error{context_msg}: {exc}", err=True)
    else:
        logger.error(
            "Unexpected error",
        )
        click.echo(f"Error{context_msg}: {exc}", err=True)

    raise click.Abort()


class CliOperations[T: Base, ResponseT: BaseModel, CreateT: BaseModel]:
    """Base class for CLI operations on database tables.

    Provides common functionality for Click commands that interact
    with database tables through LocalOperations. Uses synchronous
    wrappers appropriate for CLI contexts.

    Parameters
    ----------
    operations
        Table operations instance for database access
    group
        Click command group to register commands to

    Examples
    --------
    >>> @click.group()
    >>> def cli():
    ...     pass
    >>>
    >>> from rail_svc.local import algorithm
    >>> algo_cli = CliOperations(algorithm, cli)
    >>> algo_cli.register_all_read_commands()
    """

    def __init__(
        self,
        sync_oper: SyncOperations[T, ResponseT, CreateT],
        group: click.Group,
    ) -> None:
        self.sync_oper = sync_oper
        self.ctx = sync_oper.async_ops._table_ops.ctx
        self.group = group
        self.col_names_for_table = self.ctx.response_class.col_names_for_table  # type: ignore

    # ========================================================================
    # READ COMMAND REGISTRATION
    # ========================================================================

    def register_get_row(self) -> None:
        """Register the get-row command to the group.

        Adds a Click command that retrieves a single row by ID.
        """

        @self.group.command(name="get-row", help=f"Get a single {self.ctx.class_string} by ID")
        @common_options.output()
        @click.argument("row_id", type=int)
        def command(
            output: OutputEnum,
            row_id: int,
        ) -> None:
            """Get a single row by ID."""

            # Ensure database engine is initialized
            init_db()

            try:
                row = self.sync_oper.get_row(row_id=row_id)
                print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as exc:
                handle_database_error(exc, f"getting {self.ctx.class_string} with ID {row_id}")

    def register_get_row_by_name(self) -> None:
        """Register the get-row-by-name command to the group.

        Adds a Click command that retrieves a single row by name.
        """

        @self.group.command(name="get-by-name", help=f"Get a single {self.ctx.class_string} by name")
        @common_options.output()
        @click.argument("name", type=str)
        def command(
            output: OutputEnum,
            name: str,
        ) -> None:
            """Get a single row by name."""

            # Ensure database engine is initialized
            init_db()

            try:
                row = self.sync_oper.get_row_by_name(name=name)
                print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"getting {self.ctx.class_string} with name '{name}'")

    def register_get_rows(self) -> None:
        """Register the get-rows command to the group.

        Adds a Click command that retrieves and displays rows from the table
        with pagination support and multiple output formats.
        """

        @self.group.command(name="get-rows", help=f"List {self.ctx.class_string} rows")
        @common_options.output()
        @common_options.skip()
        @common_options.limit()
        @common_options.page_size()
        def command(
            output: OutputEnum,
            skip: int,
            limit: int | None,
            page_size: int,
        ) -> None:
            """List rows from the table with pagination."""

            # Ensure database engine is initialized
            init_db()

            # Validate pagination parameters
            try:
                params = common_options.PaginationParams(skip=skip, limit=limit, page_size=page_size)
                params.validate()
            except ValueError as exc:
                click.echo(f"Error: {exc}", err=True)
                raise click.Abort()

            # Retrieve and display rows
            try:
                rows = self.sync_oper.get_rows(
                    skip=skip,
                    limit=limit or page_size,
                )
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"listing {self.ctx.class_string} rows")

    def register_get_row_or_none(self) -> None:
        """Register the get-row-or-none command to the group.

        Adds a Click command that retrieves a single row by ID,
        returning nothing if not found instead of erroring.
        """

        @self.group.command(
            name="get-row-if-exists",
            help=f"Get a {self.ctx.class_string} by ID (returns nothing if not found)",
        )
        @common_options.output()
        @click.argument("row_id", type=int)
        def command(
            output: OutputEnum,
            row_id: int,
        ) -> None:
            """Get a single row by ID, or nothing if not found."""

            # Ensure database engine is initialized
            init_db()

            try:
                row = self.sync_oper.get_row_or_none(row_id=row_id)
                if row is None:
                    click.echo(f"No {self.ctx.class_string} found with ID {row_id}")
                else:
                    print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"getting {self.ctx.class_string} with ID {row_id}")

    def register_count_rows(self) -> None:
        """Register the count-rows command to the group.

        Adds a Click command that counts total rows in the table.
        """

        @self.group.command(name="count", help=f"Count total {self.ctx.class_string} rows")
        def command() -> None:
            """Count total rows in the table."""

            # Ensure database engine is initialized
            init_db()

            try:
                count = self.sync_oper.count_rows()
                click.echo(f"Total {self.ctx.class_string} rows: {count}")

            except Exception as uexc:
                handle_database_error(uexc, f"counting {self.ctx.class_string} rows")

    def register_lookup_by_id_or_name(self) -> None:
        """Register the lookup command to the group.

        Adds a Click command that looks up a row by either ID or name.
        """

        @self.group.command(name="lookup", help=f"Look up a {self.ctx.class_string} by ID or name")
        @common_options.output()
        @click.option("--id", "row_id", type=int, help="Row ID to look up")
        @click.option("--name", type=str, help="Row name to look up")
        def command(
            output: OutputEnum,
            row_id: int | None,
            name: str | None,
        ) -> None:
            """Look up a row by either ID or name."""

            # Ensure database engine is initialized
            init_db()

            # Validate that exactly one is provided
            if (row_id is None) == (name is None):
                click.echo("Error: Provide exactly one of --id or --name", err=True)
                raise click.Abort()

            try:
                row = self.sync_oper.lookup_by_id_or_name(row_id=row_id, name=name)
                print(output_pydantic([cast(ResponseT, row)], output, self.col_names_for_table))

            except Exception as uexc:
                identifier = f"ID {row_id}" if row_id else f"name '{name}'"
                handle_database_error(uexc, f"looking up {self.ctx.class_string} with {identifier}")

    def register_all_read_commands(self) -> None:
        """Register all read commands to the group.

        Convenience method to register all available read operations
        at once.
        """
        self.register_get_row()
        self.register_get_row_by_name()
        self.register_get_rows()
        self.register_get_row_or_none()
        self.register_count_rows()
        self.register_lookup_by_id_or_name()

    # ========================================================================
    # CREATE COMMAND REGISTRATION
    # ========================================================================

    def register_create_row(self) -> None:
        """Register the create-row command to the group.

        Adds a Click command that creates a single row from command-line arguments
        or JSON file.
        """

        @self.group.command(name="create", help=f"Create a new {self.ctx.class_string}")
        @common_options.output()
        @click.option(
            "--from-json", type=click.Path(exists=True), help="Path to JSON file containing row data"
        )
        @click.option("--no-validate", is_flag=True, help="Skip Pydantic validation")
        @click.argument("fields", nargs=-1)
        def command(
            output: OutputEnum,
            from_json: str | None,
            *,
            no_validate: bool,
            fields: tuple[str, ...],
        ) -> None:
            """Create a single row.

            Provide fields as KEY=VALUE pairs, e.g.:
            create name=MyName class_name=MyClass active=true

            Or use --from-json to load from a file.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse input
            if from_json:
                try:
                    with open(from_json, encoding="utf-8") as f:
                        row_data = json.load(f)
                except json.JSONDecodeError as uexc:
                    click.echo(f"Error: Invalid JSON: {uexc}", err=True)
                    raise click.Abort()
                except OSError as uexc:
                    click.echo(f"Error: Cannot read file: {uexc}", err=True)
                    raise click.Abort()
            else:
                # Parse KEY=VALUE arguments
                row_data = {}
                for field in fields:
                    if "=" not in field:
                        click.echo(f"Error: Invalid field format '{field}'. Use KEY=VALUE format.", err=True)
                        raise click.Abort()

                    key, value = field.split("=", 1)
                    # Try to parse as JSON for complex types
                    try:
                        row_data[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # Keep as string if not valid JSON
                        row_data[key] = value

            if not row_data:
                click.echo("Error: No data provided. Use KEY=VALUE arguments or --from-json", err=True)
                raise click.Abort()

            try:
                row = self.sync_oper.create_row(validate=not no_validate, **row_data)
                click.echo(f"Created {self.ctx.class_string} successfully")
                print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as exc:
                handle_database_error(exc, f"creating {self.ctx.class_string}")

    def register_create_rows(self) -> None:
        """Register the create-rows command to the group.

        Adds a Click command that creates multiple rows from a JSON file.
        All rows are created atomically.
        """

        @self.group.command(
            name="create-many", help=f"Create multiple {self.ctx.class_string} rows from JSON file"
        )
        @common_options.output()
        @click.option("--no-validate", is_flag=True, help="Skip Pydantic validation")
        @click.argument("json_file", type=click.Path(exists=True))
        def command(
            output: OutputEnum,
            *,
            no_validate: bool,
            json_file: str,
        ) -> None:
            """Create multiple rows from JSON file.

            JSON file should contain an array of objects.
            All rows are created atomically - if any fails, none are created.
            """

            # Ensure database engine is initialized
            init_db()

            # Load JSON file
            try:
                with open(json_file, encoding="utf-8") as f:
                    rows_data = json.load(f)
            except json.JSONDecodeError as exc:
                click.echo(f"Error: Invalid JSON: {exc}", err=True)
                raise click.Abort()
            except OSError as uexc:
                click.echo(f"Error: Cannot read file: {uexc}", err=True)
                raise click.Abort()

            if not isinstance(rows_data, list):
                click.echo("Error: JSON file must contain an array", err=True)
                raise click.Abort()

            if unexpected(not rows_data):
                click.echo("Error: Array is empty", err=True)
                raise click.Abort()

            try:
                rows = self.sync_oper.create_rows(rows_data=rows_data, validate=not no_validate)
                click.echo(f"Successfully created {len(rows)} {self.ctx.class_string} rows")
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"creating {self.ctx.class_string} rows")

    def register_create_rows_batched(self) -> None:
        """Register the create-rows-batched command to the group.

        Adds a Click command that creates multiple rows in batches from a JSON file.
        Allows partial success if later batches fail.
        """

        @self.group.command(
            name="create-batched", help=f"Create multiple {self.ctx.class_string} rows in batches"
        )
        @common_options.output()
        @click.option("--batch-size", type=int, default=1000, help="Number of rows per batch (default: 1000)")
        @click.option("--no-validate", is_flag=True, help="Skip Pydantic validation")
        @click.argument("json_file", type=click.Path(exists=True))
        def command(
            output: OutputEnum,
            batch_size: int,
            *,
            no_validate: bool,
            json_file: str,
        ) -> None:
            """Create multiple rows in batches from JSON file.

            JSON file should contain an array of objects.
            Rows are committed in batches - if a batch fails,
            previously committed batches remain in the database.
            """

            # Ensure database engine is initialized
            init_db()

            # Validate batch size
            if batch_size < 1:
                click.echo("Error: Batch size must be at least 1", err=True)
                raise click.Abort()

            # Load JSON file
            try:
                with open(json_file, encoding="utf-8") as f:
                    rows_data = json.load(f)
            except json.JSONDecodeError as uexc:
                click.echo(f"Error: Invalid JSON: {uexc}", err=True)
                raise click.Abort()
            except OSError as uexc:
                click.echo(f"Error: Cannot read file: {uexc}", err=True)
                raise click.Abort()

            if unexpected(not isinstance(rows_data, list)):
                click.echo("Error: JSON file must contain an array", err=True)
                raise click.Abort()

            if unexpected(not rows_data):
                click.echo("Error: Array is empty", err=True)
                raise click.Abort()

            try:
                rows = self.sync_oper.create_rows_batched(
                    rows_data=rows_data, validate=not no_validate, batch_size=batch_size
                )
                click.echo(
                    f"Successfully created {len(rows)} {self.ctx.class_string} rows "
                    f"in batches of {batch_size}"
                )
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"creating {self.ctx.class_string} rows in batches")

    def register_bulk_insert_rows(self) -> None:
        """Register the bulk-insert command to the group.

        Adds a Click command that performs high-performance bulk insert from JSON file.
        Does not return created objects.
        """

        @self.group.command(
            name="bulk-insert", help=f"Bulk insert {self.ctx.class_string} rows (fast, no objects returned)"
        )
        @click.option("--no-validate", is_flag=True, help="Skip Pydantic validation")
        @click.argument("json_file", type=click.Path(exists=True))
        def command(
            *,
            no_validate: bool,
            json_file: str,
        ) -> None:
            """Bulk insert rows from JSON file (high performance).

            JSON file should contain an array of objects.
            This is much faster than create-many but does not return
            created objects or call hooks.
            """

            # Ensure database engine is initialized
            init_db()

            # Load JSON file
            try:
                with open(json_file, encoding="utf-8") as f:
                    rows_data = json.load(f)
            except json.JSONDecodeError as uexc:
                click.echo(f"Error: Invalid JSON: {uexc}", err=True)
                raise click.Abort()
            except OSError as uexc:
                click.echo(f"Error: Cannot read file: {uexc}", err=True)
                raise click.Abort()

            if unexpected(not isinstance(rows_data, list)):
                click.echo("Error: JSON file must contain an array", err=True)
                raise click.Abort()

            if unexpected(not rows_data):
                click.echo("Error: Array is empty", err=True)
                raise click.Abort()

            try:
                count = self.sync_oper.bulk_insert_rows(rows_data=rows_data, validate=not no_validate)
                click.echo(f"Successfully inserted {count} {self.ctx.class_string} rows")

            except Exception as uexc:
                handle_database_error(uexc, f"bulk inserting {self.ctx.class_string} rows")

    def register_all_create_commands(self) -> None:
        """Register all create commands to the group.

        Convenience method to register all available create operations
        at once.
        """
        self.register_create_row()
        self.register_create_rows()
        self.register_create_rows_batched()
        self.register_bulk_insert_rows()

    # ========================================================================
    # UPDATE COMMAND REGISTRATION
    # ========================================================================

    def register_update_row(self) -> None:
        """Register the update-row command to the group.

        Adds a Click command that updates a single row by ID.
        """

        @self.group.command(name="update", help=f"Update a {self.ctx.class_string} by ID")
        @common_options.output()
        @click.option(
            "--from-json", type=click.Path(exists=True), help="Path to JSON file containing update data"
        )
        @click.argument("row_id", type=int)
        @click.argument("fields", nargs=-1)
        def command(
            output: OutputEnum,
            from_json: str | None,
            row_id: int,
            fields: tuple[str, ...],
        ) -> None:
            """Update a single row by ID.

            Provide fields to update as KEY=VALUE pairs, e.g.:
            update 123 name=NewName active=false

            Or use --from-json to load update data from a file.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse input
            if from_json:
                try:
                    with open(from_json, encoding="utf-8") as f:
                        update_data = json.load(f)
                except json.JSONDecodeError as uexc:
                    click.echo(f"Error: Invalid JSON: {uexc}", err=True)
                    raise click.Abort()
                except OSError as uexc:
                    click.echo(f"Error: Cannot read file: {uexc}", err=True)
                    raise click.Abort()
            else:
                # Parse KEY=VALUE arguments
                update_data = {}
                for field in fields:
                    if unexpected("=" not in field):
                        click.echo(f"Error: Invalid field format '{field}'. Use KEY=VALUE format.", err=True)
                        raise click.Abort()

                    key, value = field.split("=", 1)
                    # Try to parse as JSON for complex types
                    try:
                        update_data[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # Keep as string if not valid JSON
                        update_data[key] = value

            if not update_data:
                click.echo("Error: No update data provided. Use KEY=VALUE arguments or --from-json", err=True)
                raise click.Abort()

            # Prevent ID changes
            if "id" in update_data and update_data["id"] != row_id:
                click.echo(f"Error: Cannot change row ID from {row_id} to {update_data['id']}", err=True)
                raise click.Abort()

            try:
                row = self.sync_oper.update_row(row_id=row_id, **update_data)
                click.echo(f"Successfully updated {self.ctx.class_string} with ID {row_id}")
                print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as exc:
                handle_database_error(exc, f"updating {self.ctx.class_string} with ID {row_id}")

    def register_update_rows(self) -> None:
        """Register the update-rows command to the group.

        Adds a Click command that updates multiple rows from a JSON file.
        All updates are performed atomically.
        """

        @self.group.command(
            name="update-many", help=f"Update multiple {self.ctx.class_string} rows from JSON file"
        )
        @common_options.output()
        @click.argument("json_file", type=click.Path(exists=True))
        def command(
            output: OutputEnum,
            json_file: str,
        ) -> None:
            """Update multiple rows from JSON file.

            JSON file should contain an array of objects, each with an 'id' field
            and the fields to update.

            All rows are updated atomically - if any fails, none are updated.

            Example JSON:
            [
              {"id": 1, "name": "NewName1", "active": true},
              {"id": 2, "name": "NewName2", "active": false}
            ]
            """

            # Ensure database engine is initialized
            init_db()

            # Load JSON file
            try:
                with open(json_file, encoding="utf-8") as f:
                    updates = json.load(f)
            except json.JSONDecodeError as uexc:
                click.echo(f"Error: Invalid JSON: {uexc}", err=True)
                raise click.Abort()
            except OSError as uexc:
                click.echo(f"Error: Cannot read file: {uexc}", err=True)
                raise click.Abort()

            if unexpected(not isinstance(updates, list)):
                click.echo("Error: JSON file must contain an array", err=True)
                raise click.Abort()

            if unexpected(not updates):
                click.echo("Error: Array is empty", err=True)
                raise click.Abort()

            # Validate each update has an 'id' field
            for idx, update in enumerate(updates):
                if not isinstance(update, dict):
                    click.echo(f"Error: Update at index {idx} is not an object", err=True)
                    raise click.Abort()
                if "id" not in update:
                    click.echo(f"Error: Update at index {idx} is missing 'id' field", err=True)
                    raise click.Abort()

            try:
                rows = self.sync_oper.update_rows(updates=updates)
                click.echo(f"Successfully updated {len(rows)} {self.ctx.class_string} rows")
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"updating {self.ctx.class_string} rows")

    def register_all_update_commands(self) -> None:
        """Register all update commands to the group.

        Convenience method to register all available update operations
        at once.
        """
        self.register_update_row()
        self.register_update_rows()

    # ========================================================================
    # DELETE COMMAND REGISTRATION
    # ========================================================================

    def register_delete_row(self) -> None:
        """Register the delete-row command to the group.

        Adds a Click command that deletes a single row by ID.
        """

        @self.group.command(name="delete", help=f"Delete a {self.ctx.class_string} by ID")
        @common_options.output()
        @click.option("--no-capture", is_flag=True, help="Do not capture deleted row data (faster)")
        @click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
        @click.argument("row_id", type=int)
        def command(
            output: OutputEnum,
            *,
            no_capture: bool,
            confirm: bool,
            row_id: int,
        ) -> None:
            """Delete a single row by ID.

            This operation calls pre and post-delete hooks and is atomic.
            Use --no-capture to skip capturing deleted data (faster).
            """

            # Ensure database engine is initialized
            init_db()

            # Confirmation prompt unless --confirm flag
            if not confirm:
                if not click.confirm(
                    f"Are you sure you want to delete {self.ctx.class_string} with ID {row_id}?"
                ):
                    click.echo("Deletion cancelled")
                    return

            try:
                deleted_data = self.sync_oper.delete_row(row_id=row_id, capture_data=not no_capture)

                click.echo(f"Successfully deleted {self.ctx.class_string} with ID {row_id}")

                if deleted_data and not no_capture:
                    click.echo("\nDeleted data:")
                    # Convert dict to list for output_pydantic compatibility
                    print(
                        output_pydantic(
                            [self.ctx.response_class(**deleted_data)],
                            output,
                            self.col_names_for_table,
                        )
                    )

            except Exception as uexc:
                handle_database_error(uexc, f"deleting {self.ctx.class_string} with ID {row_id}")

    def register_delete_rows(self) -> None:
        """Register the delete-rows command to the group.

        Adds a Click command that deletes multiple rows by IDs.
        All deletions are performed atomically.
        """

        @self.group.command(name="delete-many", help=f"Delete multiple {self.ctx.class_string} rows by IDs")
        @common_options.output()
        @click.option("--capture-data", is_flag=True, help="Capture deleted row data (slower)")
        @click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
        @click.option(
            "--from-file",
            type=click.Path(exists=True),
            help="Path to file containing row IDs (one per line or JSON array)",
        )
        @click.argument("row_ids", nargs=-1, type=int)
        def command(
            output: OutputEnum,
            *,
            capture_data: bool,
            confirm: bool,
            from_file: str | None,
            row_ids: tuple[int, ...],
        ) -> None:
            """Delete multiple rows by IDs.

            Provide IDs as arguments:
                delete-many 1 2 3 4 5

            Or use --from-file with a text file (one ID per line):
                delete-many --from-file ids.txt

            Or use --from-file with a JSON file:
                delete-many --from-file ids.json

            All rows are deleted atomically - if any fails, none are deleted.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse input
            if from_file:
                try:
                    with open(from_file, encoding="utf-8") as f:
                        content = f.read().strip()

                    # Try JSON first
                    try:
                        ids_list = json.loads(content)
                        if unexpected(not isinstance(ids_list, list)):
                            raise ValueError("JSON must be an array")
                    except json.JSONDecodeError:
                        # Parse as line-separated IDs
                        ids_list = [int(line.strip()) for line in content.split("\n") if line.strip()]

                except (OSError, ValueError) as uexc:
                    click.echo(f"Error reading file: {uexc}", err=True)
                    raise click.Abort()
            else:
                ids_list = list(row_ids)

            if not ids_list:
                click.echo("Error: No IDs provided. Use arguments or --from-file", err=True)
                raise click.Abort()

            # Confirmation prompt unless --confirm flag
            if not confirm:
                if not click.confirm(
                    f"Are you sure you want to delete {len(ids_list)} {self.ctx.class_string} rows?"
                ):
                    click.echo("Deletion cancelled")
                    return

            try:
                deleted_data = self.sync_oper.delete_rows(row_ids=ids_list, capture_data=capture_data)

                click.echo(f"Successfully deleted {len(ids_list)} {self.ctx.class_string} rows")

                if deleted_data and capture_data:
                    click.echo("\nDeleted data:")
                    print(
                        output_pydantic(
                            [self.ctx.response_class(**del_d) for del_d in deleted_data],
                            output,
                            self.col_names_for_table,
                        )
                    )

            except Exception as uexc:
                handle_database_error(uexc, f"deleting {len(ids_list)} {self.ctx.class_string} rows")

    def register_bulk_delete_rows(self) -> None:
        """Register the bulk-delete command to the group.

        Adds a Click command that performs high-performance bulk deletion.
        Does not call hooks or capture deleted data.
        """

        @self.group.command(
            name="bulk-delete", help=f"Bulk delete {self.ctx.class_string} rows (fast, no hooks)"
        )
        @click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
        @click.option(
            "--from-file",
            type=click.Path(exists=True),
            help="Path to file containing row IDs (one per line or JSON array)",
        )
        @click.argument("row_ids", nargs=-1, type=int)
        def command(
            *,
            confirm: bool,
            from_file: str | None,
            row_ids: tuple[int, ...],
        ) -> None:
            """Bulk delete rows by IDs (high performance).

            Provide IDs as arguments:
                bulk-delete 1 2 3 4 5

            Or use --from-file with a text file (one ID per line):
                bulk-delete --from-file ids.txt

            Or use --from-file with a JSON file:
                bulk-delete --from-file ids.json

            WARNING: This does not call hooks or return deleted data.
            Use delete-many if you need hooks or deleted data.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse input
            if from_file:
                try:
                    with open(from_file, encoding="utf-8") as f:
                        content = f.read().strip()

                    # Try JSON first
                    try:
                        ids_list = json.loads(content)
                        if not isinstance(ids_list, list):
                            raise ValueError("JSON must be an array")
                    except json.JSONDecodeError:  # pragma: no cover
                        # Parse as line-separated IDs
                        ids_list = [int(line.strip()) for line in content.split("\n") if line.strip()]

                except (OSError, ValueError) as exc:
                    click.echo(f"Error reading file: {exc}", err=True)
                    raise click.Abort()
            else:
                ids_list = list(row_ids)

            if unexpected(not ids_list):
                click.echo("Error: No IDs provided. Use arguments or --from-file", err=True)
                raise click.Abort()

            # Confirmation prompt unless --confirm flag
            if not confirm:
                click.echo(f"WARNING: This will bulk delete {len(ids_list)} rows without calling hooks.")
                if not click.confirm("Are you sure you want to continue?"):
                    click.echo("Deletion cancelled")
                    return

            try:
                count = self.sync_oper.bulk_delete_rows(row_ids=ids_list)

                click.echo(f"Successfully deleted {count} {self.ctx.class_string} rows")

                if count != len(ids_list):
                    click.echo(f"Note: {len(ids_list) - count} IDs were not found", err=True)

            except Exception as uexc:
                handle_database_error(uexc, f"bulk deleting {len(ids_list)} {self.ctx.class_string} rows")

    def register_all_delete_commands(self) -> None:
        """Register all delete commands to the group.

        Convenience method to register all available delete operations
        at once.
        """
        self.register_delete_row()
        self.register_delete_rows()
        self.register_bulk_delete_rows()

    # ========================================================================
    # FILTER COMMAND REGISTRATION
    # ========================================================================

    def register_filter_rows(self) -> None:
        """Register the filter command to the group.

        Adds a Click command that filters rows based on conditions.
        """

        @self.group.command(name="filter", help=f"Filter {self.ctx.class_string} rows by conditions")
        @common_options.output()
        @common_options.skip()
        @common_options.limit()
        @common_options.page_size()
        @click.option(
            "--field",
            "-f",
            multiple=True,
            help="Filter condition: FIELD:OPERATOR:VALUE (e.g., name:eq:MyName, age:gt:18)",
        )
        @click.option("--or", "use_or", is_flag=True, help="Use OR logic for multiple filters (default: AND)")
        @click.option(
            "--order-by", multiple=True, help="Sort by field: FIELD[:desc] (e.g., name, created_at:desc)"
        )
        def command(
            output: OutputEnum,
            skip: int,
            limit: int | None,
            page_size: int,
            field: tuple[str, ...],
            *,
            use_or: bool,
            order_by: tuple[str, ...],
        ) -> None:
            """Filter rows by conditions.

            Filter format: FIELD:OPERATOR:VALUE

            Operators:
              eq    - Equal
              ne    - Not equal
              lt    - Less than
              le    - Less than or equal
              gt    - Greater than
              ge    - Greater than or equal
              like  - SQL LIKE pattern
              in    - In list (comma-separated)

            Examples:
              filter -f name:eq:MyName
              filter -f age:gt:18 -f status:eq:active
              filter -f name:like:%test% --order-by created_at:desc
              filter -f status:in:active,pending --or
            """

            # Ensure database engine is initialized
            init_db()

            # Validate pagination
            try:
                params = common_options.PaginationParams(skip=skip, limit=limit, page_size=page_size)
                params.validate()
            except ValueError as uexc:
                click.echo(f"Error: {uexc}", err=True)
                raise click.Abort()

            # Parse filters
            filters = []
            for filter_spec in field:
                parts = filter_spec.split(":", 2)
                if len(parts) != 3:
                    click.echo(
                        f"Error: Invalid filter format '{filter_spec}'. Use FIELD:OPERATOR:VALUE", err=True
                    )
                    raise click.Abort()

                field_name, op_str, value_str = parts

                # Map operator string to FilterOp
                op_map = {
                    "eq": FilterOp.EQ,
                    "ne": FilterOp.NE,
                    "lt": FilterOp.LT,
                    "le": FilterOp.LE,
                    "gt": FilterOp.GT,
                    "ge": FilterOp.GE,
                    "like": FilterOp.LIKE,
                    "ilike": FilterOp.ILIKE,
                    "in": FilterOp.IN,
                    "not_in": FilterOp.NOT_IN,
                }

                if op_str not in op_map:
                    click.echo(
                        f"Error: Unknown operator '{op_str}'. Valid operators: {', '.join(op_map.keys())}",
                        err=True,
                    )
                    raise click.Abort()

                op = op_map[op_str]

                # Parse value based on operator
                if op in (FilterOp.IN, FilterOp.NOT_IN):
                    # Split comma-separated values
                    value = [v.strip() for v in value_str.split(",")]
                else:
                    # Try to parse as JSON for proper typing
                    try:
                        value = json.loads(value_str)
                    except json.JSONDecodeError:
                        value = [value_str]

                filters.append(Filter(field=field_name, op=op, value=value))

            # Parse order_by
            order_by_list = []
            for order_spec in order_by:
                parts = order_spec.split(":", 1)
                field_name = parts[0]
                descending = len(parts) > 1 and parts[1].lower() == "desc"
                order_by_list.append(OrderBy(field=field_name, descending=descending))

            try:
                rows = self.sync_oper.filter_rows(
                    filters=filters if filters else None,
                    logical_op="or" if use_or else "and",
                    order_by=order_by_list if order_by_list else None,
                    skip=skip,
                    limit=limit or page_size,
                )

                click.echo(f"Found {len(rows)} matching {self.ctx.class_string} rows")
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as exc:
                handle_database_error(exc, f"filtering {self.ctx.class_string} rows")

    def register_count_filtered_rows(self) -> None:
        """Register the count-filtered command to the group.

        Adds a Click command that counts rows matching filter conditions.
        """

        @self.group.command(
            name="count-filtered", help=f"Count {self.ctx.class_string} rows matching conditions"
        )
        @click.option("--field", "-f", multiple=True, help="Filter condition: FIELD:OPERATOR:VALUE")
        @click.option("--or", "use_or", is_flag=True, help="Use OR logic for multiple filters (default: AND)")
        def command(
            field: tuple[str, ...],
            *,
            use_or: bool,
        ) -> None:
            """Count rows matching filter conditions.

            See 'filter' command for filter format details.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse filters (same logic as filter_rows)
            filters = []
            for filter_spec in field:
                parts = filter_spec.split(":", 2)
                if unexpected(len(parts) != 3):
                    click.echo(
                        f"Error: Invalid filter format '{filter_spec}'. Use FIELD:OPERATOR:VALUE", err=True
                    )
                    raise click.Abort()

                field_name, op_str, value_str = parts

                op_map = {
                    "eq": FilterOp.EQ,
                    "ne": FilterOp.NE,
                    "lt": FilterOp.LT,
                    "le": FilterOp.LE,
                    "gt": FilterOp.GT,
                    "ge": FilterOp.GE,
                    "like": FilterOp.LIKE,
                    "in": FilterOp.IN,
                }

                if unexpected(op_str not in op_map):
                    click.echo(f"Error: Unknown operator '{op_str}'", err=True)
                    raise click.Abort()

                op = op_map[op_str]

                if op in (FilterOp.IN, FilterOp.NOT_IN):  # pragma: no cover
                    value = [v.strip() for v in value_str.split(",")]
                else:
                    try:
                        value = json.loads(value_str)
                    except json.JSONDecodeError:
                        value = [value_str]

                filters.append(Filter(field=field_name, op=op, value=value))

            try:
                count = self.sync_oper.count_filtered_rows(
                    filters=filters if filters else None,
                    logical_op="or" if use_or else "and",
                )

                filter_desc = "all" if not filters else "matching"
                click.echo(f"Total {filter_desc} {self.ctx.class_string} rows: {count}")

            except Exception as uexc:
                handle_database_error(uexc, f"counting filtered {self.ctx.class_string} rows")

    def register_find_by(self) -> None:
        """Register the find-by command to the group.

        Adds a Click command for simple equality-based filtering.
        """

        @self.group.command(name="find-by", help=f"Find {self.ctx.class_string} rows by field values")
        @common_options.output()
        @common_options.skip()
        @common_options.limit()
        @common_options.page_size()
        @click.option("--order-by", multiple=True, help="Sort by field: FIELD[:desc]")
        @click.argument("conditions", nargs=-1)
        def command(
            output: OutputEnum,
            skip: int,
            limit: int | None,
            page_size: int,
            order_by: tuple[str, ...],
            conditions: tuple[str, ...],
        ) -> None:
            """Find rows by equality conditions.

            Provide conditions as KEY=VALUE pairs:
              find-by name=MyName status=active

            All conditions must match (AND logic).
            """

            # Ensure database engine is initialized
            init_db()

            # Validate pagination
            try:
                params = common_options.PaginationParams(skip=skip, limit=limit, page_size=page_size)
                params.validate()
            except ValueError as uexc:
                click.echo(f"Error: {uexc}", err=True)
                raise click.Abort()

            # Parse conditions
            kwargs = {}
            for condition in conditions:
                if "=" not in condition:
                    click.echo(f"Error: Invalid condition format '{condition}'. Use KEY=VALUE", err=True)
                    raise click.Abort()

                key, value = condition.split("=", 1)
                try:
                    kwargs[key] = json.loads(value)
                except json.JSONDecodeError:
                    kwargs[key] = value

            if not kwargs:
                click.echo("Error: No conditions provided. Use KEY=VALUE format", err=True)
                raise click.Abort()

            # Parse order_by
            order_by_list = []
            for order_spec in order_by:
                parts = order_spec.split(":", 1)
                field_name = parts[0]
                descending = len(parts) > 1 and parts[1].lower() == "desc"
                order_by_list.append(OrderBy(field=field_name, descending=descending))

            try:
                rows = self.sync_oper.find_by(
                    order_by=order_by_list if order_by_list else None,
                    skip=skip,
                    limit=limit or page_size,
                    **kwargs,
                )

                click.echo(f"Found {len(rows)} matching {self.ctx.class_string} rows")
                print(output_pydantic(rows, output, self.col_names_for_table))

            except Exception as uexc:
                handle_database_error(uexc, f"finding {self.ctx.class_string} rows")

    def register_find_one_by(self) -> None:
        """Register the find-one-by command to the group.

        Adds a Click command to find exactly one row by field values.
        """

        @self.group.command(
            name="find-one-by", help=f"Find exactly one {self.ctx.class_string} by field values"
        )
        @common_options.output()
        @click.argument("conditions", nargs=-1)
        def command(
            output: OutputEnum,
            conditions: tuple[str, ...],
        ) -> None:
            """Find exactly one row by equality conditions.

            Provide conditions as KEY=VALUE pairs:
              find-one-by email=user@example.com

            Raises an error if no rows or multiple rows match.
            """

            # Ensure database engine is initialized
            init_db()

            # Parse conditions
            kwargs = {}
            for condition in conditions:
                if unexpected("=" not in condition):
                    click.echo(f"Error: Invalid condition format '{condition}'. Use KEY=VALUE", err=True)
                    raise click.Abort()

                key, value = condition.split("=", 1)
                try:
                    kwargs[key] = json.loads(value)
                except json.JSONDecodeError:
                    kwargs[key] = value

            if not kwargs:
                click.echo("Error: No conditions provided. Use KEY=VALUE format", err=True)
                raise click.Abort()

            try:
                row = self.sync_oper.find_one_by(**kwargs)
                print(output_pydantic([row], output, self.col_names_for_table))

            except Exception as exc:
                handle_database_error(exc, f"finding {self.ctx.class_string}")

    def register_all_filter_commands(self) -> None:
        """Register all filter commands to the group.

        Convenience method to register all available filter operations
        at once.
        """
        self.register_filter_rows()
        self.register_count_filtered_rows()
        self.register_find_by()
        self.register_find_one_by()


def make_table_group(name: str, ops: Any, desc: str) -> click.Group:
    """Create table CLI group with all commands."""

    @click.group(name=name, help=desc)
    def grp() -> None:  # pragma: no cover
        pass

    cli_ops = CliOperations(ops, grp)
    cli_ops.register_all_create_commands()
    cli_ops.register_all_read_commands()
    cli_ops.register_all_update_commands()
    cli_ops.register_all_delete_commands()
    cli_ops.register_all_filter_commands()
    return grp
