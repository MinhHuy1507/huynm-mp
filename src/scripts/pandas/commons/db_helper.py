from ec2_airflow.scripts.pandas.commons.utils import read_file
from sqlalchemy import create_engine, text
from scripts.utils.configs import pg_conn


def get_engine():
    return create_engine(pg_conn, pool_pre_ping=True)


def mapping_constraint(key, value, col):
    CONSTRAINT_MAPPING = {
        "not_null": lambda v, c: "NOT NULL" if v else None,
        "primary_key": lambda v, c: "PRIMARY KEY" if v else None,
        "unique": lambda v, c: "UNIQUE" if v else None,
        "range": lambda v, c: (
            f"CHECK ({c['name']} BETWEEN {v[0]} AND {v[1]})" if v else None
        ),
        "default": lambda v, c: f"DEFAULT {v}",
    }
    handler = CONSTRAINT_MAPPING.get(key)

    if not handler:
        return None
    return handler(value, col)


def create_table(config):
    schema = config["schema_name"]
    table = config["table_name"]
    column_defs = []

    for col in config["columns"]:
        parts = [col["name"], col["db_type"]]
        for key, value in col.items():
            expr = mapping_constraint(key, value, col)
            if expr:
                parts.append(expr)
        column_defs.append(" ".join(parts))

    columns_sql = ",\n".join(column_defs)
    sql = f"""
    CREATE SCHEMA IF NOT EXISTS {schema};

    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        {columns_sql}
    );
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(engine))


def append_only(bucket, key, config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]

    df = read_file(bucket, key, config["l1_format"])
    engine = get_engine()
    with engine.begin() as conn:
        df.to_sql(
            name=table_name,
            schema=schema_name,
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=10000,
        )


def truncate_and_insert(bucket, key, config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]

    df = read_file(bucket, key, config["l1_format"])
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(f"TRUNCATE TABLE {schema_name}.{table_name}")
        df.to_sql(
            name=table_name,
            schema=schema_name,
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=10000,
        )


def upsert(bucket, key, config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]

    df = read_file(bucket, key, config["l1_format"])

    columns = df.columns.to_list()
    columns_text = ", ".join(columns)
    primary_key = config["load_database"]["primary_key"]
    update_cols = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in columns if col != primary_key
    )
    insert_into_main_table = f"""
        INSERT INTO {schema_name}.{table_name} ({columns_text})
        SELECT {columns_text}
        FROM {schema_name}.{table_name}_stg
        ON CONFLICT ({primary_key})
        DO UPDATE
        SET {update_cols};
    """

    create_temp_table = f"""
        DROP TABLE IF EXISTS {schema_name}.{table_name}_stg;
        CREATE TABLE {schema_name}.{table_name}_stg (LIKE {schema_name}.{table_name});
    """

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(create_temp_table))
        df.to_sql(
            name=f"{table_name}_stg",
            schema=schema_name,
            con=conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=10000,
        )
        conn.execute(text(insert_into_main_table))


LOAD_STRATEGIES = {
    "upsert": upsert,
    "truncate_and_insert": truncate_and_insert,
    "append_only": append_only,
}
