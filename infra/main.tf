locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

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
