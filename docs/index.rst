macon
=====

**macon** is a generic Python library that provides CRUD (Create-Read-Update-Delete)
and filtering database operations across multiple software layers. It gives you one
consistent interface for database tables at every level: raw SQLAlchemy functions,
operation classes, async/sync local wrappers, FastAPI routers, and remote HTTP clients.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   getting_started
   user_guide/index
   api/index

Features
--------

- **Layered architecture** — use the abstraction level that fits your needs
- **Full type safety** — generic typing across SQLAlchemy models and Pydantic schemas
- **Lifecycle hooks** — pre/post hooks for create, update, and delete operations
- **Flexible filtering** — 16 filter operators with AND/OR logic and ordering
- **Auto-generated REST API** — one call creates a full CRUD router for any table
- **Sync and async** — async-first with sync wrappers for CLI/scripts
- **Remote client** — HTTP client that mirrors the local interface exactly
- **CLI tools** — Click-based admin commands for local and remote operations
