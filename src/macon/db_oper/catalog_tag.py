"""
CatalogTag table operations.

Provides CRUD operations and Pydantic conversions for the CatalogTag table.
"""

from .. import db, models
from .base import TableContext, TableOperations


class CatalogTagOperations(TableOperations[db.CatalogTag, models.CatalogTag, models.CatalogTagCreate]):
    """Create operations for CatalogTag table."""


__all__ = ["CatalogTagOperations", "catalog_tag"]

# Module-level singleton
catalog_tag: CatalogTagOperations = CatalogTagOperations(TableContext.from_db_class(db.CatalogTag))
