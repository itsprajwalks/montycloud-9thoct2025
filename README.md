# Image API on LocalStack

*(Lambda + API Gateway + S3 + DynamoDB)*

A minimal, serverless image management API that runs entirely on **LocalStack**, mimicking real AWS Lambda behavior.
You can upload images (multipart/form-data, no base64), list stored items, get pre-signed URLs for download, and delete both metadata and files.

---

## Features

* Upload image + metadata (user, description)
* List all uploaded items from DynamoDB
* View an image via pre-signed URL
* Delete image + metadata from both S3 and DynamoDB
* Fully local, offline AWS emulation using LocalStack

---

## Architecture

| Service                   | Purpose                                         |
| ------------------------- | ----------------------------------------------- |
| **API Gateway**           | Routes HTTP requests to Lambda functions        |
| **Lambda (Python)**       | Implements CRUD operations for image management |
| **S3 (LocalStack)**       | Stores the uploaded image files                 |
| **DynamoDB (LocalStack)** | Persists image metadata                         |
| **LocalStack**            | Provides full AWS emulation for local testing   |

All services run locally on:
`http://localhost:4566`

---

## Requirements

* **Docker + LocalStack** running
* **AWS CLI** installed (`aws --version`)
* **Python 3.9+** and `pip`
* **requests-toolbelt** and `boto3` for multipart + S3 access

---

## Setup & Deployment

```bash
# Clone and navigate
git clone https://github.com/itsprajwalks/montycloud-9thoct2025.git
cd montycloud-9thoct2025

# Start LocalStack using Docker Compose
docker-compose up -d

# Install dependencies (optional for local execution)
pip install -r requirements.txt

# Deploy all Lambdas + API Gateway routes
bash deploy.sh
```

Once deployed, your API base URL will look like:

```
http://localhost:4566/_aws/execute-api/<API_ID>/dev
```

---

## API Documentation

### 1. POST /upload

Upload an image with metadata.
**Form fields**:

* `user` — uploader name
* `description` — optional text
* `file` — image file (multipart/form-data)

**Example (curl)**:

```bash
curl -X POST \
  "http://localhost:4566/_aws/execute-api/<API_ID>/dev/upload" \
  -F "user=prajwal" \
  -F "description=Sample image upload" \
  -F "file=@test.jpg"
```

**Response:**

```json
{
  "id": "23d30af0-bf27-4c10-996d-abeec59c4a19",
  "key": "23d30af0-bf27-4c10-996d-abeec59c4a19.jpg",
  "bucket": "images-bucket",
  "message": "Upload successful"
}
```

---

### 2. GET /list

List all uploaded images and metadata from DynamoDB.

**Example:**

```bash
curl "http://localhost:4566/_aws/execute-api/<API_ID>/dev/list"
```

**Response:**

```json
[
  {
    "id": "23d30af0-bf27-4c10-996d-abeec59c4a19",
    "filename": "23d30af0-bf27-4c10-996d-abeec59c4a19.jpg",
    "user": "prajwal",
    "description": "Sample image upload",
    "created_at": 1759753456
  }
]
```

---

### 3. GET /view/{id}

Fetch metadata and a **pre-signed S3 URL** to download or view the image.

**Example:**

```bash
curl "http://localhost:4566/_aws/execute-api/<API_ID>/dev/view/23d30af0-bf27-4c10-996d-abeec59c4a19"
```

**Response:**

```json
{
  "id": "23d30af0-bf27-4c10-996d-abeec59c4a19",
  "filename": "23d30af0-bf27-4c10-996d-abeec59c4a19.jpg",
  "bucket": "images-bucket",
  "url": "http://localhost:4566/images-bucket/23d30af0-bf27-4c10-996d-abeec59c4a19.jpg?AWSAccessKeyId=...",
  "user": "prajwal",
  "description": "Sample image upload",
  "created_at": 1759753456
}
```

Open the `url` field in a browser to download or preview the image.

---

### 4. DELETE /delete/{id}

Deletes both the S3 object and its DynamoDB record.

**Example:**

```bash
curl -X DELETE \
  "http://localhost:4566/_aws/execute-api/<API_ID>/dev/delete/23d30af0-bf27-4c10-996d-abeec59c4a19"
```

**Response:**

```json
{
  "deleted": "23d30af0-bf27-4c10-996d-abeec59c4a19",
  "key": "23d30af0-bf27-4c10-996d-abeec59c4a19.jpg"
}
```

---

## Notes

* Pre-signed URLs are valid for **1 hour**.
* `view.py` automatically replaces the internal container IP (e.g., `192.*`) with `localhost` for accessibility.
* All data is stored persistently inside LocalStack volumes (`./localstack/`).

---

## LocalStack Debug Commands

Check services:

```bash
awslocal s3 ls
awslocal dynamodb scan --table-name images
```

Re-deploy Lambdas:

```bash
bash deploy.sh
```

Clean all resources:

```bash
docker-compose down -v
```

---

## Author

**Prajwal K S**

---

Would you like me to also add a **“Project Folder Structure”** section before the API docs (showing how `/services/task/*.py`, `/deploy.sh`, and `/docker-compose.yml` are organized)? It’ll make it even clearer for readers or interviewers.
