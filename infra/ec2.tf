# --- SSH key pair ---
# Đăng ký public key lên AWS; private key chỉ tồn tại trên máy deploy.
resource "aws_key_pair" "deployer" {
  key_name   = "${local.name_prefix}-deployer"
  public_key = trimspace(var.ssh_public_key)

  tags = {
    Name = "${local.name_prefix}-deployer"
  }
}

# --- Máy chủ ứng dụng ---
# Khởi tạo Ubuntu, gắn network/IAM và chạy bootstrap. Upload file được tách ra để EC2 không bị taint khi SSH chậm.
resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  key_name                    = aws_key_pair.deployer.key_name
  associate_public_ip_address = true
  disable_api_termination     = var.enable_termination_protection
  monitoring                  = false

  user_data = templatefile("${path.module}/user_data.sh", {
    api_domain           = var.api_domain
    aws_region           = var.aws_region
    chatbot_domain       = var.chatbot_domain
    cloudwatch_log_group = aws_cloudwatch_log_group.host.name
    letsencrypt_email    = var.letsencrypt_email == null ? "" : var.letsencrypt_email
    project_name         = var.project_name
    storefront_domain    = var.storefront_domain
  })

  user_data_replace_on_change = var.user_data_replace_on_change

  metadata_options {
    http_endpoint               = "enabled"
    http_protocol_ipv6          = "disabled"
    http_put_response_hop_limit = 1
    http_tokens                 = "required"
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted             = true
    delete_on_termination = true
    volume_size           = var.root_volume_size
    volume_type           = "gp3"

    tags = {
      Name = "${local.name_prefix}-root"
    }
  }

  credit_specification {
    cpu_credits = "standard"
  }

  depends_on = [
    aws_iam_role_policy.cloudwatch_logs,
    aws_iam_role_policy_attachment.ssm,
    aws_route_table_association.public,
    null_resource.prepare_env,
  ]

  tags = {
    Name = "${local.name_prefix}-app"
    Role = "application"
  }
}

# --- Địa chỉ IP tĩnh ---
# EIP giữ địa chỉ public ổn định khi EC2 restart và được gắn vào instance ứng dụng.
resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "${local.name_prefix}-eip"
  }
}

# Gắn EIP vào EC2 sau khi cả hai resource đã sẵn sàng.
resource "aws_eip_association" "app" {
  allocation_id = aws_eip.app.id
  instance_id   = aws_instance.app.id
}

# --- Upload file bootstrap qua EIP ---
# Chỉ chạy sau khi EIP đã gắn; retry SSH tại đây không làm aws_instance bị taint.
resource "null_resource" "bootstrap_files" {
  triggers = {
    instance_id        = aws_instance.app.id
    docker_compose_sha = filesha256("${path.module}/../medusa-pubic/docker-compose.yml")
    init_sql_sha       = filesha256("${path.module}/../medusa-pubic/init.sql")
    env_source_sha     = filesha256("${path.module}/../.env")
    lex_bot_id         = var.managed_lex_bot_id
    lex_bot_alias_id   = coalesce(var.lex_bot_alias_id, "TSTALIASID")
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = file(pathexpand("~/.ssh/id_ed25519"))
    host        = aws_eip.app.public_ip
    timeout     = "10m"
  }

  provisioner "file" {
    source      = "${path.module}/../medusa-pubic/docker-compose.yml"
    destination = "/home/ubuntu/docker-compose.yml"
  }

  provisioner "file" {
    source      = "${path.module}/../medusa-pubic/init.sql"
    destination = "/home/ubuntu/init.sql"
  }

  provisioner "file" {
    source      = "${path.module}/../.env.deploy"
    destination = "/home/ubuntu/.env"
  }

  depends_on = [
    aws_eip_association.app,
    null_resource.prepare_env,
  ]
}

# --- Tạo file environment để deploy ---
# Lấy .env làm nguồn, thay bot ID/alias ID và ghi sang .env.deploy trước khi upload.
resource "null_resource" "prepare_env" {
  triggers = {
    lex_bot_id       = var.managed_lex_bot_id
    lex_bot_alias_id = coalesce(var.lex_bot_alias_id, "TSTALIASID")
    env_hash         = filesha256("${path.module}/../.env")
  }

  provisioner "local-exec" {
    command = <<EOF
python3 -c "
import re
with open('${path.module}/../.env', 'r') as f:
    content = f.read()
content = re.sub(r'^LEX_BOT_ID=.*', 'LEX_BOT_ID=${var.managed_lex_bot_id}', content, flags=re.MULTILINE)
content = re.sub(r'^LEX_BOT_ALIAS_ID=.*', 'LEX_BOT_ALIAS_ID=${coalesce(var.lex_bot_alias_id, "TSTALIASID")}', content, flags=re.MULTILINE)
with open('${path.module}/../.env.deploy', 'w') as f:
    f.write(content)
"
EOF
  }
}

# --- Đồng bộ environment và restart stack ---
# Chạy lại khi Lex ID hoặc nội dung .env thay đổi, hoặc file bootstrap thay đổi, sau đó restart Docker Compose trên EC2.
resource "null_resource" "sync_env_and_restart" {
  triggers = {
    lex_bot_id       = var.managed_lex_bot_id
    lex_bot_alias_id = coalesce(var.lex_bot_alias_id, "TSTALIASID")
    env_hash         = filesha256("${path.module}/../.env")
    bootstrap_id     = null_resource.bootstrap_files.id
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = file(pathexpand("~/.ssh/id_ed25519"))
    host        = aws_eip.app.public_ip
  }

  provisioner "file" {
    source      = "${path.module}/../.env.deploy"
    destination = "/home/ubuntu/.env"
  }

  # Chờ bootstrap hoàn tất, đặt .env đúng vị trí và restart các container.
  provisioner "remote-exec" {
    inline = [
      "echo 'Waiting for bootstrap to finish...'",
      "until [ -f /opt/${var.project_name}/app/medusa-pubic/docker-compose.yml ]; do sleep 5; done",
      "[ -f /home/ubuntu/.env ] && sudo mv /home/ubuntu/.env /opt/${var.project_name}/app/.env || true",
      "sudo ln -sf /opt/${var.project_name}/app/.env /opt/${var.project_name}/app/medusa-pubic/.env",
      "cd /opt/${var.project_name}/app",
      "sudo env COMPOSE_PROGRESS=plain docker compose -f medusa-pubic/docker-compose.yml down --remove-orphans || true",
      "sudo env COMPOSE_PROGRESS=plain docker compose -f medusa-pubic/docker-compose.yml up -d --remove-orphans"
    ]
  }

  depends_on = [
    null_resource.bootstrap_files,
  ]
}
