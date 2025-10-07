import json
import pytest
import boto3
from moto import mock_aws
from app import delete


@pytest.fixture(scope="function")
def aws_env(monkeypatch):
    """Mock AWS services for each test."""
    with mock_aws():
        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table_name = "images"
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST"
        )

        # Setup S3
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "images-bucket"
        s3.create_bucket(Bucket=bucket_name)

        # Patch environment variables
        monkeypatch.setenv("TABLE_NAME", table_name)
        monkeypatch.setenv("S3_BUCKET", bucket_name)
        monkeypatch.delenv("LOCALSTACK_HOSTNAME", raising=False)

        yield {"table": table, "s3": s3, "bucket": bucket_name}


@pytest.mark.order(7)
def test_delete_existing_item(aws_env):
    """Should delete S3 object + DynamoDB record."""
    table = aws_env["table"]
    s3 = aws_env["s3"]
    bucket = aws_env["bucket"]

    # Seed data
    s3.put_object(Bucket=bucket, Key="x.jpg", Body=b"data")
    table.put_item(Item={"id": "123", "filename": "x.jpg"})

    event = {"pathParameters": {"id": "123"}}
    result = delete.handler(event, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert "deleted" in body
    assert body["key"] == "x.jpg"


@pytest.mark.order(8)
def test_delete_missing_id():
    """Missing path parameter should return 400."""
    result = delete.handler({"pathParameters": {}}, None)
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "error" in body


@pytest.mark.order(9)
def test_delete_not_found(aws_env):
    """Should return 404 if item doesn’t exist."""
    event = {"pathParameters": {"id": "999"}}
    result = delete.handler(event, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 404
    assert "error" in body
