from __future__ import annotations

import json
from collections.abc import Sequence
from enum import Enum, auto
from typing import Any, cast

import yaml
from pydantic import BaseModel
from tabulate import tabulate


class OutputEnum(Enum):
    """Options for output format"""

    yaml = auto()  # pylint: disable=invalid-name
    json = auto()  # pylint: disable=invalid-name
    table = auto()  # pylint: disable=invalid-name


def display_table(data: list[dict[str, Any]], col_names: list[str]) -> str:
    """
    Display data as a formatted table.

    Parameters
    ----------
    data
        List of dictionaries containing the data to display
    col_names
        Column names to display and extract from each dict

    Returns
    -------
        Formatted table string, or empty string if no data

    Notes
    -----
    Uses tabulate library to format the table. Missing keys in data
    dictionaries will be displayed as empty cells.
    """
    if not data:
        return ""

    rows = [[item.get(col, "") for col in col_names] for item in data]
    return tabulate(rows, headers=col_names, tablefmt="simple")


def format_output(data: list[dict[str, Any]] | dict[str, Any], output_format: OutputEnum) -> str:
    """
    Format data as JSON or YAML.

    Parameters
    ----------
    data
        Dictionary or list of dictionaries to format
    output_format
        Output format: 'json' or 'yaml'

    Returns
    -------
        Formatted data string

    Raises
    ------
    ValueError
        If output_format is not 'json' or 'yaml'

    Examples
    --------
    >>> data = {'name': 'Alice', 'age': 25}
    >>> print(format_output(data, 'json'))
    {
      "name": "Alice",
      "age": 25
    }
    """
    if output_format == OutputEnum.json:
        return json.dumps(data, indent=2)
    if output_format == OutputEnum.yaml:
        return yaml.dump(data, default_flow_style=False)
    raise ValueError(f"Unknown output format: {output_format.name}")


def output_pydantic(
    result: BaseModel | Sequence[BaseModel], output_format: OutputEnum, col_names: list[str] | None = None
) -> str:
    """
    Output Pydantic model(s) in the specified format.

    This function handles both single models and lists of models,
    providing a unified interface for output formatting.

    Parameters
    ----------
    result
        Single Pydantic model instance or list of model instances
    output_format
        Output format: 'json', 'yaml', or 'table'
    col_names, optional
        Column names for table output. Required if output_format is 'table'

    Returns
    -------
        Formatted output string

    Raises
    ------
    ValueError
        If output_format is 'table' but col_names is None, or if
        output_format is not recognized

    Examples
    --------
    >>> from pydantic import BaseModel
    >>> class User(BaseModel):
    ...     name: str
    ...     age: int

    Single model:
    >>> user = User(name='Alice', age=25)
    >>> print(output_pydantic(user, 'json'))
    {
      "name": "Alice",
      "age": 25
    }

    List of models:
    >>> users = [User(name='Alice', age=25), User(name='Bob', age=30)]
    >>> print(output_pydantic(users, 'table', col_names=['name', 'age']))
    name      age
    ------  -----
    Alice      25
    Bob        30
    """
    # Normalize to list
    is_single = isinstance(result, BaseModel)
    results = cast(list[BaseModel], [result] if is_single else result)

    # Convert to dicts
    data = [item.model_dump() for item in results]

    # Handle table output
    if output_format == OutputEnum.table:
        if col_names is None:
            raise ValueError("Table output requires column names")
        return display_table(data, col_names)

    # Handle other formats
    return format_output(data, output_format)
