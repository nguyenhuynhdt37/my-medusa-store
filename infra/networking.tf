# --- Mạng VPC ---
# Tạo VPC có DNS nội bộ để EC2 và các dịch vụ AWS phân giải hostname bình thường.
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

# --- Kết nối Internet ---
# Internet Gateway cung cấp đường ra/vào Internet cho public subnet.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}

# --- Public subnet ---
# Đặt EC2 tại availability zone đầu tiên; public IP được quản lý rõ ràng bởi EC2/EIP.
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.name_prefix}-public-a"
    Tier = "public"
  }
}

# --- Định tuyến public ---
# Mọi lưu lượng ngoài VPC đi qua Internet Gateway.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${local.name_prefix}-public"
  }
}

# Gắn route table public vào subnet chạy ứng dụng.
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
