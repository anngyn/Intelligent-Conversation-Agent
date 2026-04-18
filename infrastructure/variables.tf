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
  default     = "256"  # 0.25 vCPU
}

variable "task_memory" {
  description = "Fargate task memory in MB"
  type        = string
  default     = "512"  # 0.5 GB
}

variable "desired_count" {
  description = "Desired number of Fargate tasks"
  type        = number
  default     = 1
}
