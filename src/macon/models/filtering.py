from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class FilterOp(StrEnum):
    """Comparison operators for filtering."""

    EQ = "eq"  # Equal (==)
    NE = "ne"  # Not equal (!=)
    LT = "lt"  # Less than (<)
    LE = "le"  # Less than or equal (<=)
    GT = "gt"  # Greater than (>)
    GE = "ge"  # Greater than or equal (>=)
    IN = "in"  # In list
    NOT_IN = "not_in"  # Not in list
    LIKE = "like"  # SQL LIKE pattern matching
    ILIKE = "ilike"  # Case-insensitive LIKE
    IS_NULL = "is_null"  # IS NULL
    IS_NOT_NULL = "is_not_null"  # IS NOT NULL
    BETWEEN = "between"  # BETWEEN two values
    CONTAINS = "contains"  # Array contains (for PostgreSQL arrays)
    STARTS_WITH = "starts_with"  # String starts with
    ENDS_WITH = "ends_with"  # String ends with


class Filter(BaseModel):
    """Represents a single filter condition.

    Parameters
    ----------
    field
        Name of the column to filter on
    op
        Comparison operator to use
    value
        Value to compare against (not needed for IS_NULL/IS_NOT_NULL)

    Examples
    --------
    >>> Filter(field="age", op=FilterOp.GT, value=18)
    >>> Filter(field="status", op=FilterOp.IN, value=["active", "pending"])
    >>> Filter(field="deleted_at", op=FilterOp.IS_NULL)
    >>> Filter(field="name", op=FilterOp.LIKE, value="John%")
    """

    field: str
    op: FilterOp
    value: Any = None

    def __repr__(self) -> str:
        return f"Filter({self.field} {self.op} {self.value})"


class OrderBy(BaseModel):
    """Represents an ordering directive.

    Parameters
    ----------
    field
        Name of the column to order by
    descending
        If True, order descending; if False, order ascending

    Examples
    --------
    >>> OrderBy(field="created_at", descending=True)  # Most recent first
    >>> OrderBy(field="name", descending=False)       # Alphabetical
    """

    field: str
    descending: bool = False

    def __repr__(self) -> str:
        direction = "DESC" if self.descending else "ASC"
        return f"OrderBy({self.field} {direction})"
