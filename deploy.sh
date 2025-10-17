#!/bin/bash
set -e

# --- CONFIG ---
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
AWS="${AWS:-aws}"                 # let env override if you want
ENDPOINT="http://localhost:4566"
REGION="us-east-1"

ROOT_DIR="$(pwd)"
BUILD_DIR="${ROOT_DIR}/build"
DEPS_DIR="${BUILD_DIR}/deps"      # deps installed once here
REQ_FILE="${ROOT_DIR}/requirements.txt"

echo "🔍 Using AWS CLI:"
$AWS --version || { echo "AWS CLI not found. Exiting."; exit 1; }

# --- CLEAN ---
echo "🧹 Cleaning..."
rm -rf "$BUILD_DIR" *.zip || true
mkdir -p "$DEPS_DIR"

# --- REQUIREMENTS ---
if [ ! -f "$REQ_FILE" ]; then
  cat > "$REQ_FILE" <<EOF
boto3==1.34.86
requests==2.31.0
requests-toolbelt==1.0.0
EOF
fi

echo "📦 Installing dependencies to ${DEPS_DIR} ..."
pip3 install -r "$REQ_FILE" -t "$DEPS_DIR" --no-cache-dir >/dev/null

# --- HELPER: build one function zip with full app/ package preserved ---
build_zip () {
  local fn="$1"        # upload | list | view | delete
  local out_zip="${ROOT_DIR}/${fn}.zip"

  echo "📦 Bundling ${fn} -> ${out_zip}"

  rm -rf "${BUILD_DIR}/${fn}"
  mkdir -p "${BUILD_DIR}/${fn}"

  # copy deps
  rsync -a "${DEPS_DIR}/" "${BUILD_DIR}/${fn}/"

  # copy entire app/ package (preserve structure)
  rsync -a "${ROOT_DIR}/app/" "${BUILD_DIR}/${fn}/app/"

  # (optional) you can prune other handlers if you want smaller zips:
  # find "${BUILD_DIR}/${fn}/app" -maxdepth 1 -type f ! -name "${fn}.py" \
  #     ! -name "common.py" -delete

  (cd "${BUILD_DIR}/${fn}" && zip -qr "$out_zip" .)
}

# --- BUILD ALL FUNCTION ZIPS ---
for fn in upload list view delete; do
  [ -f "app/${fn}.py" ] || { echo "❗ Skipping missing app/${fn}.py"; continue; }
  build_zip "$fn"
done

# --- CORE RESOURCES ---
echo "🪣 Ensuring S3 bucket and DynamoDB table..."
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" s3 mb s3://images-bucket || true

$AWS --endpoint-url="$ENDPOINT" --region "$REGION" dynamodb create-table \
  --table-name images \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST || true

# --- DEPLOY / UPDATE LAMBDAS ---
deploy_or_update () {
  local fn="$1"                 # upload | list | view | delete
  local function_name="${fn}Image"
  local zip_file="${ROOT_DIR}/${fn}.zip"
  local handler="app.${fn}.handler"   # <— IMPORTANT: app.<fn>.handler

  echo "🚀 Deploying ${function_name} (handler=${handler})..."

  if $AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda get-function --function-name "$function_name" >/dev/null 2>&1; then
    $AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda update-function-code \
      --function-name "$function_name" --zip-file "fileb://${zip_file}" >/dev/null
  else
    $AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda create-function \
      --function-name "$function_name" \
      --runtime python3.9 \
      --handler "$handler" \
      --zip-file "fileb://${zip_file}" \
      --role arn:aws:iam::000000000000:role/lambda-role \
      --timeout 30 --memory-size 256 >/dev/null
  fi

  $AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda wait function-active --function-name "$function_name" || true
}

for fn in upload list view delete; do
  [ -f "${fn}.zip" ] && deploy_or_update "$fn"
done

# --- API GATEWAY ---
API_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-rest-api \
  --name "ImageAPI" --query 'id' --output text)
PARENT_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway get-resources \
  --rest-api-id "$API_ID" --query 'items[0].id' --output text)

create_endpoint () {
  local METHOD="$1"
  local PATH_PART="$2"
  local FN_NAME="$3"   # e.g., uploadImage

  RID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-resource \
    --rest-api-id "$API_ID" --parent-id "$PARENT_ID" --path-part "$PATH_PART" --query 'id' --output text)

  $AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-method \
    --rest-api-id "$API_ID" --resource-id "$RID" \
    --http-method "$METHOD" --authorization-type "NONE"

  $AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-integration \
    --rest-api-id "$API_ID" --resource-id "$RID" --http-method "$METHOD" \
    --type AWS_PROXY --integration-http-method POST \
    --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:${FN_NAME}/invocations

  # permission
  local method_lower
  method_lower="$(echo "$METHOD" | tr '[:upper:]' '[:lower:]')"
  $AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda add-permission \
    --function-name "$FN_NAME" \
    --statement-id "apigw-${PATH_PART}-${method_lower}-$(date +%s)" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/${METHOD}/${PATH_PART} || true
}

# Base routes
create_endpoint POST upload uploadImage
create_endpoint GET  list   listImage

# /view/{id}
VIEW_PARENT_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-resource \
  --rest-api-id "$API_ID" --parent-id "$PARENT_ID" --path-part view --query 'id' --output text)
VIEW_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-resource \
  --rest-api-id "$API_ID" --parent-id "$VIEW_PARENT_ID" --path-part "{id}" --query 'id' --output text)

$AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-method \
  --rest-api-id "$API_ID" --resource-id "$VIEW_ID" --http-method GET --authorization-type "NONE"
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-integration \
  --rest-api-id "$API_ID" --resource-id "$VIEW_ID" --http-method GET \
  --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:viewImage/invocations
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda add-permission \
  --function-name viewImage \
  --statement-id "apigw-view-$(date +%s)" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/GET/view/* || true

# /delete/{id}
DELETE_PARENT_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-resource \
  --rest-api-id "$API_ID" --parent-id "$PARENT_ID" --path-part delete --query 'id' --output text)
DELETE_ID=$($AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-resource \
  --rest-api-id "$API_ID" --parent-id "$DELETE_PARENT_ID" --path-part "{id}" --query 'id' --output text)

$AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-method \
  --rest-api-id "$API_ID" --resource-id "$DELETE_ID" --http-method DELETE --authorization-type "NONE"
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway put-integration \
  --rest-api-id "$API_ID" --resource-id "$DELETE_ID" --http-method DELETE \
  --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:deleteImage/invocations
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda add-permission \
  --function-name deleteImage \
  --statement-id "apigw-delete-$(date +%s)" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/DELETE/delete/* || true

# Deploy stage
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" apigateway create-deployment \
  --rest-api-id "$API_ID" --stage-name dev >/dev/null

echo "✅ Deployment complete!"
echo "Base URL: http://localhost:4566/_aws/execute-api/${API_ID}/dev/"
$AWS --endpoint-url="$ENDPOINT" --region "$REGION" lambda list-functions \
  --query 'Functions[].{Name:FunctionName,Handler:Handler}' --output table
