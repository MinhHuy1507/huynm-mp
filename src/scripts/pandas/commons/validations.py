import pandas as pd
from itertools import islice
from scripts.utils import logger, s3_helper
from scripts.pandas.commons.utils import read_file

logging = logger.get_logger(__name__)


class ValidationError(Exception):
    pass


# RCV to L0
# Validate file exists, file format, file readable, file not empty
def validate_file(context):
    bucket = context["bucket"]
    key_source = context["key_source"]
    key_quarantine = context["key_quarantine"]
    config = context["config"]

    logging.info(f"Validating file: s3://{bucket}/{key_source}")

    # File exists
    if not s3_helper.check_file_exists(bucket, key_source):
        msg = f"File not found - s3://{bucket}/{key_source}"
        logging.error(msg)
        raise ValidationError(msg)

    # File readable, file not empty
    try:
        response = s3_helper.get_object(bucket, key_source)
        iterator = response["Body"].iter_lines()

        first_line = next(iterator, None)
        if not first_line:
            raise ValidationError(f"File empty - {key_source}")

        header_line = first_line.decode("utf-8").strip()
        if not header_line:
            raise ValidationError(f"File has blank header: {key_source}")

        first_data_line = next(
            (l.decode("utf-8").strip() for l in islice(iterator, 10) if l.strip()), None
        )
        if not first_data_line:
            raise ValidationError(
                f"File contains only header, no data records: {key_source}"
            )

        context["header_line"] = header_line
        context["df"] = read_file(bucket, key_source, config["l0_format"])

    except Exception as e:
        s3_helper.copy_file(bucket, key_source, bucket, key_quarantine)
        error_msg = f"File is not readable - {key_source}. Error: {str(e)}"
        logging.error(error_msg)
        raise ValidationError(error_msg)


def validate_schema(context):
    df = context["df"]
    config = context["config"]

    actual = df.columns.tolist()
    expected = [column["name"] for column in config["columns"]]

    if actual != expected:
        s3_helper.copy_file(
            context["bucket"],
            context["key_source"],
            context["bucket"],
            context["key_quarantine"],
        )
        raise ValidationError(f"Schema mismatch. Expected {expected}, got {actual}")


def validate_rcv_to_l0(context):
    config = context["config"]
    for function, required in config["validation"].items():
        if required:
            function_map = VALIDATE_FUNCTIONS[function]
            function_map(context)


# L0 to L1
def validate_not_null(df, column):
    mask = df[column].notna()
    return mask


def validate_unique(df, column):
    is_duplicated = df.duplicated(subset=column, keep=False)

    if isinstance(column, list):
        is_na = df[column].isna().any(axis=1)
    else:
        is_na = df[column].isna()

    mask = ~is_duplicated | is_na
    return mask


def validate_format(df, column, format):
    python_format = format.replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d")
    parsed = pd.to_datetime(df[column], format=python_format, errors="coerce")
    mask = parsed.notna() | df[column].isna()
    return mask


def validate_range(df, column, min, max):
    mask = ((df[column] >= min) & (df[column] <= max)) | df[column].isna()
    return mask


def validate_datatype(df, column, col_type):
    s = df[column]
    if col_type == "string":
        return s.apply(lambda x: isinstance(x, str)) | s.isna()
    elif col_type == "int":
        numeric = pd.to_numeric(s, errors="coerce")
        return numeric.notna() & numeric.mod(1).eq(0) | s.isna()
    elif col_type == "decimal":
        return pd.to_numeric(s, errors="coerce").notna() | s.isna()
    elif col_type in ["date", "datetime"]:
        return pd.to_datetime(s, errors="coerce").notna() | s.isna()
    else:
        raise ValueError(f"Unsupported type: {col_type}")


# Add new row error, for audit (error_records)
def _add_row_error(error_rows, df, idx, rule, params):
    column = params.get("column", "")
    if isinstance(column, list):
        error_columns = column
    elif column:
        error_columns = [column]
    else:
        error_columns = []

    error_message = f"{rule}({','.join(error_columns)})"
    record = error_rows.get(idx)
    if record is None:
        record = {
            "_source_index": idx,
            **df.loc[idx].to_dict(),
            "error_type": "validation",
            "error_rule": set(),
            "error_column": set(),
            "error_message": set(),
        }
        error_rows[idx] = record

    record["error_rule"].add(rule)
    record["error_message"].add(error_message)
    for col in error_columns:
        record["error_column"].add(col)


def validate_l0_to_l1(df, config):
    error_rows = {}

    # Validate datatype
    for col in config["columns"]:
        col_name = col["name"]
        col_type = col["type"]

        if col_name and col_type and col_name in df.columns:
            mask = validate_datatype(df, col_name, col_type)
            failed_idx = df.index[~mask]
            params = {"column": col_name, "type": col_type}
            for idx in failed_idx:
                _add_row_error(error_rows, df, idx, "datatype", params)

    # Validate rules (not null, unique, range, format)
    for validation in config["validation"]:
        rule = validation["rule"]
        function = VALIDATE_FUNCTIONS[rule]
        params = {k: v for k, v in validation.items() if k != "rule"}
        columns = params.get("column", [])

        if isinstance(columns, list) and rule != "unique":
            for col in columns:
                single_col_params = params.copy()
                single_col_params["column"] = col
                mask = function(df, **single_col_params)

                failed_idx = df.index[~mask]
                for idx in failed_idx:
                    _add_row_error(error_rows, df, idx, rule, single_col_params)
        else:
            mask = function(df, **params)
            failed_idx = df.index[~mask]
            for idx in failed_idx:
                _add_row_error(error_rows, df, idx, rule, params)

    error_records = pd.DataFrame(
        [
            {
                **record,
                "error_rule": "; ".join(record["error_rule"]),
                "error_column": "; ".join(record["error_column"]),
                "error_message": "; ".join(record["error_message"]),
            }
            for record in error_rows.values()
        ]
    )

    if not error_records.empty:
        valid_df = df.drop(index=error_records["_source_index"].unique()).copy()
    else:
        valid_df = df.copy()
    return valid_df, error_records


VALIDATE_FUNCTIONS = {
    "validate_file": validate_file,
    "validate_schema": validate_schema,
    "not_null": validate_not_null,
    "unique": validate_unique,
    "format": validate_format,
    "range": validate_range,
}
