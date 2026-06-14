data "archive_file" "chatbot_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/lambda_function.py"
  output_path = "${path.module}/../chatbot_lambda.zip"
}

resource "aws_iam_role" "chatbot_lambda_role" {
  name = "${local.name_prefix}-chatbot-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-chatbot-lambda-role"
  }
}

resource "aws_iam_role_policy_attachment" "chatbot_lambda_logs" {
  role       = aws_iam_role.chatbot_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

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

# Bổ sung policy để ghi logs chi tiết
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

resource "aws_lambda_permission" "allow_lex" {
  statement_id  = "AllowExecutionFromLex"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot_lambda.function_name
  principal     = "lexv2.amazonaws.com"
  source_arn    = "arn:aws:lex:${var.aws_region}:${data.aws_caller_identity.current.account_id}:bot-alias/*"
}

resource "null_resource" "cleanup_lex" {
  triggers = {
    bot_id = var.managed_lex_bot_id
  }

  provisioner "local-exec" {
    when    = destroy
    command = "aws lexv2-models delete-bot --bot-id ${self.triggers.bot_id} --skip-resource-in-use-check || true"
  }
}
