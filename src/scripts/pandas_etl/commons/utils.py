from io import BytesIO
import pandas as pd
from scripts.utils.s3_helper import s3
from scripts.utils import logger

logging = logger.get_logger(__name__)


def read_file(bucket: str, key: str, format: str):
    logging.info(f"Reading file s3://{bucket}/{key} with {format} format")
    response = s3.get_object(Bucket=bucket, Key=key)
    if format == "csv":
        return pd.read_csv(BytesIO(response["Body"].read()))
    elif format == "parquet":
        return pd.read_parquet(BytesIO(response["Body"].read()), engine="pyarrow")
    else:
        logging.error(f"Unsupported format")
        raise


def write_file(df, bucket: str, key: str, format: str):
    logging.info(f"Writing {format} format to s3://{bucket}/{key}")
    if format == "csv":
        body = df.to_csv(index=False, header=True).encode("utf-8")
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/csv")
    elif format == "parquet":
        body = BytesIO()
        df.to_parquet(body, index=False, engine="pyarrow")
        body.seek(0)
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body.getvalue(),
            ContentType="application/octet-stream",
        )
    else:
        logging.error(f"Unsupported format")
        raise
