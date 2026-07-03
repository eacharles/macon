Architecture
============

macon uses a layered architecture where each layer adds functionality on top
of the previous one. You can use whichever layer fits your needs.

Layer Diagram
-------------

.. code-block:: text

   CLI (click)
     └── local_sync / remote_sync        ← synchronous wrappers (asyncio.run)
           └── local_async / remote_async ← async operations
                 └── db_oper (TableOperations)   ← CRUD + validation + hooks
                       └── db_funcs (read, filter, update, delete) ← raw queries
                             └── db (Base, session) ← ORM models + engine

Layers
------

``db/``
~~~~~~~

SQLAlchemy ORM base class (``Base``) with lifecycle hooks and session management.
All table models inherit from ``Base`` and must implement:

- ``pydantic_model_class()`` — returns the response Pydantic model
- ``pydantic_create_class()`` — returns the creation Pydantic model
- ``class_string()`` — returns a string identifier

``db_funcs/``
~~~~~~~~~~~~~

Stateless async functions that operate directly on SQLAlchemy sessions.
These never commit — the caller manages the transaction.

Modules: ``read``, ``filter``, ``update``, ``delete``.

``db_oper/``
~~~~~~~~~~~~

``TableOperations`` class wraps ``db_funcs`` with:

- Pydantic validation on create
- Lifecycle hooks (pre/post create, update, delete)
- Batch operations and bulk inserts
- Type-safe generics: ``TableOperations[T, ResponseT, CreateT]``

``local_async/``
~~~~~~~~~~~~~~~~

``LocalOperations`` adds automatic session management via decorators.
No session parameter needed — just call methods directly:

.. code-block:: python

   row = await local_ops.create_row(name="Alice")
   rows = await local_ops.get_rows(limit=10)

``local_sync/``
~~~~~~~~~~~~~~~

``SyncOperations`` wraps async operations with ``asyncio.run()`` for use
in CLI commands and scripts.

``router/``
~~~~~~~~~~~

``create_table_router()`` generates a FastAPI ``APIRouter`` with full CRUD,
filtering, streaming, and batch endpoints for any table.

``client/``
~~~~~~~~~~~

``RemoteTableOperations`` and ``RemoteAPI`` provide an HTTP client that
mirrors the local interface. Use ``RemoteDatabase`` for multi-table access.

``remote_async/`` and ``remote_sync/``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-configured remote operation instances with connection management
and sync wrappers.

Lifecycle Hooks
---------------

The ``Base`` class provides six hooks that subclasses can override:

.. code-block:: python

   class MyModel(Base):
       @classmethod
       async def pre_create_hook(cls, session, data):
           data["created_at"] = datetime.utcnow()
           return data

       @classmethod
       async def after_create_hook(cls, session, row):
           await send_notification(row.id_)

Hook execution order:

- **CREATE**: ``pre_create_hook`` → flush → ``after_create_hook`` → commit
- **UPDATE**: ``pre_update_hook`` → flush → ``after_update_hook`` → commit
- **DELETE**: ``pre_delete_hook`` → flush → ``after_delete_hook`` → commit

Transaction Management
----------------------

The ``db_funcs`` layer only flushes, never commits. Transactions are managed by:

- ``get_session()`` — auto-commits on successful exit, rolls back on exception
- ``@with_session_transaction`` — wraps in ``session.begin()`` for explicit boundaries
- Direct session management for fine-grained control
