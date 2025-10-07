import pytest
import boto3
from moto import mock_aws

@pytest.fixture(scope="function")
def aws_env():
    """
    Creates a clean mock AWS environment for every test using Moto.
    Includes S3 + DynamoDB.
    """
    with mock_aws():
        # Setup S3
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "images-bucket"
        s3.create_bucket(Bucket=bucket_name)

        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table_name = "images"
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        yield {
            "s3": s3,
            "table": table,
            "bucket": bucket_name,
            "table_name": table_name,
        }
