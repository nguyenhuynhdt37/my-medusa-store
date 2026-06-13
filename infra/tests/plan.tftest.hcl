mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["ap-southeast-1a", "ap-southeast-1b"]
    }
  }

  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }
}

run "production_plan" {
  command = plan

  variables {
    storefront_domain = "store.example.com"
    api_domain        = "api.example.com"
    chatbot_domain    = "chatbot.example.com"
    letsencrypt_email = "ops@example.com"
    ssh_allowed_cidr  = "203.0.113.10/32"
    ssh_public_key    = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEFAKEKEYFORSTATICPLANONLY000000000000000"
  }

  assert {
    condition     = aws_instance.app.metadata_options[0].http_tokens == "required"
    error_message = "EC2 must require IMDSv2 tokens."
  }

  assert {
    condition     = aws_instance.app.root_block_device[0].encrypted
    error_message = "The EC2 root volume must be encrypted."
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.ssh.cidr_ipv4 != "0.0.0.0/0"
    error_message = "SSH must not be open to the internet."
  }

  assert {
    condition = toset([
      aws_vpc_security_group_ingress_rule.ssh.from_port,
      aws_vpc_security_group_ingress_rule.http.from_port,
      aws_vpc_security_group_ingress_rule.https.from_port,
      aws_vpc_security_group_ingress_rule.app_ports["8000"].from_port,
      aws_vpc_security_group_ingress_rule.app_ports["8080"].from_port,
      aws_vpc_security_group_ingress_rule.app_ports["9000"].from_port,
      aws_vpc_security_group_ingress_rule.app_ports["9001"].from_port,
    ]) == toset([22, 80, 443, 8000, 8080, 9000, 9001])
    error_message = "Only SSH, HTTP, HTTPS, and explicit application ingress rules are expected."
  }

  assert {
    condition     = length(aws_iam_role_policy.deployment_s3) == 0
    error_message = "S3 access must remain disabled when no bucket ARN is supplied."
  }


  assert {
    condition     = length(aws_iam_role_policy.lex_runtime) == 0
    error_message = "Lex access must remain disabled until a bot and alias are explicitly configured."
  }
}
