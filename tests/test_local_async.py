"""Tests for macon.local_async (LocalOperations with auto-session)."""

from macon.models import TestNamed as TestNamedModel, Filter, FilterOp


class TestLocalAsyncCRUD:
    async def test_create_row(self, local_db_session):
        from macon.local_async import test_named

        result = await test_named.create_row(name="local_create")
        assert isinstance(result, TestNamedModel)
        assert result.name == "local_create"
        assert result.id_ > 0

    async def test_get_row(self, local_db_session):
        from macon.local_async import test_named

        created = await test_named.create_row(name="get_me")
        fetched = await test_named.get_row(created.id_)
        assert fetched.name == "get_me"

    async def test_get_row_by_name(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="find_by_name")
        fetched = await test_named.get_row_by_name("find_by_name")
        assert fetched.name == "find_by_name"

    async def test_get_rows(self, local_db_session):
        from macon.local_async import test_named

        for i in range(3):
            await test_named.create_row(name=f"list_{i}")
        rows = await test_named.get_rows(limit=100)
        assert len(rows) >= 3
        assert all(isinstance(r, TestNamedModel) for r in rows)

    async def test_count_rows(self, local_db_session):
        from macon.local_async import test_named

        for i in range(4):
            await test_named.create_row(name=f"count_{i}")
        count = await test_named.count_rows()
        assert count >= 4

    async def test_update_row(self, local_db_session):
        from macon.local_async import test_named

        created = await test_named.create_row(name="before_update")
        updated = await test_named.update_row(created.id_, name="after_update")
        assert updated.name == "after_update"

    async def test_delete_row(self, local_db_session):
        from macon.local_async import test_named

        created = await test_named.create_row(name="to_delete")
        result = await test_named.delete_row(created.id_, capture_data=True)
        assert result is not None
        assert result["name"] == "to_delete"

    async def test_filter_rows(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="filter_target")
        await test_named.create_row(name="filter_other")
        results = await test_named.filter_rows(
            filters=[Filter(field="name", op=FilterOp.EQ, value="filter_target")]
        )
        assert len(results) == 1
        assert results[0].name == "filter_target"

    async def test_get_rows_streaming(self, local_db_session):
        from macon.local_async import test_named

        for i in range(3):
            await test_named.create_row(name=f"stream_{i}")
        rows = []
        async for row in test_named.get_rows_streaming(limit=100):
            rows.append(row)
        assert len(rows) >= 3
        assert all(isinstance(r, TestNamedModel) for r in rows)
