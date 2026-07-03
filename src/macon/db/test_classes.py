"""Database models for test tables."""

from pydantic import BaseModel
from sqlalchemy import ForeignKey
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .. import models
from .base import Base


class TestNamed(Base):
    """Test class for tables with unique name per row

    Attributes
    ----------
    id_ : int
        Primary key, auto-incrementing unique identifier
    name : str
        Unique name for this row

    Examples
    --------
    >>> tag = TestNamed(
    ...     name="production_models",
    ... )
    """

    __tablename__ = "test_named"

    # Primary key
    id_: Mapped[int] = mapped_column(primary_key=True)

    # Unique name for this catalog tag
    name: Mapped[str] = mapped_column(String(255), index=True, unique=True)

    # Pydantic integration
    @classmethod
    def pydantic_create_class(cls) -> type[BaseModel]:
        """Pydantic model used to create rows in this table.

        Subclasses must implement this to specify their associated
        Pydantic model for creation.

        Returns
        -------
            The Pydantic model class
        """
        return models.TestNamedCreate

    @classmethod
    def pydantic_model_class(cls) -> type[BaseModel]:
        """Return the Pydantic model class for serialization/validation.

        Returns
        -------
            The Pydantic model class for Sed
        """
        return models.TestNamed

    @classmethod
    def class_string(cls) -> str:
        """Return the class identifier string.

        Returns
        -------
            The string 'band' for use in help functions and descriptions
        """
        return cls.__tablename__

    def __repr__(self) -> str:
        """Return a detailed string representation of the Sed.

        Returns
        -------
            String showing id_, name, and description
        """
        return f"Sed(id_={self.id_}, name='{self.name}')"

    def __str__(self) -> str:
        """Return a simple string representation of the Sed.

        Returns
        -------
            Just the bad name
        """
        return self.name


class TestRef(Base):
    """Test class for tables with foreign keys into other tables

    Attributes
    ----------
    id_ : int
        Primary key, auto-incrementing unique identifier
    name : str
        Unique name for this row
    ref_id: int
        Foreign key to other table

    Examples
    --------
    >>> tag = TestRef(
    ...     name="production_models",
    ...     ref_id=3,
    ... )
    """

    __tablename__ = "test_ref"

    # Primary key
    id_: Mapped[int] = mapped_column(primary_key=True)

    # Unique name for this catalog tag
    name: Mapped[str] = mapped_column(String(255), index=True, unique=True)

    #: foreign key into catalog_tag table
    ref_id: Mapped[int] = mapped_column(
        ForeignKey("test_named.id_", ondelete="CASCADE"),
        index=True,
    )

    # Pydantic integration
    @classmethod
    def pydantic_create_class(cls) -> type[BaseModel]:
        """Pydantic model used to create rows in this table.

        Subclasses must implement this to specify their associated
        Pydantic model for creation.

        Returns
        -------
            The Pydantic model class
        """
        return models.TestRefCreate

    @classmethod
    def pydantic_model_class(cls) -> type[BaseModel]:
        """Return the Pydantic model class for serialization/validation.

        Returns
        -------
            The Pydantic model class for TestRef
        """
        return models.TestRef

    @classmethod
    def class_string(cls) -> str:
        """Return the class identifier string.

        Returns
        -------
            The string 'test_ref' for use in help functions and descriptions
        """
        return cls.__tablename__

    def __repr__(self) -> str:
        """Return a detailed string representation of the TestRef.

        Returns
        -------
            String showing id_, name, and ref_id
        """
        return f"Sed(id_={self.id_}, name='{self.name}', ref_id={self.ref_id})"

    def __str__(self) -> str:
        """Return a simple string representation of the TestRef.

        Returns
        -------
            Just the bad name
        """
        return self.name


class TestListPair(Base):
    """Test class for tables paired lists of values

    Attributes
    ----------
    id_ : int
        Primary key, auto-incrementing unique identifier
    name : str
        Unique name for this row
    list_1: list[float]
        First list of values
    list_2: list[float]
        Second list of values

    Examples
    --------
    >>> tag = TestListPair(
    ...     name="production_models",
    ...     list_1=[3.,4.,5.],
    ...     list_2=[5.,6.,7.],
    ... )
    """

    __tablename__ = "test_list_pair"

    # Primary key
    id_: Mapped[int] = mapped_column(primary_key=True)

    # Unique name for this catalog tag
    name: Mapped[str] = mapped_column(String(255), index=True, unique=True)

    #: First list of values
    list_1: Mapped[list[float]] = mapped_column(JSON)

    #: Second list of values
    list_2: Mapped[list[float]] = mapped_column(JSON)

    # Pydantic integration
    @classmethod
    def pydantic_create_class(cls) -> type[BaseModel]:
        """Pydantic model used to create rows in this table.

        Subclasses must implement this to specify their associated
        Pydantic model for creation.

        Returns
        -------
            The Pydantic model class
        """
        return models.TestListPairCreate

    @classmethod
    def pydantic_model_class(cls) -> type[BaseModel]:
        """Return the Pydantic model class for serialization/validation.

        Returns
        -------
            The Pydantic model class for TestRef
        """
        return models.TestListPair

    @classmethod
    def class_string(cls) -> str:
        """Return the class identifier string.

        Returns
        -------
            The string 'test_ref' for use in help functions and descriptions
        """
        return cls.__tablename__

    def __repr__(self) -> str:
        """Return a detailed string representation of the TestRef.

        Returns
        -------
            String showing id_, name
        """
        return f"Sed(id_={self.id_}, name='{self.name}'"

    def __str__(self) -> str:
        """Return a simple string representation of the TestRef.

        Returns
        -------
            Just the bad name
        """
        return self.name
