# --- Đóng gói Lambda ---
# Tạo file ZIP từ handler Python; hash ZIP giúp Terraform cập nhật khi source thay đổi.
data "archive_file" "chatbot_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/../chatbot_lambda.zip"
}

# --- IAM role của Lambda ---
# Cho phép dịch vụ Lambda assume role này khi thực thi fulfillment hook.
resource "aws_iam_role" "chatbot_lambda_role" {
  name = "${local.name_prefix}-chatbot-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com" # thằng được cấp quyền assume role này là Lambda service của AWS
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-chatbot-lambda-role"
  }
}

# Gắn quyền CloudWatch Logs cơ bản do AWS quản lý.
resource "aws_iam_role_policy_attachment" "chatbot_lambda_logs" {
  role       = aws_iam_role.chatbot_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Lambda fulfillment proxy ---
# Nhận event từ Lex và chuyển tiếp đến endpoint /lexv2/webhook của FastAPI.
resource "aws_lambda_function" "chatbot_lambda" {
  filename         = data.archive_file.chatbot_lambda_zip.output_path
  source_code_hash = data.archive_file.chatbot_lambda_zip.output_base64sha256
  function_name    = "${local.name_prefix}-chatbot-lambda"
  role             = aws_iam_role.chatbot_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 15

  environment {
    variables = {
      CHATBOT_LEXV2_WEBHOOK_URL = local.chatbot_webhook_url
      CHATBOT_SERVICE_URL       = local.chatbot_webhook_url
    }
  }

  depends_on = [
    aws_iam_role_policy.chatbot_logs_custom,
  ]

  tags = {
    Name = "${local.name_prefix}-chatbot-lambda"
  }
}

# Bổ sung quyền tạo log group/stream và ghi log khi Lambda chạy lần đầu.
resource "aws_iam_role_policy" "chatbot_logs_custom" {
  name = "${local.name_prefix}-chatbot-lambda-logs"
  role = aws_iam_role.chatbot_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# --- Cho phép Lex gọi Lambda ---
# Resource-based policy trên Lambda chấp nhận invocation từ Lex V2 alias.
resource "aws_lambda_permission" "allow_lex" {
  statement_id  = "AllowExecutionFromLex"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot_lambda.function_name
  principal     = "lexv2.amazonaws.com"
  source_arn    = "arn:aws:lex:${var.aws_region}:${data.aws_caller_identity.current.account_id}:bot-alias/*"
}

# --- Generate và deploy Lex V2 cùng terraform apply ---
# Hash hai script làm trigger. Khi một script thay đổi, Terraform thay resource và chạy lại import.
resource "terraform_data" "lex_bot_deployment" {
  input = {
    bot_id = var.managed_lex_bot_id
    region = var.aws_region
  }

  triggers_replace = [
    filesha256("${path.module}/scripts/generate_lex_export.py"),
    filesha256("${path.module}/scripts/import_lex_bot.sh"),
  ]

  # Script import tự chạy generator, upload export, build en_US và gắn Lambda vào alias.
  provisioner "local-exec" {
    command     = "${path.module}/scripts/import_lex_bot.sh"
    working_dir = path.root

    environment = {
      AWS_REGION       = var.aws_region
      LEX_BOT_ID       = var.managed_lex_bot_id
      LEX_BOT_ALIAS_ID = coalesce(var.lex_bot_alias_id, "TSTALIASID")
      LAMBDA_ARN       = aws_lambda_function.chatbot_lambda.arn
    }
  }

  # Xóa bot Lex V2 trên AWS khi chạy terraform destroy
  provisioner "local-exec" {
    when    = destroy
    command = "aws lexv2-models delete-bot --bot-id ${self.output.bot_id} --skip-resource-in-use-check --region ${self.output.region} || true"
  }

  depends_on = [
    aws_lambda_permission.allow_lex,
  ]
}
