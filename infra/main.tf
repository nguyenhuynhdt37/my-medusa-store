# --- Giá trị dùng chung ---
# Chuẩn hóa tên resource và URL webhook Lambda sẽ gọi tới FastAPI.
locals {
  name_prefix         = "${var.project_name}-${var.environment}"
  chatbot_webhook_url = coalesce(var.chatbot_webhook_url_override, "https://${var.chatbot_domain}/lexv2/webhook")
}

# --- AWS data sources ---
# Đọc thông tin động từ tài khoản AWS thay vì hard-code AZ, account ID và AMI.
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

# --- Kiểm tra cấu hình Lex runtime ---
# Bot ID và alias ID phải được khai báo cùng nhau để tránh runtime thiếu một nửa cấu hình.
check "lex_configuration" {
  assert {
    condition = (
      var.lex_bot_id == null && var.lex_bot_alias_id == null
      ) || (
      var.lex_bot_id != null && var.lex_bot_alias_id != null
    )
    error_message = "lex_bot_id and lex_bot_alias_id must either both be set or both be null."
  }
}
