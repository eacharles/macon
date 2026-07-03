Defining Tables
===============

To add a new table to macon, you need three components:

1. A SQLAlchemy ORM model (inherits from ``Base``)
2. Pydantic models for creation and response
3. A ``TableOperations`` instance (or subclass for custom logic)

Step 1: SQLAlchemy Model
------------------------

.. code-block:: python

   from sqlalchemy import String, ForeignKey
   from sqlalchemy.orm import Mapped, mapped_column
   from pydantic import BaseModel

   from macon.db.base import Base


   class Project(Base):
       __tablename__ = "projects"

       id_: Mapped[int] = mapped_column(primary_key=True)
       name: Mapped[str] = mapped_column(String(255), unique=True)
       owner_id: Mapped[int] = mapped_column(ForeignKey("users.id_"))
       description: Mapped[str | None] = mapped_column(String(1000), default=None)

       @classmethod
       def pydantic_model_class(cls):
           return ProjectResponse

       @classmethod
       def pydantic_create_class(cls):
           return ProjectCreate

       @classmethod
       def class_string(cls):
           return "project"

Step 2: Pydantic Models
-----------------------

.. code-block:: python

   from typing import ClassVar
   from pydantic import BaseModel, ConfigDict, Field


   class ProjectCreate(BaseModel):
       name: str = Field(..., description="Unique project name")
       owner_id: int
       description: str | None = None


   class ProjectResponse(BaseModel):
       model_config = ConfigDict(from_attributes=True)

       # Used by CLI for table display
       col_names_for_table: ClassVar[list[str]] = ["id_", "name", "owner_id"]

       id_: int
       name: str
       owner_id: int
       description: str | None = None

Step 3: Create Operations
-------------------------

For simple tables (no custom logic needed):

.. code-block:: python

   from macon.db_oper.base import TableContext, TableOperations

   project_ops = TableOperations(TableContext.from_db_class(Project))

For tables with foreign key resolution or custom creation logic, subclass
``TableOperations`` and override ``get_create_kwargs``:

.. code-block:: python

   from macon.db_funcs.read import lookup_by_id_or_name


   class ProjectOperations(TableOperations[Project, ProjectResponse, ProjectCreate]):

       async def get_create_kwargs(self, session, owner_id=None, owner_name=None, **kwargs):
           # Allow creating by owner name instead of ID
           owner_id, _ = await lookup_by_id_or_name(
               User, session, owner_id, owner_name
           )
           return {"owner_id": owner_id, **kwargs}

Step 4: Wire Up Higher Layers
-----------------------------

.. code-block:: python

   from macon.local_async.base import LocalOperations
   from macon.local_sync.base import SyncOperations
   from macon.router.base import create_table_router

   # Async local operations (auto-session)
   local_projects = LocalOperations(project_ops)

   # Sync wrapper (for CLI)
   sync_projects = SyncOperations(local_projects)

   # FastAPI router
   project_router = create_table_router("projects", local_projects)

Custom Lifecycle Hooks
----------------------

Override hooks on the model class to add behavior at key points:

.. code-block:: python

   class Project(Base):
       # ... columns ...

       @classmethod
       async def pre_create_hook(cls, session, data):
           # Validate the owner exists
           owner = await session.get(User, data["owner_id"])
           if owner is None:
               raise ValueError(f"Owner {data['owner_id']} not found")
           return data

       @classmethod
       async def after_delete_hook(cls, session, row):
           # Clean up related resources
           await cleanup_project_files(row.id_)
