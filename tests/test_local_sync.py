"""Tests for macon.local_sync (SyncOperations wrapper).

These tests run synchronous operations. Since pytest-asyncio auto mode
uses an event loop, we test the sync wrapper by calling it from a
subprocess to avoid RuntimeError('This event loop is already running').
"""

import subprocess
import sys
import textwrap


def run_sync_test(code: str) -> subprocess.CompletedProcess:
    """Run a snippet of Python code in a subprocess."""
    setup = textwrap.dedent("""\
        import sys
        sys.path.insert(0, "src")

        from macon.db.base import Base
        from macon.db import init_db
        from sqlalchemy.ext.asyncio import create_async_engine
        import asyncio

        async def setup():
            engine = create_async_engine("sqlite+aiosqlite://", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await engine.dispose()
            init_db("sqlite+aiosqlite://")
            from macon.db.session import _engine
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(setup())
    """)
    full_code = setup + textwrap.dedent(code)
    return subprocess.run(
        [sys.executable, "-c", full_code],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestSyncOperations:
    def test_create_and_get(self):
        result = run_sync_test("""
from macon.local_sync import test_named

created = test_named.create_row(name="sync_test")
assert created.name == "sync_test"
assert created.id_ > 0

fetched = test_named.get_row(created.id_)
assert fetched.name == "sync_test"
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_get_rows(self):
        result = run_sync_test("""
from macon.local_sync import test_named

test_named.create_row(name="sync_a")
test_named.create_row(name="sync_b")
rows = test_named.get_rows(limit=100)
assert len(rows) >= 2
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_count_rows(self):
        result = run_sync_test("""
from macon.local_sync import test_named

test_named.create_row(name="sync_count_1")
test_named.create_row(name="sync_count_2")
count = test_named.count_rows()
assert count >= 2
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_filter_rows(self):
        result = run_sync_test("""
from macon.local_sync import test_named
from macon.models import Filter, FilterOp

test_named.create_row(name="sync_filter_target")
test_named.create_row(name="sync_filter_other")
results = test_named.filter_rows(
    filters=[Filter(field="name", op=FilterOp.EQ, value="sync_filter_target")]
)
assert len(results) == 1
assert results[0].name == "sync_filter_target"
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_update_row(self):
        result = run_sync_test("""
from macon.local_sync import test_named

created = test_named.create_row(name="sync_before")
updated = test_named.update_row(created.id_, name="sync_after")
assert updated.name == "sync_after"
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_delete_row(self):
        result = run_sync_test("""
from macon.local_sync import test_named

created = test_named.create_row(name="sync_delete_me")
result = test_named.delete_row(created.id_, capture_data=True)
assert result["name"] == "sync_delete_me"
print("OK")
""")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "OK" in result.stdout
