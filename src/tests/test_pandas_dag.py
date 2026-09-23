TABLE_ENUM = [
    "customers",
    "products",
    "orders",
    "province",
]

PARAMS = {
    "bucket_name": "huynm43-mock-project-s3-414061810527-us-east-1-an",
    "schema_name": "retail",
    "table_name": "customers",
    "region_name": "us-east-1",
    "dynamo_table_name": "huynm43-mp-dynamo",
    "sns_topic_arn": "arn:aws:sns:us-east-1:414061810527:huynm43-mp-sns",
}


def test_pipeline_params():
    assert PARAMS["bucket_name"] == (
        "huynm43-mock-project-s3-414061810527-us-east-1-an"
    )

    assert PARAMS["schema_name"] == "retail"

    assert PARAMS["table_name"] == "customers"

    assert PARAMS["region_name"] == "us-east-1"

    assert PARAMS["dynamo_table_name"] == "huynm43-mp-dynamo"

    assert PARAMS["sns_topic_arn"] == (
        "arn:aws:sns:us-east-1:414061810527:huynm43-mp-sns"
    )

    assert TABLE_ENUM == [
        "customers",
        "products",
        "orders",
        "province",
    ]
