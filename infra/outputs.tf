output "instance_id" {
  description = "EC2 instance ID used by SSM and deployment automation."
  value       = aws_instance.app.id
}

output "aws_region" {
  description = "AWS region containing the stack."
  value       = var.aws_region
}

output "elastic_ip" {
  description = "Stable public IPv4 address. Point the Mat Bao DNS A record to this value."
  value       = aws_eip.app.public_ip
}

output "storefront_url" {
  description = "Storefront URL after DNS and TLS are configured."
  value       = "https://${var.storefront_domain}"
}

output "api_url" {
  description = "Backend API and WebSocket base URL after DNS and TLS are configured."
  value       = "https://${var.api_domain}"
}

output "chatbot_url" {
  description = "FastAPI chatbot URL after DNS and TLS are configured."
  value       = "https://${var.chatbot_domain}"
}

output "ssm_start_session_command" {
  description = "Preferred administrative access command."
  value       = "aws ssm start-session --target ${aws_instance.app.id} --region ${var.aws_region}"
}

output "ssh_command" {
  description = "Fallback SSH command. The matching private key must remain outside Terraform."
  value       = "ssh ubuntu@${aws_eip.app.public_ip}"
}

output "cloudwatch_log_group" {
  description = "CloudWatch Logs group receiving host and Nginx logs."
  value       = aws_cloudwatch_log_group.host.name
}
