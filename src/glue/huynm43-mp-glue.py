import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from commons import validations, transformations, utils, logger

logging = logger.get_logger(__name__)


def rcv_to_l0(schema, table, bucket, process_date, spark):
    logging.info(f"Start processing table {table} from rcv/ to l0/")
    config = utils.load_config(bucket=bucket, layer="rcv", table=table)
    target_config = utils.load_config(bucket=bucket, layer="l0", table=table)
    key_rcv = f"{config.get('rcv_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('rcv_format')}"
    key_l0 = f"{target_config.get('l0_layer')}/{schema}/{table}/{process_date}/{table}.{target_config.get('l0_format')}"
    key_quarantine = f"{config.get('quarantine_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('rcv_format')}"

    path_rcv = f"s3://{bucket}/{key_rcv}"
    path_l0 = f"s3://{bucket}/{key_l0}"

    context = {
        "df": None,
        "bucket": bucket,
        "key_source": key_rcv,
        "key_quarantine": key_quarantine,
        "file_path": path_rcv,
        "config": config,
        "target_config": target_config,
        "spark": spark,
    }

    logging.info(f"Validating table {table} from {context['file_path']}")
    validations.validate_rcv_to_l0(context)
    logging.info(f"Transforming table {table} from {context['file_path']}")
    context["df"] = transformations.transform(context)

    utils.write_file(context["df"], path_l0, config["l0_format"])
    logging.info(f"\nCompleted process from rcv to l0, table {table}")


def l0_to_l1(schema, table, bucket, process_date, spark):
    logging.info(f"Start processing table {table} from l0/ to l1/")
    config = utils.load_config(bucket=bucket, layer="l0", table=table)
    target_config = utils.load_config(bucket=bucket, layer="l1", table=table)

    key_l0 = f"{config.get('l0_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('l0_format')}"
    key_l1 = f"{target_config.get('l1_layer')}/{schema}/{table}/{process_date}/{table}.{target_config.get('l1_format')}"
    key_audit = f"{config.get('audit_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('audit_format')}"

    path_l0 = f"s3://{bucket}/{key_l0}"
    path_l1 = f"s3://{bucket}/{key_l1}"
    path_audit = f"s3://{bucket}/{key_audit}"

    context = {
        "df": None,
        "config": config,
        "target_config": target_config,
        "spark": spark,
    }
    context["df"] = utils.read_file(spark, path_l0, config["l0_format"])

    logging.info(f"Validating table {table}")
    valid_records, error_records, df_cached = validations.validate_l0_to_l1(
        context["df"], config
    )

    logging.info(f"Transforming table {table}")
    context["df"] = valid_records
    context["df"] = valid_records
    valid_records = transformations.transform(context)

    utils.write_file(valid_records, path_l1, config["l1_format"])
    if not error_records.isEmpty():
        utils.write_file(error_records, path_audit, config["audit_format"])
    df_cached.unpersist()
    logging.info(f"\nCompleted process from l0 to l1, table {table}")


def main():
    args = getResolvedOptions(
        sys.argv, ["JOB_NAME", "layer", "bucket", "schema", "table", "process_date"]
    )

    layer = args["layer"]
    bucket = args["bucket"]
    schema = args["schema"]
    table = args["table"]
    process_date = args["process_date"]

    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args["JOB_NAME"], args)
    error_message = None

    try:
        process_layers = {"rcv_to_l0": rcv_to_l0, "l0_to_l1": l0_to_l1}
        process_function = process_layers[layer]
        process_function(schema, table, bucket, process_date, spark)
        logging.info("Completed Processing")

    except Exception as e:
        error_message = f"FAILED_AT_[{layer}]: {str(e)}"
        logging.error(error_message)
        raise Exception(error_message)

    finally:
        job.commit()


if __name__ == "__main__":
    main()
