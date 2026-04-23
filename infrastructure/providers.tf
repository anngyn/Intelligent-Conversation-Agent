terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # S3 backend for shared state across CI/CD and local
  backend "s3" {
    bucket         = "terraform-state-agentic-system-503130572927"
    key            = "agentic-system/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-lock-agentic-system"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Agentic-Conversational-System"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
