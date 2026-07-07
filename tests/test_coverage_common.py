"""Coverage tests for macon.common — line 169 (integer in slice_to_str)."""

from macon.common import slice_to_str


class TestSliceToStrInteger:
    def test_integer_input(self):
        result = slice_to_str(5)
        assert result == "5"

    def test_integer_zero(self):
        assert slice_to_str(0) == "0"
