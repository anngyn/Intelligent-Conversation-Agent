output "alb_dns_name" {
  description = "DNS name of the frontend Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "ecr_backend_repository_url" {
  description = "URL of the backend ECR repository"
  value       = module.ecr.backend_repository_url
}

output "ecr_frontend_repository_url" {
  description = "URL of the frontend ECR repository"
  value       = module.ecr.frontend_repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "frontend_service_name" {
  description = "Name of the frontend ECS service"
  value       = aws_ecs_service.frontend.name
}

output "backend_service_name" {
  description = "Name of the backend ECS service"
  value       = aws_ecs_service.backend.name
}

output "backend_service_url" {
  description = "Private service discovery URL used by the frontend to reach the backend API"
  value       = local.backend_service_url
}

output "conversation_table_name" {
  description = "DynamoDB table used for per-session conversation history"
  value       = aws_dynamodb_table.conversation_history.name
}

output "order_database_endpoint" {
  description = "PostgreSQL endpoint for order and customer operational data"
  value       = aws_db_instance.orders.address
}

output "order_database_port" {
  description = "PostgreSQL port for order and customer operational data"
  value       = aws_db_instance.orders.port
}

output "order_database_name" {
  description = "Logical PostgreSQL database name"
  value       = local.order_database_name
}

output "order_database_username" {
  description = "Application username for PostgreSQL"
  value       = local.order_database_username
}

output "order_database_connection_secret_arn" {
  description = "Secrets Manager ARN for the backend ORDER_DATABASE_URL secret"
  value       = aws_secretsmanager_secret.order_database_url.arn
}

output "pii_hash_salt_secret_arn" {
  description = "Secrets Manager ARN for the backend PII_HASH_SALT secret"
  value       = aws_secretsmanager_secret.pii_hash_salt.arn
}

output "monitoring_dashboard_name" {
  description = "CloudWatch dashboard for agent traffic, latency, and service health"
  value       = aws_cloudwatch_dashboard.agent.dashboard_name
}

output "monitoring_alarm_names" {
  description = "CloudWatch alarms created for the application baseline"
  value = [
    aws_cloudwatch_metric_alarm.agent_latency_high.alarm_name,
    aws_cloudwatch_metric_alarm.rag_retrieval_latency_high.alarm_name,
    aws_cloudwatch_metric_alarm.order_store_latency_high.alarm_name,
    aws_cloudwatch_metric_alarm.chat_stream_errors.alarm_name,
    aws_cloudwatch_metric_alarm.frontend_unhealthy_hosts.alarm_name,
  ]
}
