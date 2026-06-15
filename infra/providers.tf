# --- Cấu hình AWS provider ---
# Tất cả resource dùng chung region và bộ tag mặc định để truy vết môi trường.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Environment = var.environment
        ManagedBy   = "Terraform"
        Project     = var.project_name
      },
      var.additional_tags
    )
  }
}
