import pandas as pd
import pytest
from unittest.mock import Mock, patch
from scripts.pandas_etl.commons.validations import validate_l0_to_l1

from scripts.pandas_etl.commons.validations import (
    validate_not_null,
    validate_unique,
    validate_duplicate,
    validate_range,
    validate_format,
    validate_datatype,
)

VALIDATION_MODULE = "scripts.pandas_etl.commons.validations"
# validate_not_null


def test_validate_not_null():
    df = pd.DataFrame(
        {
            "id": [1, None, 3],
        }
    )

    result = validate_not_null(df, "id")

    assert result.tolist() == [True, False, True]


# validate_unique


def test_validate_unique_single_column():
    df = pd.DataFrame(
        {
            "id": [1, 2, 2, None],
        }
    )

    result = validate_unique(df, "id")

    assert result.tolist() == [True, False, False, True]


def test_validate_unique_multiple_columns():
    df = pd.DataFrame(
        {
            "id": [1, 1, 1],
            "name": ["A", "A", "B"],
        }
    )

    result = validate_unique(df, ["id", "name"])

    assert result.tolist() == [False, False, True]


def test_validate_unique_ignore_null():
    df = pd.DataFrame(
        {
            "id": [1, 1, None],
        }
    )

    result = validate_unique(df, "id")

    assert result.tolist() == [False, False, True]


# validate_duplicate


def test_validate_duplicate_full_row():
    df = pd.DataFrame(
        {
            "id": [1, 2, 1],
            "name": ["Huy", "An", "Huy"],
        }
    )

    result = validate_duplicate(df)

    assert result.tolist() == [True, True, False]


def test_validate_duplicate_with_primary_key():
    df = pd.DataFrame(
        {
            "id": [1, 2, 1],
            "name": ["Huy", "An", "Minh"],
        }
    )

    result = validate_duplicate(
        df,
        primary_key=["id"],
    )

    assert result.tolist() == [True, True, False]


def test_validate_duplicate_empty_primary_key():
    df = pd.DataFrame(
        {
            "id": [1, 1],
            "name": ["A", "A"],
        }
    )

    result = validate_duplicate(
        df,
        primary_key=[],
    )

    assert result.tolist() == [True, False]


# validate_range


def test_validate_range():
    df = pd.DataFrame(
        {
            "kpi": [-1, 0, 90, 101, None],
        }
    )

    result = validate_range(
        df,
        column="kpi",
        min=0,
        max=100,
    )

    assert result.tolist() == [
        False,
        True,
        True,
        False,
        True,
    ]


# validate_format


def test_validate_format():
    df = pd.DataFrame(
        {
            "birthday": [
                "2026-09-09",
                "2026/09/09",
                None,
            ]
        }
    )

    result = validate_format(
        df,
        column="birthday",
        format="yyyy-MM-dd",
    )

    assert result.tolist() == [
        True,
        False,
        True,
    ]


# validate_datatype


def test_validate_datatype_string():
    df = pd.DataFrame(
        {
            "value": ["abc", 123, None],
        }
    )

    result = validate_datatype(
        df,
        column="value",
        col_type="string",
    )

    assert result.tolist() == [
        True,
        False,
        True,
    ]


def test_validate_datatype_int():
    df = pd.DataFrame(
        {
            "value": [1, "2", 3.5, None],
        }
    )

    result = validate_datatype(
        df,
        column="value",
        col_type="int",
    )

    assert result.tolist() == [
        True,
        True,
        False,
        True,
    ]


def test_validate_datatype_decimal():
    df = pd.DataFrame(
        {
            "value": [1, "3.14", "abc", None],
        }
    )

    result = validate_datatype(
        df,
        column="value",
        col_type="decimal",
    )

    assert result.tolist() == [
        True,
        True,
        False,
        True,
    ]


def test_validate_datatype_date():
    df = pd.DataFrame(
        {
            "value": [
                "2026-09-09",
                "invalid-date",
                None,
            ]
        }
    )

    result = validate_datatype(
        df,
        column="value",
        col_type="date",
    )

    assert result.tolist() == [
        True,
        False,
        True,
    ]


def test_validate_datatype_unsupported():
    df = pd.DataFrame(
        {
            "value": ["abc"],
        }
    )

    with pytest.raises(
        ValueError,
        match="Unsupported type",
    ):
        validate_datatype(
            df,
            column="value",
            col_type="unknown",
        )


def test_validate_l0_to_l1_calls_validators():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["A"],
            "birthday": ["2026-01-01"],
            "address": ["HCM"],
            "kpi": [10],
            "source_file": ["file.csv"],
            "process_date": ["2026-01-01"],
        }
    )

    config = {
        "columns": [
            {"name": "id", "type": "int"},
        ],
        "validation": [
            {
                "rule": "not_null",
                "column": [
                    "id",
                    "name",
                    "birthday",
                    "address",
                    "kpi",
                    "source_file",
                    "process_date",
                ],
            },
            {
                "rule": "range",
                "column": "kpi",
                "min": 0,
                "max": 100,
            },
            {
                "rule": "duplicate",
                "primary_key": "id",
            },
        ],
    }

    true_mask = pd.Series([True], index=df.index)

    mock_not_null = Mock(return_value=true_mask)
    mock_range = Mock(return_value=true_mask)
    mock_duplicate = Mock(return_value=true_mask)

    with patch(
        f"{VALIDATION_MODULE}.validate_duplicate"
    ) as validate_duplicate_mock, patch(
        f"{VALIDATION_MODULE}.validate_datatype"
    ) as validate_datatype_mock, patch.dict(
        f"{VALIDATION_MODULE}.VALIDATE_FUNCTIONS",
        {
            "not_null": mock_not_null,
            "range": mock_range,
            "duplicate": mock_duplicate,
        },
        clear=False,
    ):
        validate_duplicate_mock.return_value = true_mask
        validate_datatype_mock.return_value = true_mask

        validate_l0_to_l1(df, config)

        validate_duplicate_mock.assert_called_once_with(df)

        validate_datatype_mock.assert_called_once_with(
            df,
            "id",
            "int",
        )

        assert mock_not_null.call_count == 7
        mock_range.assert_called_once_with(
            df,
            column="kpi",
            min=0,
            max=100,
        )
        mock_duplicate.assert_called_once_with(
            df,
            primary_key="id",
        )


def test_validate_l0_to_l1_generates_error_records():
    df = pd.DataFrame(
        {
            "id": [1, None],
            "name": ["A", None],
        }
    )

    config = {
        "columns": [],
        "validation": [
            {
                "rule": "not_null",
                "column": ["id", "name"],
            }
        ],
    }

    valid_df, error_df = validate_l0_to_l1(df, config)

    assert len(valid_df) == 1
    assert len(error_df) == 1

    error_row = error_df.iloc[0]

    assert error_row["_source_index"] == 1

    assert "not_null" in error_row["error_rule"]

    assert "id" in error_row["error_column"]
    assert "name" in error_row["error_column"]

    assert "not_null(id)" in error_row["error_message"]
    assert "not_null(name)" in error_row["error_message"]
