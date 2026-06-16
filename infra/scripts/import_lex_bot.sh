#!/usr/bin/env bash
set -euo pipefail

# Đọc cấu hình JSON từ stdin do Terraform data "external" truyền vào
query=$(cat)
LEX_DIR=$(echo "$query" | jq -r '.lex_dir')
LAMBDA_ARN=$(echo "$query" | jq -r '.lambda_arn')
ACCOUNT_ID=$(echo "$query" | jq -r '.account_id')

ZIP_PATH="/tmp/EcomoiChatbot.zip"

echo "Starting import process..." >&2

# Nén thư mục Lex Bot
echo "Zipping Lex folder at $LEX_DIR..." >&2
rm -f "$ZIP_PATH"
cd "$LEX_DIR"
zip -r "$ZIP_PATH" Manifest.json EcomoiChatbot > /dev/null

# Tạo URL để upload lên S3 của AWS Lex
echo "Generating upload URL..." >&2
UPLOAD_RESP=$(aws lexv2-models create-upload-url)
UPLOAD_URL=$(echo "$UPLOAD_RESP" | jq -r '.uploadUrl')
UPLOAD_ID=$(echo "$UPLOAD_RESP" | jq -r '.importId') # Sử dụng importId làm Upload ID

# Upload tệp zip lên S3 qua curl
echo "Uploading zip file to AWS S3..." >&2
curl -s -X PUT -T "$ZIP_PATH" "$UPLOAD_URL"

# Khởi chạy quá trình import
echo "Starting Lex Bot import (Import ID: $UPLOAD_ID)..." >&2
aws lexv2-models start-import \
    --import-id "$UPLOAD_ID" \
    --resource-specification "{
        \"botImportSpecification\": {
            \"botName\": \"EcomoiChatbot\",
            \"roleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/lexv2.amazonaws.com/AWSServiceRoleForLexV2Bots\",
            \"dataPrivacy\": {
                \"childDirected\": false
            }
        }
    }" \
    --merge-strategy "Overwrite" > /dev/null

# Chờ quá trình import hoàn tất (polling)
echo "Polling import status..." >&2
while true; do
    IMPORT_STATUS_RESP=$(aws lexv2-models describe-import --import-id "$UPLOAD_ID")
    STATUS=$(echo "$IMPORT_STATUS_RESP" | jq -r '.importStatus')
    echo "Current status: $STATUS" >&2
    if [ "$STATUS" = "Completed" ]; then
        BOT_ID=$(echo "$IMPORT_STATUS_RESP" | jq -r '.importedResourceId')
        echo "Import completed successfully! Bot ID: $BOT_ID" >&2
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo "Import failed!" >&2
        echo "$IMPORT_STATUS_RESP" | jq -r '.failureReasons' >&2
        exit 1
    fi
    sleep 3
done

# Tiến hành Build Bot Locale (en_US) bắt buộc để kích hoạt API RecognizeText
echo "Building Bot Locale (en_US) to activate NLU..." >&2
aws lexv2-models build-bot-locale \
    --bot-id "$BOT_ID" \
    --bot-version "DRAFT" \
    --locale-id "en_US" > /dev/null

# Chờ quá trình build locale hoàn tất
while true; do
    BUILD_RESP=$(aws lexv2-models describe-bot-locale --bot-id "$BOT_ID" --bot-version "DRAFT" --locale-id "en_US")
    BUILD_STATUS=$(echo "$BUILD_RESP" | jq -r '.botLocaleStatus')
    echo "Current build status: $BUILD_STATUS" >&2
    if [[ "$BUILD_STATUS" == "Built" || "$BUILD_STATUS" == "ReadyExpressTesting" ]]; then
        echo "Bot Locale built successfully and ready for production!" >&2
        break
    elif [ "$BUILD_STATUS" = "Failed" ]; then
        echo "Bot Locale build failed!" >&2
        exit 1
    fi
    sleep 3
done

# Cập nhật Bot Alias TestBotAlias (TSTALIASID) để liên kết với AWS Lambda function vừa tạo
echo "Associating Lambda function $LAMBDA_ARN with Bot $BOT_ID (TestBotAlias)..." >&2
aws lexv2-models update-bot-alias \
    --bot-alias-id "TSTALIASID" \
    --bot-id "$BOT_ID" \
    --bot-alias-name "TestBotAlias" \
    --bot-version "DRAFT" \
    --bot-alias-locale-settings "{
        \"en_US\": {
            \"enabled\": true,
            \"codeHookSpecification\": {
                \"lambdaCodeHook\": {
                    \"lambdaARN\": \"$LAMBDA_ARN\",
                    \"codeHookInterfaceVersion\": \"1.0\"
                }
            }
        }
    }" > /dev/null

# Xuất ra JSON cho Terraform nhận diện
echo "{\"bot_id\": \"$BOT_ID\"}"
