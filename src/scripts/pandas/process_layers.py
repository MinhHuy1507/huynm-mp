import argparse
from datetime import datetime

from scripts.pandas.commons import utils, transformations, validations
from scripts.utils import logger, s3_helper

logging = logger.get_logger(__name__)


def rcv_to_l0(schema, table, bucket, process_date):
    logging.info(f"Start processing table {table} from rcv/ to l0/")
    config = s3_helper.load_config(bucket=bucket, layer="rcv", table=table)
    key_rcv = f"{config.get('rcv_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('rcv_format')}"
    key_l0 = f"{config.get('l0_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('l0_format')}"
    key_quarantine = f"{config.get('quarantine_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('rcv_format')}"
    source_file = f"s3://{bucket}/{key_rcv}"

    context = {
        "bucket": bucket,
        "key_source": key_rcv,
        "key_quarantine": key_quarantine,
        "config": config,
        "source_file": source_file,
        "df": None,
    }

    logging.info(f"Validating table {table} from {context['key_source']}")
    validations.validate_rcv_to_l0(context)
    logging.info(f"Transforming table {table} from {context['key_source']} to {key_l0}")
    context["df"] = transformations.transform(context)

    logging.info(f"After processing")
    logging.info(context["df"])

    utils.write_file(context["df"], bucket, key_l0, format=config["l0_format"])
    logging.info(f"\nCompleted process from rcv to l0, table {table}")


def l0_to_l1(schema, table, bucket, process_date):
    logging.info(f"Start processing table {table} from l0/ to l1/")
    config = s3_helper.load_config(bucket=bucket, layer="l0", table=table)
    key_l0 = f"{config.get('l0_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('l0_format')}"
    key_l1 = f"{config.get('l1_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('l1_format')}"
    key_audit = f"{config.get('audit_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('audit_format')}"

    context = {
        "df": None,
        "layer": "l0_to_l1",
        "config": config,
    }

    context["df"] = utils.read_file(bucket, key_l0, format=config["l0_format"])

    logging.info(f"Validating table {table}")
    valid_records, error_records = validations.validate_l0_to_l1(context["df"], config)

    logging.info(f"Transforming table {table}")
    context["df"] = valid_records
    valid_records = transformations.transform(context)

    logging.info(f"After processing")
    logging.info("=== Error records")
    logging.info(error_records)
    logging.info("=== Valid records")
    logging.info(valid_records)

    utils.write_file(valid_records, bucket, key_l1, format=config["l1_format"])
    if not error_records.empty:
        utils.write_file(
            valid_records, bucket, key_audit, format=config["audit_format"]
        )

    logging.info(f"\nCompleted process from l0 to l1, table {table}")


# For airflow
def process(layer, schema, table, bucket, process_date):
    try:
        process_layers = {"rcv_to_l0": rcv_to_l0, "l0_to_l1": l0_to_l1}
        process_function = process_layers[layer]
        process_function(schema, table, bucket, process_date)
        logging.info("Completed Processing")
    except Exception as e:
        error_message = f"FAILED_AT_[{layer}]: {str(e)}"
        logging.error(error_message)
        raise Exception(error_message)


# Test
def test(event, context):
    table = event.get("table")
    process_date = event.get("process_date")
    schema = event.get("schema")
    bucket = event.get("bucket")
    rcv_to_l0(schema, table, bucket, process_date)
    l0_to_l1(schema, table, bucket, process_date)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the data transformation pipeline")
    parser.add_argument(
        "--bucket",
        default="huynm43-mock-project-s3-414061810527-us-east-1-an",
        help="S3 bucket name",
    )
    parser.add_argument("--schema", default="retail", help="Schema name")
    parser.add_argument(
        "--table",
        nargs="?",
        default="customers",
        help="Table to transform (customers, products, orders, province)",
    )
    parser.add_argument(
        "--process-date",
        default=datetime.now().strftime("%Y/%m/%d"),
        help="Date partition to process (default: current date)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    mock_event = {
        "bucket": args.bucket,
        "schema": args.schema,
        "table": args.table,
        "process_date": args.process_date,
    }
    mock_context = {}

    test(mock_event, mock_context)
