import boto3
import os

S3_BUCKET = os.getenv("S3_BUCKET", "images-bucket")
TABLE_NAME = os.getenv("TABLE_NAME", "images")
LOCALSTACK_URL = os.getenv("LOCALSTACK_URL", "http://host.docker.internal:4566")

# Initialize clients
s3 = boto3.client("s3", endpoint_url=LOCALSTACK_URL, region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", endpoint_url=LOCALSTACK_URL, region_name="us-east-1")

def ensure_bucket():
    """Create the S3 bucket if it does not exist"""
    try:
        existing = s3.list_buckets()
        if not any(b["Name"] == S3_BUCKET for b in existing.get("Buckets", [])):
            s3.create_bucket(Bucket=S3_BUCKET)
    except Exception as e:
        print(f"⚠️ ensure_bucket error: {e}")

def get_header(headers, key):
    """Case-insensitive header lookup"""
    for k, v in headers.items():
        if k.lower() == key.lower():
            return v
    return None
