import json
import uuid
import time
import base64
from requests_toolbelt.multipart import decoder
from common import s3, dynamodb, S3_BUCKET, TABLE_NAME, ensure_bucket, get_header


def _response(status_code, body_dict):
    """Return a valid API Gateway proxy response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"  # important for Postman/browser
        },
        "body": json.dumps(body_dict)
    }


def _parse_multipart(event):
    """Parse multipart/form-data from API Gateway event"""
    body = event.get("body")
    if not body:
        raise ValueError("Empty body")

    headers = event.get("headers", {})
    content_type = get_header(headers, "Content-Type")
    if not content_type or "multipart/form-data" not in content_type.lower():
        raise ValueError("Content-Type must be multipart/form-data")

    raw_body = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("latin-1", "ignore")
    mp = decoder.MultipartDecoder(raw_body, content_type)

    form = {}
    file_part, file_name = None, None

    for part in mp.parts:
        cd = part.headers.get(b"Content-Disposition", b"").decode("utf-8", "ignore")
        name, filename = None, None

        for token in cd.split(";"):
            token = token.strip()
            if token.startswith("name="):
                name = token.split("=", 1)[1].strip('"')
            elif token.startswith("filename="):
                filename = token.split("=", 1)[1].strip('"')

        if not name:
            continue

        if filename:
            file_part = part.content
            file_name = filename
        else:
            # .text decodes the part using charset from headers
            form[name] = part.text

    if not file_part:
        raise ValueError("Missing file field (expected field name='file')")

    return form, file_part, file_name


def handler(event, context):
    """Handle file upload: save to S3 and metadata to DynamoDB"""
    try:
        ensure_bucket()  # ensure the S3 bucket exists

        # ✅ Parse multipart body
        form, file_bytes, original_name = _parse_multipart(event)
        user = form.get("user", "anonymous")
        description = form.get("description", "")

        # ✅ Generate ID and filename
        image_id = str(uuid.uuid4())
        ext = f".{original_name.rsplit('.', 1)[-1]}" if original_name and "." in original_name else ""
        key = f"{image_id}{ext}"

        # ✅ Upload file to S3
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=file_bytes)

        # ✅ Save metadata in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item={
            "id": image_id,
            "filename": key,
            "user": user,
            "description": description,
            "created_at": int(time.time()),
            "original_name": original_name or "",
        })

        return _response(200, {
            "id": image_id,
            "key": key,
            "bucket": S3_BUCKET,
            "message": "Upload successful"
        })

    except Exception as e:
        print(f"❌ Upload handler error: {e}")
        return _response(400, {"error": str(e)})
