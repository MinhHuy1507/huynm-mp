import psycopg2
from commons.logger import get_logger
from datetime import datetime

logging = get_logger(__name__)


def get_jdbc_url(db_config):
    return f"jdbc:postgresql://{db_config['host']}:{db_config['port']}/{db_config['database']}"


def execute_query(db_config, query):
    conn = psycopg2.connect(
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
    )
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(query)
    cursor.close()
    conn.close()


def get_jdbc_properties(db_config, batch_size):
    return {
        "user": db_config["user"],
        "password": db_config["password"],
        "driver": "org.postgresql.Driver",
        "batchsize": str(batch_size),
        "rewriteBatchedInserts": "true",
        "stringtype": "unspecified",
    }


# CREATE TABLE FUNCTIONS
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


def create_table(db_config, config):
    schema = config["schema_name"]
    table = config["table_name"]
    column_defs = []

    logging.info(f"Creating table {schema}.{table}")

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
    execute_query(db_config, sql)


# LOAD STRATEGIES
def append_only(df, config, db_config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]

    db_load_config = config.get("load_database", {})
    batch_size = db_load_config.get("batch_size", 10000)
    num_partitions = db_load_config.get("num_partitions", 4)

    jdbc_url = get_jdbc_url(db_config)
    properties = get_jdbc_properties(db_config, batch_size)

    logging.info(
        f"Writing to {table_name} with {num_partitions} partitions and batchsize {batch_size}"
    )

    df_append = df.repartition(num_partitions)
    df_append.write.jdbc(
        url=jdbc_url,
        table=f"{schema_name}.{table_name}",
        mode="append",
        properties=properties,
    )


def truncate_and_insert(df, config, db_config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]

    execute_query(db_config, f"TRUNCATE TABLE {schema_name}.{table_name};")
    append_only(df, config, db_config)


def upsert(df, config, db_config):
    schema_name = config["schema_name"]
    table_name = config["table_name"]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stg_table = f"{table_name}_stg_{timestamp}"

    db_load_config = config.get("load_database", {})
    batch_size = db_load_config.get("batch_size", 10000)
    num_partitions = db_load_config.get("num_partitions", 4)
    primary_key = db_load_config.get("primary_key")

    jdbc_url = get_jdbc_url(db_config)
    properties = get_jdbc_properties(db_config, batch_size)

    # create staging table
    execute_query(
        db_config,
        f"""
        DROP TABLE IF EXISTS {schema_name}.{stg_table};
        CREATE TABLE {schema_name}.{stg_table} (LIKE {schema_name}.{table_name});
        """,
    )

    try:
        # write to staging table
        logging.info(
            f"Writing STG table {stg_table} with {num_partitions} partitions and batchsize {batch_size}"
        )
        df_write = df.repartition(num_partitions)
        df_write.write.jdbc(
            url=jdbc_url,
            table=f"{schema_name}.{stg_table}",
            mode="append",
            properties=properties,
        )

        # Merge from staging to main table
        columns = df.columns
        columns_text = ", ".join(
            f'"{col}"' for col in columns
        )  # Bọc ngoặc kép để an toàn với PostgreSQL
        update_cols = ", ".join(
            f'"{col}" = EXCLUDED."{col}"' for col in columns if col != primary_key
        )

        insert_into_main_table = f"""
            INSERT INTO {schema_name}.{table_name} ({columns_text})
            SELECT {columns_text}
            FROM {schema_name}.{stg_table}
            ON CONFLICT ("{primary_key}")
            DO UPDATE SET {update_cols};
        """

        logging.info(f"Merging from STG to Main table: {table_name}")
        execute_query(db_config, insert_into_main_table)

    finally:
        logging.info(f"Cleaning up staging table: {stg_table}")
        execute_query(db_config, f"DROP TABLE IF EXISTS {schema_name}.{stg_table};")


LOAD_STRATEGIES = {
    "upsert": upsert,
    "truncate_and_insert": truncate_and_insert,
    "append_only": append_only,
}
