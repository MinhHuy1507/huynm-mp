from scripts.utils import logger, s3_helper
from scripts.pandas_etl.commons.db_helper import LOAD_STRATEGIES, create_table

logging = logger.get_logger(__name__)


def l1_to_database(schema, table, bucket, process_date):
    logging.info(f"Start processing table {table} from l1/ to database")
    config = s3_helper.load_config(bucket=bucket, layer="l1", table=table)
    key_l1 = f"{config.get('l1_layer')}/{schema}/{table}/{process_date}/{table}.{config.get('l1_format')}"
    load_config = config["load_database"]["load_strategy"]
    load_functions = LOAD_STRATEGIES[load_config]

    create_table(config)
    load_functions(bucket, key_l1, config)

    logging.info(f"\nCompleted loading into database, table {table}")
