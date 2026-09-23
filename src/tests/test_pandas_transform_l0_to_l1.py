import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from scripts.pandas_etl.commons.transformations import (
    cast_datatype,
    filter_columns,
    rename_columns,
    split_customers_address,
    split_customers_name,
)


# split_customers_name
@pytest.mark.parametrize(
    "input_name,expected_first,expected_last",
    [
        (None, pd.NA, pd.NA),
        ("Huy", "Huy", pd.NA),
        ("Ngo Huy", "Huy", "Ngo"),
        ("Ngo Minh Huy", "Huy", "Ngo Minh"),
        ("  Ngo    Minh     Huy  ", "Huy", "Ngo Minh"),
        ("", pd.NA, pd.NA),
    ],
)
def test_split_customers_name(
    input_name,
    expected_first,
    expected_last,
):
    df = pd.DataFrame({"name": [input_name]})

    result = split_customers_name(
        {"df": df},
        [{"from": "name", "to": ["first_name", "last_name"]}],
    )

    assert (
        pd.isna(result.loc[0, "first_name"])
        if pd.isna(expected_first)
        else result.loc[0, "first_name"] == expected_first
    )

    assert (
        pd.isna(result.loc[0, "last_name"])
        if pd.isna(expected_last)
        else result.loc[0, "last_name"] == expected_last
    )


# split_customers_address
@pytest.mark.parametrize(
    "input_address,expected_address,expected_province",
    [
        (None, None, None),
        ("Ho Chi Minh", "Ho Chi Minh", None),
        (
            "123 Nguyen Ai Quoc, Ho Chi Minh",
            "123 Nguyen Ai Quoc, Ho Chi Minh",
            "Ho Chi Minh",
        ),
        (
            "123 Nguyen Ai Quoc, District 1, Ho Chi Minh",
            "123 Nguyen Ai Quoc, District 1, Ho Chi Minh",
            "Ho Chi Minh",
        ),
        (
            ",123 Nguyen Ai Quoc, Ho Chi Minh,",
            "123 Nguyen Ai Quoc, Ho Chi Minh",
            "Ho Chi Minh",
        ),
        (
            "123 Nguyen Ai Quoc, , Ho Chi Minh",
            "123 Nguyen Ai Quoc, Ho Chi Minh",
            "Ho Chi Minh",
        ),
    ],
)
def test_split_customers_address(
    input_address,
    expected_address,
    expected_province,
):
    df = pd.DataFrame({"customer_address": [input_address]})

    result = split_customers_address(
        {"df": df},
        [
            {
                "from": "customer_address",
                "to": ["address", "address_province"],
            }
        ],
    )

    if expected_address is None:
        assert pd.isna(result.loc[0, "address"])
    else:
        assert result.loc[0, "address"] == expected_address

    if expected_province is None:
        assert pd.isna(result.loc[0, "address_province"])
    else:
        assert result.loc[0, "address_province"] == expected_province


# rename_columns
def test_rename_columns_success():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["Huy"],
            "status": ["active"],
        }
    )

    result = rename_columns(
        {"df": df},
        [
            {"from": "id", "to": "customer_id"},
            {"from": "name", "to": "customer_name"},
        ],
    )

    assert result.columns.tolist() == [
        "customer_id",
        "customer_name",
        "status",
    ]

    assert result.iloc[0]["customer_id"] == 1


def test_rename_columns_not_found():
    df = pd.DataFrame({"id": [1]})

    with pytest.raises(
        ValueError,
        match="Columns not found",
    ):
        rename_columns(
            {"df": df},
            [
                {
                    "from": "customer_name",
                    "to": "name",
                }
            ],
        )


# filter columns
def test_filter_columns_success():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["Huy"],
            "email": ["a@test.com"],
        }
    )

    result = filter_columns(
        {"df": df},
        [{"output": ["name", "id"]}],
    )

    assert result.columns.tolist() == [
        "name",
        "id",
    ]

    assert len(result) == 1


def test_filter_columns_not_found():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["Huy"],
        }
    )

    with pytest.raises(
        ValueError,
        match="Columns not found",
    ):
        filter_columns(
            {"df": df},
            [{"output": ["id", "email"]}],
        )


# cast datatype
@pytest.mark.parametrize(
    "column_type,input_values,expected_values",
    [
        (
            "int",
            ["1", "2", "abc"],
            [1, 2, pd.NA],
        ),
        (
            "integer",
            ["1", "2", "abc"],
            [1, 2, pd.NA],
        ),
        (
            "decimal",
            ["1.5", "2.5", "abc"],
            [1.5, 2.5, None],
        ),
        (
            "double",
            ["1.5", "2.5", "abc"],
            [1.5, 2.5, None],
        ),
    ],
)
def test_cast_numeric(
    column_type,
    input_values,
    expected_values,
):
    df = pd.DataFrame({"col": input_values})

    result = cast_datatype(
        df,
        "col",
        {"type": column_type},
    )

    for actual, expected in zip(
        result.tolist(),
        expected_values,
    ):
        if pd.isna(expected):
            assert pd.isna(actual)
        else:
            assert actual == expected


@pytest.mark.parametrize(
    "column_type",
    [
        "date",
        "datetime",
        "timestamp",
    ],
)
def test_cast_datetime_types(column_type):
    df = pd.DataFrame({"col": ["2026-09-09", "invalid"]})

    result = cast_datatype(
        df,
        "col",
        {"type": column_type},
    )

    assert pd.notna(result.iloc[0])
    assert pd.isna(result.iloc[1])


def test_cast_datatype_unsupported():
    df = pd.DataFrame({"col": ["1"]})

    with pytest.raises(
        ValueError,
        match="Unsupported type",
    ):
        cast_datatype(
            df,
            "col",
            {"type": "binary"},
        )
