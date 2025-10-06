# Image API on LocalStack (Lambda + API Gateway + S3 + DynamoDB)

A minimal project to upload images via **multipart/form-data** (no base64), list them, get a signed download URL, and delete them. Designed for **LocalStack**.

## Endpoints

- `POST /upload` — multipart form: fields `user`, `description`, `file`
- `GET /list` — list items from DynamoDB
- `GET /view/{id}` — returns pre-signed URL for file
- `DELETE /delete/{id}` — deletes file + metadata

## Requirements

- Docker + LocalStack running on `http://localhost:4566`
- AWS CLI in your PATH (`aws --version`)
- Python 3 + `pip`

## Install & Deploy

```bash
# from repo root
pip3 install -r requirements.txt  # optional if you want to run locally
bash deploy.sh
