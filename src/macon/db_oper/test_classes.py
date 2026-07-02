"""CatalogBandAssoc operations.

This module provides operations for creating associations between catalog tags
and bands, with automatic lookup of foreign keys by ID or name.

Examples
--------
Create by IDs:

>>> async with session.begin():
...     assoc = await catalog_band_assoc_creator.create_row(
...         session,
...         mag_column_name="g_prime",
...         mag_err_column_name="g_prime_err",
...         catalog_tag_id=123,
...         band_id=456
...     )

Create by names:

>>> async with session.begin():
...     assoc = await catalog_band_assoc_creator.create_row(
...         session,
...         mag_column_name="g_prime",
...         mag_err_column_name="g_prime_err",
...         catalog_tag_name="SDSS_DR16",
...         band_name="r"
...     )

Mix IDs and names:

>>> async with session.begin():
...     assoc = await catalog_band_assoc_creator.create_row(
...         session,
...         mag_column_name="g_prime",
...         mag_err_column_name="g_prime_err",
...         catalog_tag_id=123,
...         band_name="i"
...     )
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .. import db, db_funcs, models
from .base import TableContext, TableOperations

logger = logging.getLogger(__name__)

__all__ = ["CatalogBandAssocOperations", "catalog_band_assoc"]


class CatalogBandAssocOperations(
    TableOperations[db.CatalogBandAssoc, models.CatalogBandAssoc, models.CatalogBandAssocCreate]
):
    """Create operations for CatalogBandAssoc table.

    Handles automatic lookup of catalog_tag and band by either ID or name.
    """

    async def get_create_kwargs(
        self,
        session: AsyncSession,
        mag_column_name: str | None = None,
        mag_err_column_name: str | None = None,
        catalog_tag_id: int | None = None,
        catalog_tag_name: str | None = None,
        band_id: int | None = None,
        band_name: str | None = None,
        **extra_kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare kwargs for creating a CatalogBandAssoc instance.

        Resolves foreign keys by looking up catalog_tag and band by name
        if IDs are not provided.

        Parameters
        ----------
        session
            Database session
        mag_column_name
            Name for the magntidue column for band in this catalog (required)
        mag_err_column_name
            Name for the magntidue error column for band in this catalog (required)
        catalog_tag_id
            ID of the catalog tag (provide this OR catalog_tag_name)
        catalog_tag_name
            Name of the catalog tag (provide this OR catalog_tag_id)
        band_id
            ID of the band (provide this OR band_name)
        band_name
            Name of the band (provide this OR band_id)
        **extra_kwargs
            Additional fields to pass through to model

        Returns
        -------
        dict[str, Any]
            Validated kwargs ready for CatalogBandAssoc creation

        Raises
        ------
        ValueError
            If band_alias is empty, or if neither ID nor name provided
            for catalog_tag or band
        NoResultFound
            If catalog_tag or band lookup by name fails

        Examples
        --------
        >>> creator = CatalogBandAssocCreate(...)
        >>> # By IDs
        >>> kwargs = await creator.get_create_kwargs(
        ...     session,
        ...     mag_column_name="g_prime",
        ...     mag_err_column_name="g_prime_err",
        ...     catalog_tag_id=123,
        ...     band_id=456
        ... )

        >>> # By names
        >>> kwargs = await creator.get_create_kwargs(
        ...     session,
        ...     mag_column_name="r_prime",
        ...     mag_err_column_name="r_prime_err",
        ...     catalog_tag_name="SDSS_DR16",
        ...     band_name="r"
        ... )

        >>> # Mixed
        >>> kwargs = await creator.get_create_kwargs(
        ...     session,
        ...     mag_column_name="i_prime",
        ...     mag_err_column_name="i_prime_err",
        ...     catalog_tag_id=123,
        ...     band_name="i"
        ... )
        """
        # Validate mag_column_name and mag_err_column_name
        if not mag_column_name or not isinstance(mag_column_name, str):
            logger.warning(
                "Invalid mag_column_name for CatalogBandAssoc.",
            )
            raise ValueError("mag_column_name must be a non-empty string")

        if not mag_err_column_name or not isinstance(mag_err_column_name, str):
            logger.warning(
                "Invalid mag_err_column_name for CatalogBandAssoc.",
            )
            raise ValueError("mag_err_column_name must be a non-empty string")

        catalog_tag_id, _ = await db_funcs.read.lookup_by_id_or_name(
            db.CatalogTag,
            session,
            catalog_tag_id,
            catalog_tag_name,
        )

        band_id, _ = await db_funcs.read.lookup_by_id_or_name(
            db.Band,
            session,
            band_id,
            band_name,
        )

        # Build final kwargs
        return {
            "mag_column_name": mag_column_name,
            "mag_err_column_name": mag_err_column_name,
            "catalog_tag_id": catalog_tag_id,
            "band_id": band_id,
            **extra_kwargs,
        }


# Module-level singleton
catalog_band_assoc: CatalogBandAssocOperations = CatalogBandAssocOperations(
    TableContext.from_db_class(db.CatalogBandAssoc)
)
