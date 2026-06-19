aws_region        = "ap-southeast-1"
project_name      = "ecomoi-chatbot"
environment       = "production"
instance_type     = "t3.large"
root_volume_size  = 40
storefront_domain = "store.itup.id.vn"
api_domain        = "admin.itup.id.vn"
chatbot_domain    = "bot.itup.id.vn"
ssh_allowed_cidr  = "0.0.0.0/0"
ssh_public_key    = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINa5mBCAaJ4m3Tbv/R0+6lgkvJzJRpWHl/6CGe41fVDb nguyenhuynhdt37@gmail.com"

# Optional. Leave null unless EC2 must download immutable deployment artifacts.
deployment_s3_bucket_arn = null

# Optional Amazon Lex V2 runtime access. Set both or leave both null.
lex_bot_id         = null
lex_bot_alias_id   = null
managed_lex_bot_id = "GMWCA6F3LT"

# Enable only after testing terraform destroy and defining a recovery procedure.
enable_termination_protection = false

additional_tags = {
  Owner      = "platform-team"
  CostCenter = "student-project"
}

chatbot_webhook_url_override = null
