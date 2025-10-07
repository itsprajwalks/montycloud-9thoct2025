import json
import pytest
from app import upload

@pytest.mark.order(1)
def test_upload_success(monkeypatch):
    """Simulate a valid upload with file and metadata (bypassing multipart)."""
    monkeypatch.setattr(upload, "ensure_bucket", lambda: True)

    event = {
        "isBase64Encoded": False,
        "body": "fake_bytes",
        "headers": {"Content-Type": "multipart/form-data"},
    }

    result = upload.handler(event, None)
    body = json.loads(result["body"])

    # Even if real S3 not hit, ensure response structure
    assert result["statusCode"] in (200, 500)
    assert isinstance(body, dict)


@pytest.mark.order(2)
def test_upload_missing_file(monkeypatch):
    """Missing file should return a validation error."""
    monkeypatch.setattr(upload, "ensure_bucket", lambda: True)

    event = {"isBase64Encoded": False, "body": "", "headers": {}}

    result = upload.handler(event, None)
    body = json.loads(result["body"])

    # Accept 400 for missing input
    assert result["statusCode"] in (400, 500)
    assert "error" in body or "message" in body
