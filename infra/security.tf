# --- Security group của máy chủ ứng dụng ---
# Tạo container SG; các rule được tách riêng để Terraform quản lý từng cổng.
resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app"
  description = "Public HTTP(S) and restricted administrative SSH"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-app"
  }
}

# --- Truy cập quản trị ---
# Chỉ cho phép SSH từ một địa chỉ /32 được khai báo trong terraform.tfvars.
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.app.id
  description       = "Temporary SSH access from one trusted public IP"
  cidr_ipv4         = var.ssh_allowed_cidr
  from_port         = 22
  ip_protocol       = "tcp"
  to_port           = 22
}

# --- Lưu lượng web công khai ---
# HTTP phục vụ redirect/ACME, HTTPS phục vụ storefront, API và chatbot.
resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.app.id
  description       = "Public HTTP for redirect and ACME validation"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  ip_protocol       = "tcp"
  to_port           = 80
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.app.id
  description       = "Public HTTPS application traffic"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  ip_protocol       = "tcp"
  to_port           = 443
}

# --- Lưu lượng đi ra Internet ---
# EC2 cần outbound để tải package, Docker image và gọi các API AWS/dịch vụ bên ngoài.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.app.id
  description       = "Outbound package, registry, API, and AWS service access"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
