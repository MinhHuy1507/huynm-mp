from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.pandas_etl.commons.db_helper import (
    append_only,
    create_table,
    truncate_and_insert,
    upsert,
)

DATABASE_MODULE = "scripts.pandas_etl.commons.db_helper"


@pytest.fixture
def config():
    return {
        "schema_name": "retail",
        "table_name": "customers",
        "l1_format": "parquet",
        "load_database": {
            "primary_key": "customer_id",
        },
        "columns": [
            {
                "name": "customer_id",
                "db_type": "INTEGER",
                "primary_key": True,
            },
            {
                "name": "name",
                "db_type": "VARCHAR",
                "max_length": 100,
                "not_null": True,
            },
        ],
    }


@pytest.fixture
def mock_database():
    df = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "name": ["John", "Mary"],
        }
    )

    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value

    return df, engine, conn


# create_table


def test_create_table_success(config, mock_database):
    _, engine, conn = mock_database

    with patch(
        f"{DATABASE_MODULE}.get_engine",
        return_value=engine,
    ):
        create_table(config)

    sql = str(conn.execute.call_args.args[0])

    assert "CREATE SCHEMA IF NOT EXISTS retail" in sql
    assert "CREATE TABLE IF NOT EXISTS retail.customers" in sql
    assert "customer_id INTEGER PRIMARY KEY" in sql
    assert "name VARCHAR(100) NOT NULL" in sql


# append_only


def test_append_only_success(config, mock_database):
    df, engine, conn = mock_database

    with patch(
        f"{DATABASE_MODULE}.read_file",
        return_value=df,
    ) as mock_read_file, patch(
        f"{DATABASE_MODULE}.get_engine",
        return_value=engine,
    ), patch.object(
        df,
        "to_sql",
    ) as mock_to_sql:
        append_only(
            "test-bucket",
            "l1/customers.parquet",
            config,
        )

    mock_read_file.assert_called_once_with(
        "test-bucket",
        "l1/customers.parquet",
        "parquet",
    )

    mock_to_sql.assert_called_once_with(
        name="customers",
        schema="retail",
        con=conn,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=10000,
    )


# truncate_and_insert


def test_truncate_and_insert_success(config, mock_database):
    df, engine, conn = mock_database

    with patch(
        f"{DATABASE_MODULE}.read_file",
        return_value=df,
    ), patch(
        f"{DATABASE_MODULE}.get_engine",
        return_value=engine,
    ), patch.object(
        df,
        "to_sql",
    ) as mock_to_sql:
        truncate_and_insert(
            "test-bucket",
            "l1/customers.parquet",
            config,
        )

    truncate_sql = str(conn.execute.call_args.args[0])

    assert truncate_sql == "TRUNCATE TABLE retail.customers"

    mock_to_sql.assert_called_once_with(
        name="customers",
        schema="retail",
        con=conn,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=10000,
    )


# upsert


def test_upsert_success(config, mock_database):
    df, engine, conn = mock_database

    with patch(
        f"{DATABASE_MODULE}.read_file",
        return_value=df,
    ), patch(
        f"{DATABASE_MODULE}.get_engine",
        return_value=engine,
    ), patch(
        f"{DATABASE_MODULE}.datetime",
    ) as mock_datetime, patch.object(
        df,
        "to_sql",
    ) as mock_to_sql:
        mock_datetime.now.return_value.strftime.return_value = "20260923100000"

        upsert(
            "test-bucket",
            "l1/customers.parquet",
            config,
        )

    staging_table = "customers_stg_20260923100000"

    mock_to_sql.assert_called_once_with(
        name=staging_table,
        schema="retail",
        con=conn,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=10000,
    )

    executed_sql = [str(call.args[0]) for call in conn.execute.call_args_list]

    assert any(f"CREATE TABLE retail.{staging_table}" in sql for sql in executed_sql)

    assert any(
        "INSERT INTO retail.customers" in sql
        and 'ON CONFLICT ("customer_id")' in sql
        and '"name" = EXCLUDED."name"' in sql
        for sql in executed_sql
    )

    assert any(
        f"DROP TABLE IF EXISTS retail.{staging_table}" in sql for sql in executed_sql
    )


def test_upsert_always_drops_staging_table(
    config,
    mock_database,
):
    df, engine, conn = mock_database

    with patch(
        f"{DATABASE_MODULE}.read_file",
        return_value=df,
    ), patch(
        f"{DATABASE_MODULE}.get_engine",
        return_value=engine,
    ), patch(
        f"{DATABASE_MODULE}.datetime",
    ) as mock_datetime, patch.object(
        df,
        "to_sql",
        side_effect=Exception("Insert failed"),
    ):
        mock_datetime.now.return_value.strftime.return_value = "20260923100000"

        with pytest.raises(
            Exception,
            match="Insert failed",
        ):
            upsert(
                "test-bucket",
                "l1/customers.parquet",
                config,
            )

    executed_sql = [str(call.args[0]) for call in conn.execute.call_args_list]

    assert any(
        "DROP TABLE IF EXISTS " "retail.customers_stg_20260923100000" in sql
        for sql in executed_sql
    )
