# --- Định danh stack AWS ---
# Region, tên dự án và môi trường tạo nên tên/tag chung cho mọi resource.
variable "aws_region" {
  description = "AWS region used for all resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Short lowercase project identifier used in resource names."
  type        = string
  default     = "ecomoi-chatbot"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.project_name))
    error_message = "project_name must contain 3-24 lowercase letters, numbers, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

# --- Mạng nội bộ ---
# CIDR của VPC và public subnet phải không trùng với các mạng kết nối sau này.
variable "vpc_cidr" {
  description = "IPv4 CIDR for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "IPv4 CIDR for the public application subnet."
  type        = string
  default     = "10.20.10.0/24"
}

# --- Cấu hình EC2 ---
# Chọn kích thước máy, ổ đĩa và thông tin truy cập quản trị.
variable "instance_type" {
  description = "EC2 instance type. t3.large is the production baseline for the full Docker Compose stack."
  type        = string
  default     = "t3.large"
}

variable "root_volume_size" {
  description = "Encrypted gp3 root volume size in GiB."
  type        = number
  default     = 40

  validation {
    condition     = var.root_volume_size >= 12 && var.root_volume_size <= 100
    error_message = "root_volume_size must be between 12 and 100 GiB."
  }
}

variable "ssh_allowed_cidr" {
  description = "Single trusted public IPv4 address in /32 notation allowed to use SSH. Prefer SSM and remove this rule later."
  type        = string

  validation {
    condition = length(var.ssh_allowed_cidr) > 0
    error_message = "ssh_allowed_cidr must be a valid, non-public IPv4 /32 CIDR such as 203.0.113.10/32."
  }
}

variable "ssh_public_key" {
  description = "OpenSSH public key installed for the ubuntu user. Never provide a private key."
  type        = string

  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+", trimspace(var.ssh_public_key)))
    error_message = "ssh_public_key must be a valid OpenSSH public key."
  }
}

# --- Domain và TLS ---
# Ba hostname được Nginx sử dụng cho storefront, Medusa API và FastAPI chatbot.
variable "storefront_domain" {
  description = "Public storefront DNS name configured in Nginx."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.storefront_domain))
    error_message = "storefront_domain must be a valid hostname such as store.example.com."
  }
}

variable "api_domain" {
  description = "Public Medusa API and realtime WebSocket DNS name configured in Nginx."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.api_domain))
    error_message = "api_domain must be a valid hostname such as api.example.com."
  }
}

variable "chatbot_domain" {
  description = "Public FastAPI chatbot DNS name configured in Nginx."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.chatbot_domain))
    error_message = "chatbot_domain must be a valid hostname such as chatbot.example.com."
  }
}

# Cho phép ghi đè webhook khi test tạm thời; production mặc định dùng chatbot_domain.
variable "chatbot_webhook_url_override" {
  description = "Optional full Lex V2 fulfillment webhook URL. Use this for temporary dev tunnels such as ngrok."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.chatbot_webhook_url_override == null ||
      can(regex("^https://.+/lexv2/webhook$", var.chatbot_webhook_url_override))
    )
    error_message = "chatbot_webhook_url_override must be null or a full HTTPS URL ending with /lexv2/webhook."
  }
}

# Email tùy chọn để Let's Encrypt gửi thông báo chứng chỉ.
variable "letsencrypt_email" {
  description = "Email used for Let's Encrypt expiry and account notifications."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.letsencrypt_email == null || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.letsencrypt_email))
    error_message = "letsencrypt_email must be a valid email address."
  }
}

# --- Deployment artifact tùy chọn ---
# Nếu null, Terraform không cấp bất kỳ quyền S3 nào cho EC2.
variable "deployment_s3_bucket_arn" {
  description = "Optional existing S3 bucket ARN containing deployment artifacts. Null grants no S3 access."
  type        = string
  default     = null

  validation {
    condition     = var.deployment_s3_bucket_arn == null || can(regex("^arn:aws:s3:::[a-z0-9.-]{3,63}$", var.deployment_s3_bucket_arn))
    error_message = "deployment_s3_bucket_arn must be null or a valid S3 bucket ARN."
  }
}

# --- Amazon Lex V2 ---
# Bot ID và alias ID phục vụ runtime; managed bot ID là bot được script import cập nhật.
variable "lex_bot_id" {
  description = "Optional Amazon Lex V2 bot ID. Set together with lex_bot_alias_id to grant runtime access."
  type        = string
  default     = null

  validation {
    condition     = var.lex_bot_id == null || can(regex("^[A-Z0-9]{10}$", var.lex_bot_id))
    error_message = "lex_bot_id must be null or a 10-character uppercase alphanumeric Lex bot ID."
  }
}

variable "lex_bot_alias_id" {
  description = "Optional Amazon Lex V2 bot alias ID. Set together with lex_bot_id."
  type        = string
  default     = null

  validation {
    condition     = var.lex_bot_alias_id == null || can(regex("^[A-Z0-9]{10}$", var.lex_bot_alias_id))
    error_message = "lex_bot_alias_id must be null or a 10-character uppercase alphanumeric Lex alias ID."
  }
}

variable "managed_lex_bot_id" {
  description = "Amazon Lex V2 bot ID managed by the import script and used by EC2 runtime permissions."
  type        = string

  validation {
    condition     = can(regex("^[A-Z0-9]{10}$", var.managed_lex_bot_id))
    error_message = "managed_lex_bot_id must be a 10-character uppercase alphanumeric Lex bot ID."
  }
}

# --- Bảo vệ và hành vi cập nhật EC2 ---
# Các switch này tránh replace/terminate production ngoài ý muốn.
variable "enable_termination_protection" {
  description = "Protect the EC2 instance from API termination. Keep false while validating terraform destroy."
  type        = bool
  default     = false
}

variable "user_data_replace_on_change" {
  description = "Replace EC2 when user_data changes. Disabled to avoid accidental production replacement."
  type        = bool
  default     = false
}

# --- Log và tag bổ sung ---
# Điều khiển retention CloudWatch và merge thêm tag vào provider AWS.
variable "cloudwatch_log_retention_days" {
  description = "Retention period for bootstrap and Nginx logs."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365], var.cloudwatch_log_retention_days)
    error_message = "Use an AWS-supported CloudWatch Logs retention value."
  }
}

variable "additional_tags" {
  description = "Additional tags applied to every supported AWS resource."
  type        = map(string)
  default     = {}
}
