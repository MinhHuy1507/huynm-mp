from datetime import datetime
import pandas as pd
from scripts.utils import logger

logging = logger.get_logger(__name__)


def transform(context):
    config = context["config"]
    transformations = config.get("transformation", {})

    for transform_name, transform_rules in transformations.items():
        function = TRANSFORM_FUNCTIONS[transform_name]
        context["df"] = function(context, transform_rules)

    df_transformed = context["df"].copy()
    target_config = context["target_config"]

    for column_config in target_config.get("columns", []):
        column_name = column_config["name"]

        if column_name not in df_transformed.columns:
            df_transformed[column_name] = pd.NA

        df_transformed[column_name] = cast_datatype(
            df_transformed, column_name, column_config
        )

    target_cols = [c["name"] for c in target_config.get("columns", [])]
    df_transformed = df_transformed[target_cols]

    context["df"] = df_transformed
    return context["df"]


def cast_datatype(df, column, column_config):
    col_type = column_config["type"].lower()
    date_format = column_config.get("format")

    def parse_date(series, as_datetime_only=False):
        if date_format:
            fmt = (
                date_format.replace("YYYY", "%Y")
                .replace("MM", "%m")
                .replace("DD", "%d")
            )
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        else:
            parsed = pd.to_datetime(series, errors="coerce")

        return parsed.dt.normalize() if as_datetime_only else parsed.dt.date

    mapping_type = {
        "string": lambda s: s.astype("string"),
        "int": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
        "integer": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
        "decimal": lambda s: pd.to_numeric(s, errors="coerce"),
        "double": lambda s: pd.to_numeric(s, errors="coerce"),
        "date": lambda s: pd.to_datetime(s, errors="coerce").dt.normalize(),
        "datetime": lambda s: pd.to_datetime(s, errors="coerce"),
        "timestamp": lambda s: pd.to_datetime(s, errors="coerce"),
    }

    if col_type in mapping_type:
        if col_type == "date" and date_format:
            return parse_date(df[column], as_datetime_only=True)

        return mapping_type[col_type](df[column])
    else:
        raise ValueError(f"Unsupported type: {col_type} in column {column}")


# rcv_to_l0
def add_columns(context, transform_rules):
    df = context["df"]
    path = context["source_file"]

    logging.info(f"Adding columns to DataFrame: {transform_rules}")
    columns = {"process_date": datetime.now(), "source_file": path}
    for column in transform_rules:
        column_name = column["name"]
        if column_name not in columns:
            logging.error(f"Unknown column name: {column_name}")
            raise ValueError(f"Unknown column name: {column_name}")
        df[column_name] = columns[column_name]

    return df


# l0_to_l1
## customers
def split_customers_address(context, transform_rules):
    df = context["df"]
    logging.info(f"Splitting address column")

    for rule in transform_rules:
        source = rule["from"]
        first_col, second_col = rule["to"]

        def normalize_address(value):
            if pd.isna(value):
                return None, None

            parts = [part.strip() for part in str(value).split(",")]
            parts = [" ".join(part.split()) for part in parts if part.strip()]
            if not parts:
                return None, None
            address = ", ".join(parts)
            province = parts[-1] if len(parts) > 1 else None
            return address, province

        normalized = df[source].apply(normalize_address)
        df[first_col] = normalized.str[0]
        df[second_col] = normalized.str[1]
    return df


def split_customers_name(context, transform_rules):
    df = context["df"]
    logging.info(f"Splitting name column")

    for rule in transform_rules:
        source = rule["from"]
        first_col, last_col = rule["to"]

        normalized = (
            df[source]
            .astype("string")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .replace("", pd.NA)
        )
        has_multiple_words = normalized.str.contains(" ", na=False)
        splits = normalized.str.rsplit(" ", n=1)

        df[first_col] = splits.str[-1].where(normalized.notna())
        df[first_col] = df[first_col].where(has_multiple_words, normalized)
        df[last_col] = splits.str[0].where(has_multiple_words)

    return df


def rename_columns(context, transform_rules):
    df = context["df"]
    columns = df.columns.tolist()

    logging.info(f"Renaming columns")
    mapping = {}
    missing_columns = []
    for rule in transform_rules:
        if rule["from"] not in columns:
            missing_columns.append(rule["from"])
        mapping[rule["from"]] = rule["to"]

    if missing_columns:
        logging.error(f"Columns not found: {missing_columns}")
        raise ValueError(f"Columns not found: {missing_columns}")

    df = df.rename(columns=mapping)
    return df


def filter_columns(context, transform_rules):
    df = context["df"]
    logging.info(f"Filtering columns")

    for rule in transform_rules:
        output_columns = rule["output"]
        missing_columns = [
            column for column in output_columns if column not in df.columns
        ]
        if missing_columns:
            logging.error(f"Columns not found: {missing_columns}")
            raise ValueError(f"Columns not found: {missing_columns}")

        df = df[output_columns]

    return df


TRANSFORM_FUNCTIONS = {
    "add_column": add_columns,
    "split_name": split_customers_name,
    "split_address": split_customers_address,
    "rename": rename_columns,
    "filter_columns": filter_columns,
}
