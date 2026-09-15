from itertools import islice
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from commons import logger, utils

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
    file_path = f"s3://{bucket}/{key_source}"
    logging.info(f"Validating file: {file_path}")

    # File exists
    if not utils.check_file_exists(bucket, key_source):
        msg = f"File not found - {file_path}"
        logging.error(msg)
        raise ValidationError(msg)

    # File readable, file not empty
    try:
        response = utils.get_object(bucket, key_source)
        iterator = response["Body"].iter_lines()

        first_line = next(iterator, None)
        if not first_line:
            raise ValidationError(f"File empty - {file_path}")

        header_line = first_line.decode("utf-8").strip()
        if not header_line:
            raise ValidationError(f"File empty - {file_path}")

        first_data_line = next(
            (l.decode("utf-8").strip() for l in islice(iterator, 10) if l.strip()), None
        )
        if not first_data_line:
            raise ValidationError(
                f"File contains only header without data - {file_path}"
            )

        context["header_line"] = header_line
        context["df"] = utils.read_file(
            context["spark"], file_path, config["l0_format"]
        )

    except ValidationError as ve:
        utils.copy_file(bucket, key_source, bucket, key_quarantine)
        logging.error(str(ve))
        raise ve

    except Exception as e:
        utils.copy_file(bucket, key_source, bucket, key_quarantine)
        error_msg = f"File is not readable - {file_path}"
        logging.error(f"{error_msg} | Internal Error: {str(e)}")
        raise ValidationError(error_msg)


def validate_schema(context):
    df = context["df"]
    config = context["config"]

    actual = df.columns
    expected = [col["name"] for col in config["columns"]]

    if actual != expected:
        utils.copy_file(
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
    mask = df[column].isNull()
    return F.when(mask, f"not_null({column})")


def validate_unique(df, columns):
    if not isinstance(columns, list):
        columns = [columns]

    temp_col = f"__err_unique_{'_'.join(columns)}"

    null_condition = F.lit(False)
    for col in columns:
        null_condition = null_condition | F.col(col).isNull()

    df_null = df.filter(null_condition)
    df_non_null = df.filter(~null_condition)

    window_spec = Window.partitionBy(*columns)
    duplicate_condition = F.count("*").over(window_spec) > 1

    df_non_null = df_non_null.withColumn(
        temp_col, F.when(duplicate_condition, f"unique({','.join(columns)})")
    )

    df_null = df_null.withColumn(temp_col, F.lit(None).cast("string"))

    result_df = df_non_null.unionByName(df_null)

    return result_df, temp_col


def validate_duplicate(df, column=None, primary_key=None):
    subset = primary_key if primary_key is not None else column
    if subset is None or subset == []:
        subset = df.columns
    elif not isinstance(subset, list):
        subset = [subset]

    temp_col = f"__err_duplicate_{'_'.join(subset)}"
    duplicate_order = F.monotonically_increasing_id()
    window_spec = Window.partitionBy(*subset).orderBy(duplicate_order)
    is_duplicate = F.row_number().over(window_spec) > 1

    result_df = df.withColumn(
        temp_col,
        F.when(is_duplicate, f"duplicate({','.join(subset)})"),
    )
    return result_df, temp_col


def validate_range(df, column, min, max):
    safe_col = F.expr(f"try_cast({column} as double)")
    mask = ((safe_col >= min) & (safe_col <= max)) | df[column].isNull()
    return F.when(~mask, f"range({column})")


def validate_datatype(df, column, col_type):
    mapping_type = {
        "string": df[column].cast("string").isNotNull(),
        "int": F.expr(f"try_cast({column} as bigint)").isNotNull(),
        "decimal": F.expr(f"try_cast({column} as double)").isNotNull(),
        "date": F.expr(f"try_cast({column} as date)").isNotNull(),
        "datetime": F.expr(f"try_cast({column} as timestamp)").isNotNull(),
    }
    if col_type in mapping_type:
        mask = mapping_type[col_type]
    else:
        raise ValueError(f"Unsupported type: {col_type}")
    return F.when(~mask, f"datatype({column})")


def validate_l0_to_l1(df, config):
    error_exprs = []
    temp_unique_cols = []
    validation_rules = config["validation"]

    df, temp_duplicate_col = validate_duplicate(df)
    error_exprs.append(F.col(temp_duplicate_col))
    temp_unique_cols.append(temp_duplicate_col)

    # Rule datatype
    for col in config["columns"]:
        col_name = col["name"]
        col_type = col["type"]
        if col_name and col_type and col_name in df.columns:
            error_exprs.append(validate_datatype(df, col_name, col_type))

    # Orther rules (unique, not_null, format, range)
    for validation in validation_rules:
        rule = validation["rule"]
        function = VALIDATE_FUNCTIONS[rule]
        params = {k: v for k, v in validation.items() if k != "rule"}
        columns = params.get("column", [])

        if rule == "unique":
            df, temp_col_name = function(df, columns)
            error_exprs.append(F.col(temp_col_name))
            temp_unique_cols.append(temp_col_name)
        elif rule == "duplicate":
            if params.get("primary_key") is not None:
                df, temp_col_name = function(df, **params)
                error_exprs.append(F.col(temp_col_name))
                temp_unique_cols.append(temp_col_name)
        else:
            if isinstance(columns, list):
                for col in columns:
                    single_col_params = params.copy()
                    single_col_params["column"] = col
                    error_exprs.append(function(df, **single_col_params))
            else:
                error_exprs.append(function(df, **params))

    df = df.withColumn(
        "__errors", F.filter(F.array(*error_exprs), lambda x: x.isNotNull())
    )

    df = df.persist()
    valid_df = df.filter(F.size("__errors") == 0)
    error_records = df.filter(F.size("__errors") > 0)
    error_records = (
        error_records.withColumn("error_type", F.lit("validation"))
        .withColumn("error_message", F.array_join("__errors", "; "))
        .withColumn(
            "error_rule",
            F.expr(
                "array_join(transform(__errors, x -> substring_index(x, '(', 1)), '; ')"
            ),
        )
        .withColumn(
            "error_column",
            F.expr(
                "array_join(transform(__errors, x -> replace(substring_index(x, '(', -1), ')', '')), '; ')"
            ),
        )
    )

    # Drop temporary columns used for validation
    cols_to_drop = temp_unique_cols + ["__errors"]
    valid_df = valid_df.drop(*cols_to_drop)
    error_records = error_records.drop(*cols_to_drop)

    return valid_df, error_records, df


VALIDATE_FUNCTIONS = {
    "validate_file": validate_file,
    "validate_schema": validate_schema,
    "not_null": validate_not_null,
    "unique": validate_unique,
    "duplicate": validate_duplicate,
    "range": validate_range,
}
