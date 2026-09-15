from pyspark.sql import functions as F
from pyspark.sql.functions import col, lit, to_date


def transform(context):
    config = context["config"]
    transformations = config.get("transformation", {})

    for transform_name, transform_rules in transformations.items():
        function = TRANSFORM_FUNCTIONS[transform_name]
        context["df"] = function(context, transform_rules)

    df = context["df"]
    target_config = context["target_config"]

    select_exprs = []
    for column_config in target_config.get("columns", []):
        column_name = column_config["name"]

        if column_name not in df.columns:
            base_col = lit(None)
        else:
            base_col = col(column_name)

        select_exprs.append(cast_datatype(column_name, base_col, column_config))

    context["df"] = df.select(*select_exprs)
    return context["df"]


def cast_datatype(column_name, base_col, column_config):
    col_type = column_config["type"].lower()
    date_format = column_config.get("format")

    mapping_type = {
        "string": "string",
        "int": "bigint",
        "integer": "bigint",
        "decimal": "double",
        "double": "double",
        "date": "date",
        "datetime": "timestamp",
        "timestamp": "timestamp",
    }

    if col_type in mapping_type:
        if col_type == "date" and date_format:
            fmt = date_format.replace("YYYY", "yyyy").replace("DD", "dd")
            return to_date(base_col, fmt).alias(column_name)

        return base_col.cast(mapping_type[col_type]).alias(column_name)
    else:
        raise ValueError(f"Unsupported type: {col_type} in column {column_name}")


# rcv_to_l0
def add_columns(context, transform_rules):
    df = context["df"]
    path = context["file_path"]

    COLUMNS = {"process_date": F.current_timestamp(), "source_file": F.lit(path)}
    new_columns = dict()

    for column in transform_rules:
        col_name = column["name"]
        if col_name in COLUMNS:
            new_columns[col_name] = COLUMNS[col_name]
        else:
            raise ValueError(f"Unknown column name: {col_name}")

    if new_columns:
        df = df.withColumns(new_columns)

    return df


# l0_to_l1
## customers
def split_customers_address(context, transform_rules):
    df = context["df"]
    new_columns = {}

    for rule in transform_rules:
        source = rule["from"]
        address_col, province_col = rule["to"]

        cleaned = F.trim(F.regexp_replace(F.col(source), r"(^\s*,+)|(,+\s*$)", ""))
        parts = F.filter(
            F.transform(F.split(cleaned, ","), lambda part: F.trim(part)),
            lambda part: part != "",
        )

        normalized_address = F.when(
            F.col(source).isNull() | (F.size(parts) == 0),
            F.lit(None).cast("string"),
        ).otherwise(F.concat_ws(", ", parts))
        new_columns[province_col] = F.when(F.size(parts) > 1, F.element_at(parts, -1))
        new_columns[address_col] = normalized_address

    return df.withColumns(new_columns)


def split_customers_name(context, transform_rules):
    df = context["df"]
    new_columns = {}

    for rule in transform_rules:
        source = rule["from"]
        first_col, last_col = rule["to"]

        normalized = F.regexp_replace(F.trim(F.col(source)), r"\s+", " ")
        parts = F.split(normalized, " ")
        new_columns[first_col] = F.when(
            F.size(parts) > 1, F.element_at(parts, -1)
        ).otherwise(normalized)
        new_columns[last_col] = F.when(
            F.size(parts) > 1,
            F.array_join(F.slice(parts, 1, F.size(parts) - 1), " "),
        )

    return df.withColumns(new_columns)


def rename_columns(context, transform_rules):
    df = context["df"]

    mapping = {}
    missing_columns = []
    for rule in transform_rules:
        if rule["from"] not in df.columns:
            missing_columns.append(rule["from"])
        mapping[rule["from"]] = rule["to"]

    if missing_columns:
        raise ValueError(f"Columns not found: {missing_columns}")

    df = df.withColumnsRenamed(mapping)
    return df


def filter_columns(context, transform_rules):
    df = context["df"]

    for rule in transform_rules:
        output_columns = rule["output"]
        missing_columns = [
            column for column in output_columns if column not in df.columns
        ]
        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")

    df = df.select(output_columns)
    return df


TRANSFORM_FUNCTIONS = {
    "add_column": add_columns,
    "split_name": split_customers_name,
    "split_address": split_customers_address,
    "rename": rename_columns,
    "filter_columns": filter_columns,
}
