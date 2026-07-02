"""Pydantic model for the Band"""

from typing import ClassVar

from pydantic import (BaseModel, ConfigDict, Field, ValidationInfo,
                      field_validator)


class TestNamedBase(BaseModel):
    """Simple model for a data base row with a unique name"""

    #: Name for this row, unique
    name: str = Field(..., description="Unique name for this row")


class TestNamedCreate(TestNamedBase):
    """Parameters that are used to create new rows but not in DB tables"""

    
class TestNamed(TestNamedBase):
    """Information about a particular named row

    """

    model_config = ConfigDict(from_attributes=True)

    #: column names to use when printing the table
    col_names_for_table: ClassVar[list[str]] = [
        "id_",
        "name",
    ]

    #: primary key
    id_: int = Field(..., gt=0)



class TestRefBase(BaseModel):
    """Simple model for a data base row that has a foreign key"""

    #: Name for this row, unique
    name: str = Field(..., description="Unique name for this row")


class TestRefCreate(TestRefBase):
    """Parameters that are used to create new rows but not in DB tables"""

    #: Name for the row in the other table
    ref_name: str

    
class TestRef(TestRefBase):
    """Information about a particular named row

    """

    model_config = ConfigDict(from_attributes=True)

    #: column names to use when printing the table
    col_names_for_table: ClassVar[list[str]] = [
        "id_",
        "name",
        "ref_id",
    ]

    #: primary key
    id_: int = Field(..., gt=0)

    #: foreign key
    ref_id: in
    
    
class TestListPairBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    #: Name for this Band, unique
    name: str = Field(..., description="Unique name for this band")

    #: First List
    list_1: list[float] = Field(..., description="First list of values")

    #: Second List
    list_2: list[float] = Field(..., description="Second list of values")

    @field_validator("list_1", "list_2")
    @classmethod
    def validate_non_empty(cls, v: list[float]) -> list[float]:
        """Ensure arrays are not empty"""
        if len(v) == 0:
            raise ValueError("Array must not be empty")
        return v

    @field_validator("list_1")
    @classmethod
    def validate_same_length(cls, v: list[float], info: ValidationInfo) -> list[float]:
        """Ensure list_1 and list_2 arrays have same length"""
        if "sed_wavelengths" in info.data:
            if len(v) != len(info.data["sed_wavelengths"]):
                raise ValueError("sed_values must have same length as sed_wavelengths")
        return v


class TestListPairCreate(TestListPairBase):
    """Parameters that are used to create new rows but not in DB tables"""


class TestListPair(TestListPairBase):
    """Test class that stores two lists of values

    """

    model_config = ConfigDict(from_attributes=True)

    #: column names to use when printing the table
    col_names_for_table: ClassVar[list[str]] = [
        "id_",
        "name",
    ]

    #: primary key
    id_: int = Field(..., gt=0)
