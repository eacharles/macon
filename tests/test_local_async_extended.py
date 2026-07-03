"""Extended tests for macon.local_async — more CRUD operations and edge cases."""

from macon.models import TestNamed as TestNamedModel, Filter, FilterOp, OrderBy


class TestLocalAsyncCreateRows:
    async def test_create_rows_batch(self, local_db_session):
        from macon.local_async import test_named

        data = [{"name": f"batch_{i}"} for i in range(5)]
        results = await test_named.create_rows(data)
        assert len(results) == 5
        assert all(isinstance(r, TestNamedModel) for r in results)

    async def test_create_rows_batched(self, local_db_session):
        from macon.local_async import test_named

        data = [{"name": f"batched_{i}"} for i in range(7)]
        results = await test_named.create_rows_batched(data, batch_size=3)
        assert len(results) == 7

    async def test_bulk_insert_rows(self, local_db_session):
        from macon.local_async import test_named

        data = [{"name": f"bulk_{i}"} for i in range(10)]
        count = await test_named.bulk_insert_rows(data)
        assert count == 10


class TestLocalAsyncReadOperations:
    async def test_get_row_or_none_found(self, local_db_session):
        from macon.local_async import test_named

        created = await test_named.create_row(name="find_or_none")
        result = await test_named.get_row_or_none(created.id_)
        assert result is not None
        assert result.name == "find_or_none"

    async def test_get_row_or_none_missing(self, local_db_session):
        from macon.local_async import test_named

        result = await test_named.get_row_or_none(99999)
        assert result is None

    async def test_lookup_by_id_or_name(self, local_db_session):
        from macon.local_async import test_named

        created = await test_named.create_row(name="lookup_target")
        row_id, obj = await test_named.lookup_by_id_or_name(None, "lookup_target")
        assert row_id == created.id_
        assert obj is not None
        assert obj.name == "lookup_target"


class TestLocalAsyncFilterOperations:
    async def test_filter_rows_with_order(self, local_db_session):
        from macon.local_async import test_named

        for name in ["zeta", "alpha", "mu"]:
            await test_named.create_row(name=name)

        results = await test_named.filter_rows(
            order_by=OrderBy(field="name", descending=False),
            limit=100,
        )
        names = [r.name for r in results]
        assert names == sorted(names)

    async def test_count_filtered_rows(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="counted_a")
        await test_named.create_row(name="counted_b")
        await test_named.create_row(name="other")

        count = await test_named.count_filtered_rows(
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="counted")]
        )
        assert count == 2

    async def test_filter_one(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="unique_one")
        result = await test_named.filter_one(
            filters=[Filter(field="name", op=FilterOp.EQ, value="unique_one")]
        )
        assert result.name == "unique_one"

    async def test_filter_one_or_none_missing(self, local_db_session):
        from macon.local_async import test_named

        result = await test_named.filter_one_or_none(
            filters=[Filter(field="name", op=FilterOp.EQ, value="nonexistent_xyz")]
        )
        assert result is None

    async def test_find_by(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="findable")
        results = await test_named.find_by(name="findable")
        assert len(results) == 1

    async def test_find_one_by(self, local_db_session):
        from macon.local_async import test_named

        await test_named.create_row(name="one_findable")
        result = await test_named.find_one_by(name="one_findable")
        assert result.name == "one_findable"


class TestLocalAsyncDeleteOperations:
    async def test_delete_rows_multiple(self, local_db_session):
        from macon.local_async import test_named

        rows = []
        for i in range(3):
            rows.append(await test_named.create_row(name=f"del_multi_{i}"))

        ids = [r.id_ for r in rows]
        result = await test_named.delete_rows(ids, capture_data=True)
        assert result is not None
        assert len(result) == 3

    async def test_bulk_delete_rows(self, local_db_session):
        from macon.local_async import test_named

        rows = []
        for i in range(5):
            rows.append(await test_named.create_row(name=f"bulk_del_{i}"))

        ids = [r.id_ for r in rows]
        count = await test_named.bulk_delete_rows(ids)
        assert count == 5


class TestLocalAsyncStreamingFilter:
    async def test_filter_rows_streaming(self, local_db_session):
        from macon.local_async import test_named

        for i in range(4):
            await test_named.create_row(name=f"stream_filter_{i}")

        rows = []
        async for row in test_named.filter_rows_streaming(
            filters=[Filter(field="name", op=FilterOp.STARTS_WITH, value="stream_filter")],
            limit=100,
        ):
            rows.append(row)
        assert len(rows) == 4
        assert all(isinstance(r, TestNamedModel) for r in rows)
