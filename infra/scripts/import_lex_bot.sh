#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LEX_DIR="${LEX_DIR:-$INFRA_DIR/lex}"
DRY_RUN=0
SKIP_GENERATE="${SKIP_GENERATE:-0}"
ALLOW_CREATE="${ALLOW_CREATE:-0}"

usage() {
    cat <<'EOF'
Usage: ./infra/scripts/import_lex_bot.sh [--dry-run] [--skip-generate] [--allow-create]

Generates, imports, builds, and connects the Lex V2 bot to its Lambda hook.
Configuration is resolved from Terraform state and outputs.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --skip-generate) SKIP_GENERATE=1 ;;
        --allow-create) ALLOW_CREATE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

for command in aws curl jq python3 terraform zip; do
    command -v "$command" >/dev/null || {
        echo "Missing required command: $command" >&2
        exit 1
    }
done

tf_output() {
    terraform -chdir="$INFRA_DIR" output -raw "$1" 2>/dev/null
}

tf_lambda_arn() {
    terraform -chdir="$INFRA_DIR" state show -no-color aws_lambda_function.chatbot_lambda \
        | awk -F' = ' '/^[[:space:]]*arn[[:space:]]*=/{gsub(/"/, "", $2); print $2; exit}'
}

if [[ "$SKIP_GENERATE" != "1" ]]; then
    echo "Generating Lex export..." >&2
    python3 "$SCRIPT_DIR/generate_lex_export.py"
fi

BOT_NAME="$(jq -er '.name' "$LEX_DIR/EcomoiChatbot/Bot.json")"
LOCALE_COUNT="$(find "$LEX_DIR/EcomoiChatbot/BotLocales" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
if [[ "$LOCALE_COUNT" -ne 1 ]]; then
    echo "Expected exactly one bot locale, found $LOCALE_COUNT." >&2
    exit 1
fi

LOCALE_DIR="$(find "$LEX_DIR/EcomoiChatbot/BotLocales" -mindepth 1 -maxdepth 1 -type d -print)"
LOCALE_ID="$(jq -er '.identifier' "$LOCALE_DIR/BotLocale.json")"
AWS_REGION="${AWS_REGION:-$(tf_output aws_region)}"
EXPECTED_BOT_ID="${LEX_BOT_ID:-$(tf_output lex_bot_id)}"
BOT_ALIAS_ID="${LEX_BOT_ALIAS_ID:-$(tf_output lex_bot_alias_id)}"
LAMBDA_ARN="${LAMBDA_ARN:-$(tf_lambda_arn)}"

if [[ -z "$AWS_REGION" || -z "$EXPECTED_BOT_ID" || -z "$BOT_ALIAS_ID" || -z "$LAMBDA_ARN" ]]; then
    echo "Could not resolve region, bot ID, alias ID, or Lambda ARN from Terraform." >&2
    exit 1
fi

CURRENT_BOT="$(aws lexv2-models describe-bot --bot-id "$EXPECTED_BOT_ID" --region "$AWS_REGION" 2>/dev/null || true)"
BOT_EXISTS=1
if [[ -n "$CURRENT_BOT" ]]; then
    CURRENT_BOT_NAME="$(jq -er '.botName' <<<"$CURRENT_BOT")"
    ROLE_ARN="$(jq -er '.roleArn' <<<"$CURRENT_BOT")"
    if [[ "$CURRENT_BOT_NAME" != "$BOT_NAME" ]]; then
        echo "Refusing import: Terraform bot '$CURRENT_BOT_NAME' does not match export '$BOT_NAME'." >&2
        exit 1
    fi
    BOT_ALIAS_NAME="$(aws lexv2-models describe-bot-alias \
        --bot-id "$EXPECTED_BOT_ID" \
        --bot-alias-id "$BOT_ALIAS_ID" \
        --region "$AWS_REGION" \
        | jq -er '.botAliasName')"
else
    BOT_EXISTS=0
    if [[ "$ALLOW_CREATE" != "1" ]]; then
        echo "Lex bot $EXPECTED_BOT_ID does not exist. Run once with --allow-create, then update managed_lex_bot_id." >&2
        exit 1
    fi
    ACCOUNT_ID="$(cut -d: -f5 <<<"$LAMBDA_ARN")"
    ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/lexv2.amazonaws.com/AWSServiceRoleForLexV2Bots"
    BOT_ALIAS_NAME="TestBotAlias"
    echo "Lex bot $EXPECTED_BOT_ID is missing; a replacement bot will be created." >&2
fi

echo "Lex deployment configuration:" >&2
echo "  bot: $BOT_NAME ($EXPECTED_BOT_ID)" >&2
echo "  locale: $LOCALE_ID" >&2
echo "  alias: $BOT_ALIAS_NAME ($BOT_ALIAS_ID)" >&2
echo "  region: $AWS_REGION" >&2
echo "  lambda: $LAMBDA_ARN" >&2

if [[ "$DRY_RUN" == "1" ]]; then
    echo "Dry run completed; no AWS resources were changed." >&2
    exit 0
fi

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lex-import.XXXXXX")"
ZIP_PATH="$TEMP_DIR/EcomoiChatbot.zip"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Creating Lex import archive..." >&2
(
    cd "$LEX_DIR"
    zip -qr "$ZIP_PATH" Manifest.json EcomoiChatbot
)

echo "Creating upload URL..." >&2
UPLOAD_RESP="$(aws lexv2-models create-upload-url --region "$AWS_REGION")"
UPLOAD_URL="$(jq -er '.uploadUrl' <<<"$UPLOAD_RESP")"
IMPORT_ID="$(jq -er '.importId' <<<"$UPLOAD_RESP")"

echo "Uploading Lex archive..." >&2
curl --fail --silent --show-error -X PUT -T "$ZIP_PATH" "$UPLOAD_URL" >/dev/null

RESOURCE_SPEC="$(jq -cn \
    --arg bot_name "$BOT_NAME" \
    --arg role_arn "$ROLE_ARN" \
    '{botImportSpecification:{botName:$bot_name,roleArn:$role_arn,dataPrivacy:{childDirected:false}}}')"

echo "Starting Lex import ($IMPORT_ID)..." >&2
aws lexv2-models start-import \
    --import-id "$IMPORT_ID" \
    --resource-specification "$RESOURCE_SPEC" \
    --merge-strategy Overwrite \
    --region "$AWS_REGION" >/dev/null

for _ in {1..120}; do
    IMPORT_STATUS_RESP="$(aws lexv2-models describe-import --import-id "$IMPORT_ID" --region "$AWS_REGION")"
    STATUS="$(jq -er '.importStatus' <<<"$IMPORT_STATUS_RESP")"
    echo "Import status: $STATUS" >&2
    if [[ "$STATUS" == "Completed" ]]; then
        BOT_ID="$(jq -er '.importedResourceId' <<<"$IMPORT_STATUS_RESP")"
        break
    fi
    if [[ "$STATUS" == "Failed" ]]; then
        jq -r '.failureReasons[]?' <<<"$IMPORT_STATUS_RESP" >&2
        exit 1
    fi
    sleep 3
done

if [[ -z "${BOT_ID:-}" ]]; then
    echo "Timed out waiting for Lex import." >&2
    exit 1
fi
if [[ "$BOT_EXISTS" == "1" && "$BOT_ID" != "$EXPECTED_BOT_ID" ]]; then
    echo "Import returned unexpected bot ID $BOT_ID; expected $EXPECTED_BOT_ID." >&2
    exit 1
fi

echo "Building locale $LOCALE_ID..." >&2
aws lexv2-models build-bot-locale \
    --bot-id "$BOT_ID" \
    --bot-version DRAFT \
    --locale-id "$LOCALE_ID" \
    --region "$AWS_REGION" >/dev/null

for _ in {1..120}; do
    BUILD_RESP="$(aws lexv2-models describe-bot-locale \
        --bot-id "$BOT_ID" \
        --bot-version DRAFT \
        --locale-id "$LOCALE_ID" \
        --region "$AWS_REGION")"
    BUILD_STATUS="$(jq -er '.botLocaleStatus' <<<"$BUILD_RESP")"
    echo "Build status: $BUILD_STATUS" >&2
    if [[ "$BUILD_STATUS" == "Built" || "$BUILD_STATUS" == "ReadyExpressTesting" ]]; then
        break
    fi
    if [[ "$BUILD_STATUS" == "Failed" ]]; then
        jq -r '.failureReasons[]?' <<<"$BUILD_RESP" >&2
        exit 1
    fi
    sleep 3
done

if [[ "$BUILD_STATUS" != "Built" && "$BUILD_STATUS" != "ReadyExpressTesting" ]]; then
    echo "Timed out waiting for locale build." >&2
    exit 1
fi

LOCALE_SETTINGS="$(jq -cn \
    --arg locale "$LOCALE_ID" \
    --arg lambda_arn "$LAMBDA_ARN" \
    '{($locale):{enabled:true,codeHookSpecification:{lambdaCodeHook:{lambdaARN:$lambda_arn,codeHookInterfaceVersion:"1.0"}}}}')"

echo "Associating Lambda with alias $BOT_ALIAS_NAME..." >&2
aws lexv2-models update-bot-alias \
    --bot-alias-id "$BOT_ALIAS_ID" \
    --bot-id "$BOT_ID" \
    --bot-alias-name "$BOT_ALIAS_NAME" \
    --bot-version DRAFT \
    --bot-alias-locale-settings "$LOCALE_SETTINGS" \
    --region "$AWS_REGION" >/dev/null

# Tự động cập nhật ID của Bot mới vào terraform.tfvars
if [[ -f "$INFRA_DIR/terraform.tfvars" ]]; then
    echo "Updating managed_lex_bot_id in terraform.tfvars to $BOT_ID..." >&2
    python3 -c "
import re
path = '$INFRA_DIR/terraform.tfvars'
with open(path, 'r') as f:
    content = f.read()
content = re.sub(r'^managed_lex_bot_id\s*=\s*\".*\"', 'managed_lex_bot_id = \"$BOT_ID\"', content, flags=re.MULTILINE)
with open(path, 'w') as f:
    f.write(content)
"
fi

jq -cn --arg bot_id "$BOT_ID" --arg locale_id "$LOCALE_ID" '{bot_id:$bot_id,locale_id:$locale_id}'
