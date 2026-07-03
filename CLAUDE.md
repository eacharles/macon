# CLAUDE.md — macon

## Overview

`macon` is a generic Python library that provides CRUD (Create-Read-Update-Delete) and filtering database operations across multiple software layers. It gives you one consistent interface for database tables at every level: raw SQLAlchemy functions, operation classes, async/sync local wrappers, FastAPI routers, and remote HTTP clients.

## Architecture — Layered Design

```
CLI (click)
  └── local_sync / remote_sync   ← synchronous wrappers (asyncio.run)
        └── local_async / remote_async   ← async operations
              └── db_oper (TableOperations)   ← CRUD + validation + hooks
                    └── db_funcs (read, filter, update, delete)   ← raw SQLAlchemy queries
                          └── db (Base, session)   ← ORM models + engine
```

| Layer | Purpose |
|-------|---------|
| `db/` | SQLAlchemy ORM base class (`Base`) with lifecycle hooks, session management |
| `db_funcs/` | Stateless async functions: `get_row`, `filter_rows`, `update_row`, `delete_row`, etc. |
| `db_oper/` | `TableOperations` class — typed CRUD wrapping `db_funcs`, adds validation, batching, file handling |
| `local_async/` | `LocalOperations` — adds session management decorators (`@with_session`) around `TableOperations` |
| `local_sync/` | `SyncOperations` — blocking wrappers via `asyncio.run()` for CLI/scripts |
| `remote_async/` | `AsyncRemoteOperations` — HTTP client (httpx) against the FastAPI server |
| `remote_sync/` | `SyncRemoteOperations` — blocking wrappers for the remote client |
| `router/` | `create_table_router()` — generates FastAPI `APIRouter` with full CRUD + filter endpoints |
| `client/` | `RemoteAPI` context manager + `RemoteTableOperations` / `RemoteDatabase` for HTTP access |
| `models/` | Pydantic models (response, create, filtering, web) |
| `cli/` | Click CLI entry points: `macon-local`, `macon-server`, `macon-remote` |
| `config.py` | Pydantic Settings configuration (env vars, `.env`, nested `DB__URL` etc.) |

## Key Patterns

- **Generic typing**: `TableOperations[T, ResponseT, CreateT]` — T is the SQLAlchemy model, ResponseT/CreateT are Pydantic models.
- **Lifecycle hooks**: `Base` provides `pre_create_hook`, `after_create_hook`, `pre_update_hook`, `after_update_hook`, `pre_delete_hook`, `after_delete_hook`.
- **Filter system**: `Filter(field, op, value)` with `FilterOp` enum (eq, ne, lt, gt, like, between, etc.) + `OrderBy`.
- **File-backed tables**: `FileValidatedOperations` subclass handles load/download with path security validation.
- **Decorator patterns**: `@with_session`, `@with_session_transaction`, `@to_pydantic`, `@forward_to_db_funcs`.

## Test Tables

The package includes example/test tables demonstrating the patterns:
- `TestNamed` — simple table with unique name
- `TestRef` — table with a foreign key reference to TestNamed
- `TestListPair` — table storing paired lists of values (JSON columns)

## Development

### Setup
```bash
make init          # creates .venv via uv, installs pre-commit hooks
```

### Testing
```bash
make test-sqlite   # runs pytest with SQLite backend (sets DB__URL)
```

### Linting & Type Checking
```bash
make lint          # pre-commit (ruff format + lint, trailing whitespace, yamllint)
make typing        # mypy src tests
```

### Configuration
- Environment variable nesting delimiter: `__` (e.g., `DB__URL`, `STORAGE__ARCHIVE`)
- Client env vars: `MACON_SERVICE_URL`, `MACON_AUTH_TOKEN`, `MACON_TIMEOUT`
- Remote CLI env vars: `MACON_BASE_URL`, `MACON_AUTH_TOKEN`
- Default DB: `sqlite+aiosqlite:///macon.db`
- Line length: 110 (ruff), 120 (pylint)
- Python: 3.13+ required
- Package manager: `uv`

### CLI Entry Points
- `macon-local` — local DB admin (init, CRUD via click)
- `macon-server` — FastAPI/uvicorn server
- `macon-remote` — remote client CLI

### Pre-commit Hooks
- ruff (lint + format + isort)
- trailing-whitespace, end-of-file-fixer, check-yaml, check-toml
- yamllint

### CI
- GitHub Actions: tests on Python 3.13, lint, docs, publish-to-pypi
- Test command: `pytest tests` with coverage
