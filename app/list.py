import json
import boto3
import os
from decimal import Decimal

# Always use localstack hostname inside Docker
LOCALSTACK_HOST = os.getenv("LOCALSTACK_HOSTNAME", "localstack")
ENDPOINT_URL = f"http://{LOCALSTACK_HOST}:4566"

# Safe boto3 initialization
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT_URL, region_name="us-east-1")
TABLE_NAME = os.getenv("TABLE_NAME", "images")
table = dynamodb.Table(TABLE_NAME)


# Encoder for Decimal values (DynamoDB returns them)
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    """List all items from DynamoDB 'images' table"""
    try:
        response = table.scan()
        items = response.get("Items", [])

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"  # important for Postman/browser
            },
            "body": json.dumps(items, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error scanning table '{TABLE_NAME}': {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }
