resource "aws_key_pair" "deployer" {
  key_name   = "${local.name_prefix}-deployer"
  public_key = trimspace(var.ssh_public_key)

  tags = {
    Name = "${local.name_prefix}-deployer"
  }
}

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
  ]

  tags = {
    Name = "${local.name_prefix}-app"
    Role = "application"
  }
}

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "${local.name_prefix}-eip"
  }
}

resource "aws_eip_association" "app" {
  allocation_id = aws_eip.app.id
  instance_id   = aws_instance.app.id
}
