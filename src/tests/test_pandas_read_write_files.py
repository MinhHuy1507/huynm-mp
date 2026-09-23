import pandas as pd
import pytest
from unittest.mock import patch
from io import BytesIO
from pandas.testing import assert_frame_equal

from scripts.pandas_etl.commons.utils import (
    read_file,
    write_file,
)

UTILS_MODULE = "scripts.pandas_etl.commons.utils"


# read_file
def test_read_csv():
    csv_content = b"id,name\n1,John\n2,Mary\n"

    with patch(f"{UTILS_MODULE}.s3") as mock_s3:
        mock_s3.get_object.return_value = {"Body": BytesIO(csv_content)}

        result = read_file(
            "test-bucket",
            "customers.csv",
            "csv",
        )

    expected = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["John", "Mary"],
        }
    )

    assert_frame_equal(
        result,
        expected,
    )


def test_read_parquet():
    expected = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["John", "Mary"],
        }
    )

    parquet_body = BytesIO()
    expected.to_parquet(
        parquet_body,
        index=False,
        engine="pyarrow",
    )

    parquet_body.seek(0)

    with patch(f"{UTILS_MODULE}.s3") as mock_s3:
        mock_s3.get_object.return_value = {"Body": parquet_body}

        result = read_file(
            "test-bucket",
            "customers.parquet",
            "parquet",
        )

    assert_frame_equal(
        result,
        expected,
    )


def test_read_file_unsupported_format():
    with patch(f"{UTILS_MODULE}.s3") as mock_s3:
        mock_s3.get_object.return_value = {"Body": BytesIO(b"test")}

        with pytest.raises(Exception):
            read_file(
                "test-bucket",
                "customers.json",
                "json",
            )


# write_file
def test_write_csv():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["John"],
        }
    )

    with patch(f"{UTILS_MODULE}.s3") as mock_s3:
        write_file(
            df,
            "test-bucket",
            "customers.csv",
            "csv",
        )

    kwargs = mock_s3.put_object.call_args.kwargs

    written_df = pd.read_csv(BytesIO(kwargs["Body"]))

    assert_frame_equal(
        written_df,
        df,
    )


def test_write_parquet():
    df = pd.DataFrame(
        {
            "id": [1],
            "name": ["John"],
        }
    )

    with patch(f"{UTILS_MODULE}.s3") as mock_s3:
        write_file(
            df,
            "test-bucket",
            "customers.parquet",
            "parquet",
        )

    mock_s3.put_object.assert_called_once()

    kwargs = mock_s3.put_object.call_args.kwargs

    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "customers.parquet"

    assert kwargs["ContentType"] == "application/octet-stream"

    assert len(kwargs["Body"]) > 0


def test_write_file_unsupported_format():
    df = pd.DataFrame(
        {
            "id": [1],
        }
    )

    with pytest.raises(Exception):
        write_file(
            df,
            "test-bucket",
            "customers.json",
            "json",
        )
