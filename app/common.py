import boto3
import os

# === Configuration ===
S3_BUCKET = os.getenv("S3_BUCKET", "images-bucket")
TABLE_NAME = os.getenv("TABLE_NAME", "images")

# Inside Lambda (LocalStack), LOCALSTACK_HOSTNAME is automatically set
LOCALSTACK_HOST = os.getenv("LOCALSTACK_HOSTNAME", "localstack")
LOCALSTACK_URL = f"http://{LOCALSTACK_HOST}:4566"

# === Clients ===
s3 = boto3.client("s3", endpoint_url=LOCALSTACK_URL, region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", endpoint_url=LOCALSTACK_URL, region_name="us-east-1")


# === Helpers ===
def ensure_bucket():
    """Ensure the target S3 bucket exists (idempotent)."""
    try:
        existing = s3.list_buckets().get("Buckets", [])
        if not any(b["Name"] == S3_BUCKET for b in existing):
            s3.create_bucket(Bucket=S3_BUCKET)
            print(f"Created bucket: {S3_BUCKET}")
        else:
            print(f"Bucket already exists: {S3_BUCKET}")
    except Exception as e:
        print(f"Failed to verify/create bucket {S3_BUCKET}: {e}")


def get_header(headers, key):
    """Case-insensitive header lookup."""
    for k, v in (headers or {}).items():
        if k.lower() == key.lower():
            return v
    return None
