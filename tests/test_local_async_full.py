"""Tests for macon.local_async.base — decorators and LocalOperations with mocked TableOperations."""

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel

from macon.local_async.base import (
    LocalOperations,
    with_session,
    with_session_transaction,
    to_pydantic,
    to_pydantic_list,
    to_pydantic_or_none,
    _is_method,
)
from macon.db_oper.base import TableOperations


class FakeResponse(BaseModel):
    id_: int
    name: str


class FakeCreate(BaseModel):
    name: str


class TestIsMethod:
    def test_method_detected(self):
        def foo(self, x):
            pass

        assert _is_method(foo) is True

    def test_function_detected(self):
        def bar(x):
            pass

        assert _is_method(bar) is False

    def test_no_params(self):
        def baz():
            pass

        assert _is_method(baz) is False


class TestWithSessionDecorator:
    async def test_wraps_method(self):
        """with_session injects session as first arg for methods."""

        class Fake:
            @with_session
            async def do_thing(self, session, value):
                return f"got {value} with session={session is not None}"

        with patch("macon.local_async.base.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            f = Fake()
            result = await f.do_thing("hello")
            assert "got hello" in result

    async def test_wraps_function(self):
        """with_session injects session as first arg for plain functions."""

        @with_session
        async def standalone(session, x):
            return x * 2

        with patch("macon.local_async.base.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await standalone(21)
            assert result == 42


class TestWithSessionTransactionDecorator:
    async def test_wraps_method_with_begin(self):
        """with_session_transaction opens session.begin() context."""

        class Fake:
            @with_session_transaction
            async def do_thing(self, session, value):
                return value

        with patch("macon.local_async.base.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_session.begin = MagicMock()
            mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)

            f = Fake()
            result = await f.do_thing("x")
            assert result == "x"
            mock_session.begin.assert_called_once()


class TestToPydanticDecorator:
    async def test_converts_result(self):
        mock_table_ops = MagicMock()
        mock_table_ops.to_pydantic = MagicMock(return_value=FakeResponse(id_=1, name="converted"))

        class Fake:
            def __init__(self):
                self.table_ops = mock_table_ops

            @to_pydantic
            async def get_something(self):
                return "raw_orm_object"

        f = Fake()
        result = await f.get_something()
        assert result.name == "converted"
        mock_table_ops.to_pydantic.assert_called_once_with("raw_orm_object")


class TestToPydanticListDecorator:
    async def test_converts_list(self):
        mock_table_ops = MagicMock()
        mock_table_ops.to_pydantic_list = MagicMock(
            return_value=[FakeResponse(id_=1, name="a"), FakeResponse(id_=2, name="b")]
        )

        class Fake:
            def __init__(self):
                self.table_ops = mock_table_ops

            @to_pydantic_list
            async def get_many(self):
                return ["orm_1", "orm_2"]

        f = Fake()
        result = await f.get_many()
        assert len(result) == 2
        mock_table_ops.to_pydantic_list.assert_called_once()


class TestToPydanticOrNoneDecorator:
    async def test_converts_non_none(self):
        mock_table_ops = MagicMock()
        mock_table_ops.to_pydantic = MagicMock(return_value=FakeResponse(id_=1, name="x"))

        class Fake:
            def __init__(self):
                self.table_ops = mock_table_ops

            @to_pydantic_or_none
            async def get_maybe(self):
                return "something"

        f = Fake()
        result = await f.get_maybe()
        assert result is not None
        assert result.name == "x"

    async def test_returns_none(self):
        mock_table_ops = MagicMock()

        class Fake:
            def __init__(self):
                self.table_ops = mock_table_ops

            @to_pydantic_or_none
            async def get_maybe(self):
                return None

        f = Fake()
        result = await f.get_maybe()
        assert result is None
        mock_table_ops.to_pydantic.assert_not_called()


class TestLocalOperationsInit:
    def test_stores_table_ops(self):
        mock_ops = MagicMock(spec=TableOperations)
        local = LocalOperations(mock_ops)
        assert local.table_ops is mock_ops
