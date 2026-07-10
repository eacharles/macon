<p align="center">
  <img src="docs/figures/macon_logo_big.jpg" alt="macon logo" width="400">
</p>

# macon

`macon` is a generic Python library that provides CRUD (Create-Read-Update-Delete)
and filtering database operations across many layers of software. You define a
SQLAlchemy table and a couple of Pydantic models once, and `macon` gives you one
consistent interface for it at every level — from raw async queries all the way up
to an auto-generated REST API and an HTTP client.

## Why macon?

Most projects re-implement the same database plumbing over and over: query helpers,
validation, session handling, a FastAPI router, and a client to call it. `macon`
factors that plumbing into composable layers so you write your models once and reuse
the same operations everywhere.

## Layered design

```
CLI (click)
  └── local_sync / remote_sync      ← synchronous wrappers (asyncio.run)
        └── local_async / remote_async   ← async operations
              └── db_oper (TableOperations)   ← CRUD + validation + hooks
                    └── db_funcs (read, filter, update, delete)   ← raw SQLAlchemy
                          └── db (Base, session)   ← ORM models + engine
```

| Layer          | Purpose                                                                       |
|----------------|-------------------------------------------------------------------------------|
| `db/`          | SQLAlchemy ORM base class (`Base`) with lifecycle hooks and session management |
| `db_funcs/`    | Stateless async functions: `get_row`, `filter_rows`, `update_row`, `delete_row` |
| `db_oper/`     | `TableOperations` — typed CRUD wrapping `db_funcs`, adds validation, batching, file handling |
| `local_async/` | `LocalOperations` — adds session management (`@with_session`) around `TableOperations` |
| `local_sync/`  | `SyncOperations` — blocking wrappers via `asyncio.run()` for CLI/scripts       |
| `remote_async/`| `AsyncRemoteOperations` — HTTP client (httpx) against the FastAPI server        |
| `remote_sync/` | `SyncRemoteOperations` — blocking wrappers for the remote client               |
| `router/`      | `create_table_router()` — generates a FastAPI `APIRouter` with full CRUD + filter endpoints |
| `client/`      | `RemoteAPI` context manager + `RemoteTableOperations` / `RemoteDatabase`        |
| `models/`      | Pydantic models (response, create, filtering, web)                            |
| `cli/`         | Click CLI entry points: `macon-local`, `macon-server`, `macon-remote`          |

## Key features

- **Generic typing** — `TableOperations[T, ResponseT, CreateT]` ties a SQLAlchemy
  model to its Pydantic response/create models for end-to-end type safety.
- **Lifecycle hooks** — `Base` exposes `pre_create_hook`, `after_create_hook`,
  `pre_update_hook`, `after_update_hook`, `pre_delete_hook`, `after_delete_hook`.
- **Filter system** — `Filter(field, op, value)` with a `FilterOp` enum
  (`eq`, `ne`, `lt`, `gt`, `like`, `between`, …) plus `OrderBy`.
- **File-backed tables** — `FileValidatedOperations` handles load/read-slice with
  path-security validation, using `tables_io` for HDF5/parquet I/O.
- **Auto-generated REST API** — turn any table into a full CRUD + filter API with a
  single `create_table_router()` call.
- **UUID7 or int primary keys** — supported out of the box.

## Installation

```bash
pip install macon[all]        # everything
```

Or install only what you need:

```bash
pip install macon[db]         # SQLAlchemy + async drivers
pip install macon[server]     # FastAPI server (includes db)
pip install macon[client]     # HTTP client (httpx)
```

Requires Python 3.13+.

## Quick example

Define a table and its Pydantic models to get full CRUD operations:

```python
from pydantic import BaseModel, ConfigDict
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from macon.db.base import Base
from macon.db_oper.base import TableContext, TableOperations


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


class UserCreate(BaseModel):
    name: str
    email: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_: int
    name: str
    email: str


user_ops = TableOperations(TableContext.from_db_class(User))
```

Use the operations with a database session:

```python
from macon.db.session import init_db, get_session
from macon.models import Filter, FilterOp

init_db("sqlite+aiosqlite:///app.db")

async with get_session() as session:
    user = await user_ops.create_row(session, name="Alice", email="alice@example.com")
    fetched = await user_ops.get_row(session, user.id_)

    results = await filter_rows(
        User, session,
        filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="A")],
    )
```

## Auto-generated REST API

Wrap operations with session management and generate a full FastAPI router:

```python
from fastapi import FastAPI
from macon.local_async.base import LocalOperations
from macon.router.base import create_table_router

local_users = LocalOperations(user_ops)
router = create_table_router("users", local_users)

app = FastAPI()
app.include_router(router)
```

## CLI entry points

- `macon-local` — local DB admin (init, CRUD via click)
- `macon-server` — FastAPI/uvicorn server
- `macon-remote` — remote client CLI

## Configuration

Configuration uses Pydantic Settings, read from environment variables and `.env`
(nested with a `__` delimiter, e.g. `DB__URL`, `STORAGE__ARCHIVE`). The default
database is `sqlite+aiosqlite:///macon.db`.

## Development

```bash
make init          # create .venv via uv, install pre-commit hooks
make test-sqlite   # run pytest against SQLite
make lint          # ruff format + lint, pre-commit hooks
make typing        # mypy src tests
```

## Documentation

Full documentation (Sphinx) lives in `docs/`:

```bash
pip install -e ".[docs,db,server,client]"
cd docs && make html     # builds to docs/_build/html/
```

## License

MIT — see [LICENSE](LICENSE).
