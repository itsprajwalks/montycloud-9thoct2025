import json
import uuid
import time
import traceback
import base64
from requests_toolbelt.multipart import decoder
from common import s3, dynamodb, S3_BUCKET, TABLE_NAME, ensure_bucket, get_header


def _json_response(status, body_dict):
    """Standardized JSON response."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict),
    }


def handler(event, context):
    print("=== Upload Lambda invoked ===")
    try:
        # ---- Ensure bucket exists ----
        ensure_bucket()

        # ---- Content validation ----
        content_type = get_header(event.get("headers", {}), "Content-Type")
        if not content_type or "multipart/form-data" not in content_type.lower():
            raise ValueError("Invalid Content-Type; must be multipart/form-data")

        body = event.get("body")
        if not body:
            raise ValueError("Empty request body")

        # ---- Decode payload ----
        raw = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("latin-1", "ignore")
        mp = decoder.MultipartDecoder(raw, content_type)

        file_bytes, file_name, form = None, None, {}
        for part in mp.parts:
            cd = part.headers.get(b"Content-Disposition", b"").decode("utf-8", "ignore")

            if "filename=" in cd:
                file_name = cd.split("filename=")[-1].strip().strip('"')
                file_bytes = part.content
            elif "name=" in cd:
                name = cd.split("name=")[-1].strip().strip('"')
                form[name] = part.text

        if not file_bytes:
            raise ValueError("Missing 'file' in multipart form-data")

        # ---- Upload to S3 ----
        image_id = str(uuid.uuid4())
        ext = f".{file_name.rsplit('.', 1)[-1]}" if file_name and "." in file_name else ""
        key = f"{image_id}{ext}"

        print(f"Uploading {file_name} -> s3://{S3_BUCKET}/{key}")
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=file_bytes)
        print("✅ File uploaded to S3")

        # ---- Write metadata to DynamoDB ----
        table = dynamodb.Table(TABLE_NAME)
        item = {
            "id": image_id,
            "filename": key,
            "user": form.get("user", "anonymous"),
            "description": form.get("description", ""),
            "created_at": int(time.time()),
            "original_name": file_name or "",
        }
        table.put_item(Item=item)
        print(f"✅ Metadata stored in DynamoDB: {TABLE_NAME}")

        # ---- Return success ----
        return _json_response(200, {
            "id": image_id,
            "key": key,
            "bucket": S3_BUCKET,
            "message": "Upload successful",
        })

    except Exception as e:
        print("❌ Exception during upload:", str(e))
        traceback.print_exc()
        return _json_response(500, {
            "error": str(e),
            "trace": traceback.format_exc(),
        })
