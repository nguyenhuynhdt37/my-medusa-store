# --- CloudWatch log của EC2 ---
# Lưu log bootstrap/Nginx theo retention đã cấu hình.
resource "aws_cloudwatch_log_group" "host" {
  name              = "/${var.project_name}/${var.environment}/host"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = {
    Name = "${local.name_prefix}-host-logs"
  }
}

# --- IAM role của EC2 ---
# Cho phép EC2 nhận temporary credentials qua instance profile, không lưu access key trên máy.
resource "aws_iam_role" "ec2" {
  name = "${local.name_prefix}-ec2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = {
    Name = "${local.name_prefix}-ec2"
  }
}

# --- Quản trị EC2 qua Systems Manager ---
# Gắn managed policy để có thể dùng SSM Session Manager thay cho SSH.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# --- Quyền ghi log CloudWatch ---
# Giới hạn quyền ghi vào log group của stack; chỉ quyền discovery dùng wildcard.
resource "aws_iam_role_policy" "cloudwatch_logs" {
  name = "${local.name_prefix}-cloudwatch-logs"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteHostLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.host.arn}:*"
      },
      {
        Sid      = "DiscoverLogGroups"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
    ]
  })
}

# --- Quyền đọc deployment artifact tùy chọn ---
# Chỉ tạo policy khi có S3 bucket ARN; EC2 chỉ được list bucket và get object.
resource "aws_iam_role_policy" "deployment_s3" {
  count = var.deployment_s3_bucket_arn == null ? 0 : 1

  name = "${local.name_prefix}-deployment-s3-read"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListDeploymentBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = var.deployment_s3_bucket_arn
      },
      {
        Sid      = "ReadDeploymentArtifacts"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${var.deployment_s3_bucket_arn}/*"
      },
    ]
  })
}

# --- Quyền gọi Lex runtime ---
# FastAPI trên EC2 chỉ được RecognizeText với bot/alias production đã cấu hình.
resource "aws_iam_role_policy" "lex_runtime" {
  name = "${local.name_prefix}-lex-runtime"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "RecognizeTextWithConfiguredBotAlias"
      Effect   = "Allow"
      Action   = "lex:RecognizeText"
      Resource = "arn:aws:lex:${var.aws_region}:${data.aws_caller_identity.current.account_id}:bot-alias/${var.managed_lex_bot_id}/TSTALIASID"
    }]
  })
}

# --- Instance profile ---
# Gắn IAM role bên trên vào EC2.
resource "aws_iam_instance_profile" "ec2" {
  name = "${local.name_prefix}-ec2"
  role = aws_iam_role.ec2.name
}
