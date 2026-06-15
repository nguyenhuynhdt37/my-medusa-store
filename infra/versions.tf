# --- Phiên bản Terraform và provider ---
# Khóa dải phiên bản để tránh thay đổi breaking khi khởi tạo hoặc nâng cấp stack.
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
  }
}
