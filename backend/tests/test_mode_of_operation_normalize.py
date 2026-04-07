"""Tests para normalización canónica de MODE_OF_OPERATION."""

import pandas as pd
import pytest

from app.simulation.core.mode_of_operation_normalize import (
    normalize_mode_of_operation_scalar,
    normalize_mode_of_operation_series,
)


@pytest.mark.parametrize(
    "inp, expected",
    [
        (1, "1"),
        (1.0, "1"),
        ("1", "1"),
        ("1.0", "1"),
        (42, "42"),
        ("  2  ", "2"),
        (None, ""),
        ("", ""),
        ("nan", ""),
        ("NaN", ""),
        (float("nan"), ""),
    ],
)
def test_normalize_mode_of_operation_scalar_integers_and_empty(inp, expected):
    out = normalize_mode_of_operation_scalar(inp)
    assert out == expected


def test_normalize_mode_of_operation_scalar_non_integer_float():
    assert normalize_mode_of_operation_scalar(1.5) == "1.5"


def test_normalize_mode_of_operation_series():
    s = pd.Series([1, 1.0, "1", "1.0", None, "", float("nan")])
    out = normalize_mode_of_operation_series(s)
    assert list(out) == ["1", "1", "1", "1", "", "", ""]
