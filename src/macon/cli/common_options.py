"""Common options for pz-rail-service CLIs"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any

import click
from click.decorators import FC

from ..common import LoadType, unexpected, str_to_slice
from ..config import config as global_config
from ..models.utils import OutputEnum

# Configuration defaults
DEFAULT_PAGE_SIZE = global_config.web_interface.default_page_size
MAX_PAGE_SIZE = global_config.web_interface.max_page_size
DEFAULT_BATCH_SIZE = global_config.web_interface.default_batch_size
MAX_BATCH_SIZE = global_config.web_interface.max_batch_size
DEFAULT_TIMEOUT = global_config.web_interface.default_timeout
STREAM_TIMEOUT = global_config.web_interface.stream_timeout


def validate_non_empty(_ctx: click.Context, param: click.Parameter, value: str) -> str:  # pragma: no cover
    """
    Click callback to validate non-empty string.

    Parameters
    ----------
    _ctx
        Click context
    param
        Click parameter
    value
        Parameter value

    Returns
    -------
        The value if valid

    Raises
    ------
    click.BadParameter
        If value is empty
    """
    if not value or not value.strip():
        raise click.BadParameter(f"{param.name} cannot be empty")
    return value


def parse_slice(_ctx: click.Context, _param: click.Parameter, value: str | None) -> slice | None:
    """Parse a string into a Python slice object.

    Accepts formats like:
    - "5" -> slice(5, None, None)
    - "1:5" -> slice(1, 5, None)
    - "1:10:2" -> slice(1, 10, 2)
    - ":5" -> slice(None, 5, None)
    - "5:" -> slice(5, None, None)
    - "::2" -> slice(None, None, 2)
    """

    try:
        return str_to_slice(value)
    except ValueError as e:
        raise click.BadParameter(f"Invalid slice format: {value}. Error: {e}")


@dataclass
class PaginationParams:
    """Pagination parameters with validation."""

    skip: int = 0
    limit: int | None = None
    page_size: int = DEFAULT_PAGE_SIZE

    def validate(self) -> None:
        """
        Validate pagination parameters.

        Raises:
            ValueError: If parameters are invalid
        """
        if self.skip < 0:
            raise ValueError("skip must be non-negative")
        if unexpected(self.limit is not None and self.limit <= 0):
            raise ValueError("limit must be positive")
        if unexpected(self.page_size <= 0):
            raise ValueError("page-size must be positive")
        if unexpected(self.page_size > MAX_PAGE_SIZE):
            raise ValueError(f"page-size cannot exceed {MAX_PAGE_SIZE}")


class EnumChoice(click.Choice):
    """A version of click.Choice specialized for enum types."""

    def __init__(self: "EnumChoice", enum: type[Enum], *, case_sensitive: bool = True) -> None:
        self._enum = enum
        super().__init__(list(enum.__members__.keys()), case_sensitive=case_sensitive)

    def convert(
        self: "EnumChoice",
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> Enum:
        converted_str = super().convert(value, param, ctx)
        return self._enum.__members__[converted_str]


class PartialArgument:
    """Wraps click.argument with partial arguments for convenient reuse"""

    def __init__(self, *param_decls: Any, **kwargs: Any) -> None:
        self._partial = partial(click.argument, *param_decls, cls=click.Argument, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        return self._partial(*args, **kwargs)


class PartialOption:
    """Wrap partially specified click.option decorator for convenient reuse."""

    def __init__(self: "PartialOption", *param_decls: str, **attrs: Any) -> None:
        self._partial = partial(click.option, *param_decls, cls=click.Option, **attrs)

    def __call__(self: "PartialOption", *param_decls: str, **attrs: Any) -> Callable[[FC], FC]:
        return self._partial(*param_decls, **attrs)


id_arg = PartialArgument("id", type=int)

id_args = PartialArgument("ids", nargs=-1, type=int, required=True)

name_arg = PartialArgument("name", type=str, callback=validate_non_empty)

output = PartialOption(
    "--output",
    "-o",
    type=EnumChoice(OutputEnum),
    default="table",
    help="Output format.  Summary table if not specified.",
)

skip = PartialOption(
    "--skip",
    type=int,
    default=0,
    help="Number of records to skip",
)

limit = PartialOption(
    "--limit",
    type=int,
    default=None,
    help="Maximum records to return",
)

page_size = PartialOption(
    "--page-size",
    type=int,
    default=DEFAULT_PAGE_SIZE,
    help=f"Records per page (max {MAX_PAGE_SIZE})",
)

batch_size = PartialOption(
    "--batch-size",
    type=int,
    default=DEFAULT_BATCH_SIZE,
    help=f"Records per batch (max {MAX_BATCH_SIZE})",
)

show_progress = PartialOption(
    "--show-progress", is_flag=True, help="Show progress bar (disables output until complete)"
)

timeout = PartialOption("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")

json_file = PartialOption(
    "--json-file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="JSON file containing array of update objects (each must have 'id')",
)

field = PartialOption(
    "--field", "-f", multiple=True, type=(str, str), help="Field to update (format: --field name value)"
)

fields = PartialOption(
    "--field",
    "-f",
    "field_values",
    multiple=True,
    type=(str, str),
    help="Field to update (format: --field name value)",
)

order_by = PartialOption(
    "--order-by", "-o", multiple=True, help="Order by field (prefix with - for descending)"
)

json_data = PartialOption(
    "--json-data", type=str, help="JSON string of fields to update (alternative to --field)"
)

filters = PartialOption(
    "--filter",
    "-f",
    "filter_strs",
    multiple=True,
    required=True,
    help="Filter in format field:op:value",
)

logical_op = PartialOption(
    "--logical-op",
    type=click.Choice(["and", "or"]),
    default="and",
    help="How to combine filters",
)

with_count = PartialOption(
    "--with-count",
    is_flag=True,
    help="Include total count of matching records",
)

no_validate = PartialOption(
    "--no-validate", is_flag=True, help="Skip Pydantic validation (faster, less safe)"
)

no_refresh = PartialOption(
    "--no-refresh",
    is_flag=True,
    help="Skip refresh",
)

capture_data = PartialOption(
    "--capture-data",
    is_flag=True,
    help="Capture row data before deletion",
)

confirm = PartialOption(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)

path = PartialOption(
    "--path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Input file path",
)

output_path = PartialOption(
    "--output-path",
    type=click.Path(exists=False, dir_okay=False, writable=True),
    required=True,
    help="Output file path",
)

slice_option = PartialOption(
    "--slice",
    "slice_option",
    type=str,
    default=None,
    callback=parse_slice,
    help="Slice notation (e.g., '1:5', '::2', ':10')",
)

load_type = PartialOption(
    "--load-type",
    type=click.Choice([e.value for e in LoadType], case_sensitive=False),
    default=LoadType.in_place.value,
    callback=lambda ctx, param, value: LoadType(value) if value else None,
    help="How to load the file: in_place (use file as-is), link (symlink), or copy (duplicate file)",
)

row = PartialOption(
    "--row",
    type=int,
    help="Row index",
)
