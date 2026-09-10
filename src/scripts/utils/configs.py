import os
import boto3
from utils.logger import get_logger

logging = get_logger(__name__)

pg_host = os.environ.get("POSTGRES_HOST")
pg_port = os.environ.get("POSTGRES_PORT")
pg_user = os.environ.get("POSTGRES_USER")
pg_database = os.environ.get("POSTGRES_DB")
pg_password = os.environ.get("POSTGRES_PASSWORD")
pg_conn = (
    f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
)


def upload_secret_to_s3(bucket_name, s3_key, secret_value):
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket_name, Key=s3_key, Body=secret_value)
    logging.info(f"Uploaded secret to s3://{bucket_name}/{s3_key}")


def delete_secret_from_s3(bucket_name, s3_key):
    s3 = boto3.client("s3")
    s3.delete_object(Bucket=bucket_name, Key=s3_key)
    logging.info(f"Deleted secret from s3://{bucket_name}/{s3_key}")
