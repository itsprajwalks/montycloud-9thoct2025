import boto3
import json
import os


def _response(status_code, body_dict):
    """Standard API Gateway JSON response"""
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
        # ✅ Use correct hostname for LocalStack networking
        localstack_host = os.getenv("LOCALSTACK_HOSTNAME", "localstack")
        endpoint_url = f"http://{localstack_host}:4566"

        # ✅ Initialize DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1", endpoint_url=endpoint_url)
        table_name = os.getenv("TABLE_NAME", "images")
        table = dynamodb.Table(table_name)

        # ✅ Get image id from path params
        image_id = event.get("pathParameters", {}).get("id")
        if not image_id:
            return _response(400, {"error": "Missing id"})

        # ✅ Fetch item from DynamoDB
        resp = table.get_item(Key={"id": image_id})
        item = resp.get("Item")

        if not item:
            return _response(404, {"error": "Not found"})

        return _response(200, item)

    except Exception as e:
        print(f"❌ View handler error: {e}")
        return _response(500, {"error": str(e)})
