import boto3
import json
import os


def _response(status_code, body_dict):
    """Standard API Gateway JSON response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict, default=str),
    }


def handler(event, context):
    try:
        # ✅ Use LocalStack endpoint *only if available*
        localstack_host = os.getenv("LOCALSTACK_HOSTNAME")
        endpoint_url = f"http://{localstack_host}:4566" if localstack_host else None

        # ✅ Initialize clients
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1", endpoint_url=endpoint_url)
        s3 = boto3.client("s3", region_name="us-east-1", endpoint_url=endpoint_url)

        table_name = os.getenv("TABLE_NAME", "images")
        bucket_name = os.getenv("S3_BUCKET", "images-bucket")
        table = dynamodb.Table(table_name)

        image_id = event.get("pathParameters", {}).get("id")
        if not image_id:
            return _response(400, {"error": "Missing id"})

        # ✅ Lookup record safely
        resp = table.get_item(Key={"id": image_id})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": "Not found"})

        key = item["filename"]

        # ✅ Safe delete from S3
        try:
            s3.delete_object(Bucket=bucket_name, Key=key)
        except Exception:
            pass

        # ✅ Delete from DynamoDB
        table.delete_item(Key={"id": image_id})

        return _response(200, {"deleted": image_id, "key": key})

    except Exception as e:
        print(f"Delete handler error: {e}")
        return _response(500, {"error": str(e)})
