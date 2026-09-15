import boto3
import yaml
from botocore.exceptions import ClientError

s3 = boto3.client("s3")


def check_file_exists(bucket, key):
    s3_client = boto3.client("s3")
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ["404", "403"]:
            return False
        raise e


def get_object(bucket: str, key: str):
    return s3.get_object(Bucket=bucket, Key=key)


def load_config(bucket: str, layer: str, table: str):
    key = f"config/{layer}/{table}.yaml"
    obj = get_object(bucket, key)
    return yaml.safe_load(obj["Body"].read())


def copy_file(bucket_source, key_source, bucket_target, key_target):
    copy_source = {"Bucket": bucket_source, "Key": key_source}
    s3.copy(copy_source, bucket_target, key_target)
