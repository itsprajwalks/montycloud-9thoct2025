#!/bin/bash
set -e

### --- CONFIG & PATH FIX ---
# Ensure built-in macOS utilities (rm, sed, date, awk, etc.) and AWS CLI are reachable.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"

AWS="/Library/Frameworks/Python.framework/Versions/3.12/bin/aws"
SED_BIN="/usr/bin/sed"
DATE_BIN="/bin/date"

echo "🔍 Using AWS CLI from: $AWS"
$AWS --version || { echo "❌ AWS CLI not found or not executable. Exiting."; exit 1; }

ENDPOINT="http://localhost:4566"
REGION="us-east-1"
PACKAGE_DIR="package"

### --- CLEAN & INSTALL DEPENDENCIES ---
echo "📦 Cleaning previous builds..."
rm -rf $PACKAGE_DIR *.zip requirements.txt || true
mkdir -p $PACKAGE_DIR

echo "📦 Generating requirements.txt ..."
cat <<EOF > requirements.txt
boto3==1.34.86
requests==2.31.0
requests-toolbelt==1.0.0
EOF

echo "📦 Installing dependencies into $PACKAGE_DIR ..."
pip3 install -r requirements.txt -t $PACKAGE_DIR --no-cache-dir >/dev/null

### --- PACKAGE EACH LAMBDA ---
for fn in common upload list view delete; do
  if [ -f "app/${fn}.py" ]; then
    echo "📦 Bundling ${fn}.zip ..."
    cp "app/${fn}.py" $PACKAGE_DIR/
    (cd $PACKAGE_DIR && zip -qr "../${fn}.zip" .)
  else
    echo "⚠️  Skipping missing app/${fn}.py"
  fi
done

### --- CREATE CORE RESOURCES ---
echo "🌐 Ensuring S3 bucket and DynamoDB table exist..."
$AWS --endpoint-url=$ENDPOINT --region $REGION s3 mb s3://images-bucket || true

$AWS --endpoint-url=$ENDPOINT --region $REGION dynamodb create-table \
  --table-name images \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST || true

### --- DEPLOY / UPDATE LAMBDAS ---
for fn in upload list view delete; do
  FUNC="${fn}Image"
  ZIP="${fn}.zip"
  echo "🚀 Deploying ${FUNC} ..."

  if $AWS --endpoint-url=$ENDPOINT --region $REGION lambda get-function --function-name $FUNC >/dev/null 2>&1; then
    echo "🔁 Updating existing function ${FUNC} ..."
    $AWS --endpoint-url=$ENDPOINT --region $REGION lambda update-function-code \
      --function-name $FUNC --zip-file fileb://$ZIP >/dev/null
  else
    echo "🆕 Creating new function ${FUNC} ..."
    $AWS --endpoint-url=$ENDPOINT --region $REGION lambda create-function \
      --function-name $FUNC \
      --runtime python3.9 \
      --handler ${fn}.handler \
      --zip-file fileb://$ZIP \
      --role arn:aws:iam::000000000000:role/lambda-role \
      --timeout 30 --memory-size 256 >/dev/null
  fi

  echo "⏳ Waiting for ${FUNC} to stabilize..."
  $AWS --endpoint-url=$ENDPOINT --region $REGION lambda wait function-active --function-name $FUNC || true
done

### --- CREATE API GATEWAY ---
API_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-rest-api \
  --name "ImageAPI" --query 'id' --output text)
PARENT_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway get-resources \
  --rest-api-id $API_ID --query 'items[0].id' --output text)

create_endpoint() {
  local METHOD=$1
  local PATH_PART=$2
  local FN=$3

  RID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-resource \
    --rest-api-id $API_ID --parent-id $PARENT_ID --path-part "$PATH_PART" --query 'id' --output text)

  $AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-method \
    --rest-api-id $API_ID --resource-id $RID \
    --http-method $METHOD --authorization-type "NONE"

  $AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-integration \
    --rest-api-id $API_ID --resource-id $RID --http-method $METHOD \
    --type AWS_PROXY --integration-http-method POST \
    --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:${FN}/invocations

  # Lowercase + unique statement id
  local METHOD_LOWER=$($SED_BIN 'y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklmnopqrstuvwxyz/' <<< "$METHOD")
  local TS=$($DATE_BIN +%s)

  $AWS --endpoint-url=$ENDPOINT --region $REGION lambda add-permission \
    --function-name $FN \
    --statement-id apigateway-${PATH_PART}-${METHOD_LOWER}-${TS} \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/${METHOD}/${PATH_PART} || true
}

# --- DEFINE BASE ROUTES ---
create_endpoint POST upload uploadImage
create_endpoint GET  list   listImage

# --- VIEW/{id} ---
VIEW_PARENT_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-resource \
  --rest-api-id $API_ID --parent-id $PARENT_ID --path-part view --query 'id' --output text)
VIEW_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-resource \
  --rest-api-id $API_ID --parent-id $VIEW_PARENT_ID --path-part "{id}" --query 'id' --output text)

$AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-method \
  --rest-api-id $API_ID --resource-id $VIEW_ID --http-method GET --authorization-type "NONE"
$AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-integration \
  --rest-api-id $API_ID --resource-id $VIEW_ID --http-method GET \
  --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:viewImage/invocations
$AWS --endpoint-url=$ENDPOINT --region $REGION lambda add-permission \
  --function-name viewImage \
  --statement-id apigateway-view-id-$($DATE_BIN +%s) \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/GET/view/* || true

# --- DELETE/{id} ---
DELETE_PARENT_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-resource \
  --rest-api-id $API_ID --parent-id $PARENT_ID --path-part delete --query 'id' --output text)
DELETE_ID=$($AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-resource \
  --rest-api-id $API_ID --parent-id $DELETE_PARENT_ID --path-part "{id}" --query 'id' --output text)

$AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-method \
  --rest-api-id $API_ID --resource-id $DELETE_ID --http-method DELETE --authorization-type "NONE"
$AWS --endpoint-url=$ENDPOINT --region $REGION apigateway put-integration \
  --rest-api-id $API_ID --resource-id $DELETE_ID --http-method DELETE \
  --type AWS_PROXY --integration-http-method POST \
  --uri arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:deleteImage/invocations
$AWS --endpoint-url=$ENDPOINT --region $REGION lambda add-permission \
  --function-name deleteImage \
  --statement-id apigateway-delete-id-$($DATE_BIN +%s) \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn arn:aws:execute-api:$REGION:000000000000:$API_ID/*/DELETE/delete/* || true

# --- DEPLOY ---
$AWS --endpoint-url=$ENDPOINT --region $REGION apigateway create-deployment \
  --rest-api-id $API_ID --stage-name dev >/dev/null

### --- DONE ---
echo "✅ Deployment complete!"
echo "🌐 API Base URL:"
echo "http://localhost:4566/_aws/execute-api/${API_ID}/dev/"
echo ""
echo "🧾 Deployed Lambdas:"
$AWS --endpoint-url=$ENDPOINT --region $REGION lambda list-functions \
  --query 'Functions[].FunctionName' --output table
