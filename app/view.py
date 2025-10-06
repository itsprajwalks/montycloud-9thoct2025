import boto3
import json
import os


def _response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body_dict, default=str)
    }


def handler(event, context):
    try:
        # --- LocalStack endpoint ---
        localstack_host = os.getenv("LOCALSTACK_HOSTNAME", "localstack")
        endpoint_url = f"http://{localstack_host}:4566"

        # --- DynamoDB & S3 clients ---
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1", endpoint_url=endpoint_url)
        s3 = boto3.client("s3", region_name="us-east-1", endpoint_url=endpoint_url)

        table_name = os.getenv("TABLE_NAME", "images")
        bucket_name = os.getenv("S3_BUCKET", "images-bucket")
        table = dynamodb.Table(table_name)

        # --- Extract image ID ---
        image_id = event.get("pathParameters", {}).get("id")
        if not image_id:
            return _response(400, {"error": "Missing id"})

        # --- Fetch item from DynamoDB ---
        resp = table.get_item(Key={"id": image_id})
        item = resp.get("Item")
        if not item:
            return _response(404, {"error": f"Image {image_id} not found"})

        key = item.get("filename")
        if not key:
            return _response(500, {"error": "No filename found in record"})

        # --- Generate a presigned URL (valid 1 hour) ---
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=3600,
        )

        # --- Rewrite internal IP/hostname to localhost for usability ---
        presigned_url = presigned_url.replace(localstack_host, "localhost")

        print(f"✅ Generated presigned URL: {presigned_url}")

        return _response(200, {
            "id": image_id,
            "filename": key,
            "bucket": bucket_name,
            "url": presigned_url,
            "description": item.get("description", ""),
            "user": item.get("user", ""),
            "created_at": item.get("created_at", "")
        })

    except Exception as e:
        print(f"❌ View handler error: {e}")
        return _response(500, {"error": str(e)})
