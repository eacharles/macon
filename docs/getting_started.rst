Getting Started
===============

Installation
------------

Install macon with all optional dependencies:

.. code-block:: bash

   pip install macon[all]

Or install only what you need:

.. code-block:: bash

   pip install macon[db]       # SQLAlchemy + async drivers
   pip install macon[server]   # FastAPI server (includes db)
   pip install macon[client]   # HTTP client (httpx)

Quick Example
-------------

Define a table, its Pydantic models, and get full CRUD operations:

.. code-block:: python

   from pydantic import BaseModel, ConfigDict, Field
   from sqlalchemy import String
   from sqlalchemy.orm import Mapped, mapped_column

   from macon.db.base import Base
   from macon.db_oper.base import TableContext, TableOperations


   # 1. Define the SQLAlchemy model
   class User(Base):
       __tablename__ = "users"

       id_: Mapped[int] = mapped_column(primary_key=True)
       name: Mapped[str] = mapped_column(String(255), unique=True)
       email: Mapped[str] = mapped_column(String(255))

       @classmethod
       def pydantic_model_class(cls):
           return UserResponse

       @classmethod
       def pydantic_create_class(cls):
           return UserCreate

       @classmethod
       def class_string(cls):
           return "user"


   # 2. Define Pydantic models
   class UserCreate(BaseModel):
       name: str
       email: str


   class UserResponse(BaseModel):
       model_config = ConfigDict(from_attributes=True)
       id_: int
       name: str
       email: str


   # 3. Create operations
   user_ops = TableOperations(TableContext.from_db_class(User))

Using the Operations
~~~~~~~~~~~~~~~~~~~~

With a database session:

.. code-block:: python

   from macon.db.session import init_db, get_session

   init_db("sqlite+aiosqlite:///app.db")

   async with get_session() as session:
       # Create
       user = await user_ops.create_row(session, name="Alice", email="alice@example.com")

       # Read
       fetched = await user_ops.get_row(session, user.id_)

       # Update
       from macon.db_funcs.update import update_row
       updated = await update_row(User, session, user.id_, email="newalice@example.com")

       # Filter
       from macon.db_funcs.filter import filter_rows
       from macon.models import Filter, FilterOp
       results = await filter_rows(
           User, session,
           filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="A")],
       )

Auto-Generated REST API
~~~~~~~~~~~~~~~~~~~~~~~

Create a full FastAPI router with one call:

.. code-block:: python

   from fastapi import FastAPI
   from macon.local_async.base import LocalOperations
   from macon.router.base import create_table_router

   # Wrap operations with auto-session management
   local_users = LocalOperations(user_ops)

   # Generate router with all CRUD + filter endpoints
   router = create_table_router("users", local_users)

   app = FastAPI()
   app.include_router(router, prefix="/api/v1")

This gives you endpoints like ``POST /api/v1/users/create_row``,
``GET /api/v1/users/get_rows``, ``POST /api/v1/users/filter_rows``, etc.
