import pandas as pd
import pytest
from datetime import datetime
from unittest.mock import patch, Mock

from scripts.pandas_etl.commons.transformations import add_columns, transform

TRANSFORM_MODULE = "scripts.pandas_etl.commons.transformations"


def test_add_columns_success():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["John", "Mary"],
        }
    )

    context = {
        "df": df,
        "source_file": "rcv/customers.csv",
    }

    fixed_time = datetime(2026, 9, 9, 10, 0, 0)

    rules = [
        {"name": "process_date"},
        {"name": "source_file"},
    ]

    with patch(f"{TRANSFORM_MODULE}.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time

        result = add_columns(context, rules)

    assert len(result) == 2
    assert result["source_file"].nunique() == 1
    assert result["source_file"].iloc[0] == "rcv/customers.csv"
    assert result["process_date"].iloc[0] == fixed_time


def test_add_columns_unknown_column():
    df = pd.DataFrame({"id": [1]})

    context = {
        "df": df,
        "source_file": "rcv/customers.csv",
    }

    with pytest.raises(
        ValueError,
        match="Unknown column name",
    ):
        add_columns(
            context,
            [{"name": "invalid_column"}],
        )


def test_transform_calls_enabled_transformations():
    context = {
        "df": pd.DataFrame(),
        "config": {
            "transformation": {
                "split_name": [
                    {
                        "from": "name",
                        "to": ["first_name", "last_name"],
                    }
                ],
                "split_address": [
                    {
                        "from": "address",
                        "to": ["address", "address_province"],
                    }
                ],
                "rename": [
                    {
                        "from": "id",
                        "to": "customer_id",
                    }
                ],
                "filter_columns": [
                    {
                        "output": [
                            "customer_id",
                            "first_name",
                            "last_name",
                        ]
                    }
                ],
            }
        },
        "target_config": {"columns": []},
    }

    with patch(
        f"{TRANSFORM_MODULE}.TRANSFORM_FUNCTIONS",
        {
            "split_name": Mock(side_effect=lambda ctx, rules: ctx["df"]),
            "split_address": Mock(side_effect=lambda ctx, rules: ctx["df"]),
            "rename": Mock(side_effect=lambda ctx, rules: ctx["df"]),
            "filter_columns": Mock(side_effect=lambda ctx, rules: ctx["df"]),
        },
    ) as functions:

        transform(context)

        functions["split_name"].assert_called_once()
        functions["split_address"].assert_called_once()
        functions["rename"].assert_called_once()
        functions["filter_columns"].assert_called_once()


def test_transform_add_missing_target_column():
    context = {
        "df": pd.DataFrame(
            {
                "customer_id": [1],
            }
        ),
        "config": {},
        "target_config": {
            "columns": [
                {
                    "name": "customer_id",
                    "type": "int",
                },
                {
                    "name": "first_name",
                    "type": "string",
                },
            ]
        },
    }

    with patch(
        f"{TRANSFORM_MODULE}.cast_datatype",
        side_effect=lambda df, col, cfg: df[col],
    ):
        result = transform(context)

        assert list(result.columns) == [
            "customer_id",
            "first_name",
        ]

        assert pd.isna(result.loc[0, "first_name"])
