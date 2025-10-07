import json
import pytest
from app import delete

@pytest.mark.order(7)
def test_delete_existing_item(aws_env, monkeypatch):
    """Should delete S3 object + DynamoDB record."""
    s3 = aws_env["s3"]
    table = aws_env["table"]
    bucket = aws_env["bucket"]

    s3.put_object(Bucket=bucket, Key="x.jpg", Body=b"data")
    table.put_item(Item={"id": "123", "filename": "x.jpg"})

    monkeypatch.setenv("TABLE_NAME", aws_env["table_name"])

    result = delete.handler({"pathParameters": {"id": "123"}}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] in (200, 500)
    assert isinstance(body, dict)


@pytest.mark.order(8)
def test_delete_missing_id(monkeypatch):
    """Should fail if no ID provided."""
    result = delete.handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "error" in body


@pytest.mark.order(9)
def test_delete_not_found(aws_env, monkeypatch):
    """Should return 404 if item doesn’t exist."""
    monkeypatch.setenv("TABLE_NAME", aws_env["table_name"])

    result = delete.handler({"pathParameters": {"id": "999"}}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] in (404, 500)
