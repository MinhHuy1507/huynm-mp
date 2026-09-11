from datetime import datetime
import numpy as np
from scripts.utils import logger

logging = logger.get_logger(__name__)

def transform(context):
    df = context["df"]
    config = context["config"]

    if df.empty:
        return df

    transformations = config["transformation"]
    for transform_name, transform_rules in transformations.items():
        function = TRANSFORM_FUNCTIONS[transform_name]
        context["df"] = function(context, transform_rules)

    return context["df"]


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

        cleaned_source = df[source].str.strip(" ,").replace("", None)

        splits = cleaned_source.str.rsplit(",", n=1)

        df[first_col] = splits.str[0].str.strip().replace({np.nan: None})
        df[second_col] = splits.str[-1].str.strip().replace({np.nan: None})

    return df


def split_customers_name(context, transform_rules):
    df = context["df"]
    logging.info(f"Splitting name column")

    for rule in transform_rules:
        source = rule["from"]
        first_col, last_col = rule["to"]

        splits = df[source].str.strip().str.split(r"\s+")

        df[last_col] = splits.str[-1].replace({np.nan: None})
        df[first_col] = splits.str[:-1].str.join(" ")

    return df


def rename_columns(context, transform_rules):
    df = context["df"]
    columns = df.columns.tolist()

    logging.info(f"Renaming columns")
    mapping = {}
    for rule in transform_rules:
        if rule["from"] not in columns:
            logging.error(f"Columns not found: {columns}")
            raise ValueError(f"Columns not found: {columns}")
        mapping[rule["from"]] = rule["to"]

    df = df.rename(columns=mapping)
    return df


def filter_columns(context, transform_rules):
    df = context["df"]
    logging.info(f"Filtering columns")

    for rule in transform_rules:
        output_columns = rule["output"]

        df = df[output_columns]

    return df


TRANSFORM_FUNCTIONS = {
    "add_column": add_columns,
    "split_name": split_customers_name,
    "split_address": split_customers_address,
    "rename": rename_columns,
    "filter_columns": filter_columns,
}
