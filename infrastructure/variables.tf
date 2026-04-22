variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "agentic-system"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "backend_image" {
  description = "Docker image URI for backend"
  type        = string
  default     = ""
}

variable "frontend_image" {
  description = "Docker image URI for frontend"
  type        = string
  default     = ""
}

variable "task_cpu" {
  description = "Fargate task CPU units"
  type        = string
  default     = "256" # 0.25 vCPU
}

variable "task_memory" {
  description = "Fargate task memory in MB"
  type        = string
  default     = "512" # 0.5 GB
}

variable "desired_count" {
  description = "Desired number of Fargate tasks"
  type        = number
  default     = 1
}

variable "conversation_table_name" {
  description = "Optional override for the DynamoDB conversation history table name"
  type        = string
  default     = ""
}

variable "order_database_name" {
  description = "Optional override for the PostgreSQL database name"
  type        = string
  default     = ""
}

variable "order_database_username" {
  description = "Optional override for the PostgreSQL application username"
  type        = string
  default     = ""
}

variable "order_database_instance_class" {
  description = "RDS PostgreSQL instance class for order and customer operational data"
  type        = string
  default     = "db.t4g.micro"
}

variable "order_database_allocated_storage" {
  description = "Initial PostgreSQL storage allocation in GiB"
  type        = number
  default     = 20
}

variable "order_database_max_allocated_storage" {
  description = "Maximum PostgreSQL storage autoscaling limit in GiB"
  type        = number
  default     = 100
}

variable "order_database_backup_retention_days" {
  description = "Retention period for automated PostgreSQL backups"
  type        = number
  default     = 7
}

variable "order_database_multi_az" {
  description = "Enable Multi-AZ standby for PostgreSQL"
  type        = bool
  default     = false
}

variable "order_database_skip_final_snapshot" {
  description = "Skip final snapshot on PostgreSQL deletion for dev/test environments"
  type        = bool
  default     = true
}

variable "alarm_notification_topic_arn" {
  description = "Optional SNS topic ARN for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "agent_latency_p99_threshold_ms" {
  description = "Alarm threshold for chat agent p99 latency in milliseconds"
  type        = number
  default     = 5000
}

variable "rag_retrieval_p95_threshold_ms" {
  description = "Alarm threshold for RAG retrieval p95 latency in milliseconds"
  type        = number
  default     = 800
}

variable "order_store_latency_p95_threshold_ms" {
  description = "Alarm threshold for order store p95 latency in milliseconds"
  type        = number
  default     = 250
}
