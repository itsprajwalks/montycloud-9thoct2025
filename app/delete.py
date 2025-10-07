import json
from app.common import s3, dynamodb, S3_BUCKET, TABLE_NAME


def handler(event, context):
    """Delete an image entry from S3 and DynamoDB"""
    try:
        # Get image ID from path params
        path_params = event.get("pathParameters") or {}
        image_id = path_params.get("id")
        if not image_id:
            return _response(400, {"error": "Missing id"})

        table = dynamodb.Table(TABLE_NAME)

        # Get existing record
        get_resp = table.get_item(Key={"id": image_id})
        item = get_resp.get("Item")
        if not item:
            return _response(404, {"error": "Not found"})

        key = item.get("filename")

        # Delete from S3 (idempotent)
        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception as s3_err:
            print(f"⚠️  S3 delete warning: {s3_err}")

        # Delete from DynamoDB
        table.delete_item(Key={"id": image_id})

        return _response(200, {"deleted": image_id, "key": key})

    except Exception as e:
        print(f"Delete handler error: {e}")
        return _response(500, {"error": str(e)})


def _response(status_code, body_dict):
    """Utility to build valid API Gateway proxy response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"  # enables browser/Postman JSON display
        },
        "body": json.dumps(body_dict)
    }
