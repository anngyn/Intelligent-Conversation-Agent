# ECR Repositories
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
}

locals {
  conversation_table_name        = trimspace(var.conversation_table_name) != "" ? trimspace(var.conversation_table_name) : "${var.project_name}-conversation-history"
  order_database_name            = trimspace(var.order_database_name) != "" ? trimspace(var.order_database_name) : replace(var.project_name, "-", "_")
  order_database_username        = trimspace(var.order_database_username) != "" ? trimspace(var.order_database_username) : "agent_app"
  backend_image                  = trimspace(var.backend_image) != "" ? trimspace(var.backend_image) : "${module.ecr.backend_repository_url}:latest"
  frontend_image                 = trimspace(var.frontend_image) != "" ? trimspace(var.frontend_image) : "${module.ecr.frontend_repository_url}:latest"
  backend_service_discovery_name = "backend"
  backend_service_url            = "http://${local.backend_service_discovery_name}.${aws_service_discovery_private_dns_namespace.internal.name}:8000/api"
  monitoring_alarm_actions       = trimspace(var.alarm_notification_topic_arn) != "" ? [trimspace(var.alarm_notification_topic_arn)] : []
  monitoring_dashboard_name      = "${var.project_name}-${var.environment}-overview"
  frontend_container_definitions = jsonencode(jsondecode(templatefile("${path.module}/templates/frontend-container-definitions.json.tftpl", {
    image               = local.frontend_image
    backend_service_url = local.backend_service_url
    awslogs_group       = aws_cloudwatch_log_group.frontend.name
    aws_region          = var.aws_region
  })))
  backend_container_definitions = jsonencode(jsondecode(templatefile("${path.module}/templates/backend-container-definitions.json.tftpl", {
    image                   = local.backend_image
    aws_region              = var.aws_region
    conversation_table_name = aws_dynamodb_table.conversation_history.name
    order_database_url_arn  = aws_secretsmanager_secret.order_database_url.arn
    pii_hash_salt_arn       = aws_secretsmanager_secret.pii_hash_salt.arn
    awslogs_group           = aws_cloudwatch_log_group.backend.name
  })))
}

# VPC and Networking
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# Public subnets for ALB
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${count.index + 1}"
  }
}

# Private subnets for ECS tasks and RDS
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-private-${count.index + 1}"
  }
}

resource "aws_db_subnet_group" "orders" {
  name       = "${var.project_name}-orders-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-orders-db-subnet-group"
  }
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "${var.project_name}.internal"
  vpc  = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-internal"
  }
}

# Route table for public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# NAT Gateway for private subnets (cost optimization: single NAT)
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip"
  }
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "${var.project_name}-nat"
  }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-private-rt"
  }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

resource "aws_security_group" "frontend_tasks" {
  name        = "${var.project_name}-frontend-sg"
  description = "Security group for frontend ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-frontend-sg"
  }
}

resource "aws_security_group" "backend_tasks" {
  name        = "${var.project_name}-backend-sg"
  description = "Security group for backend ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.frontend_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-backend-sg"
  }
}

resource "aws_security_group" "orders_db" {
  name        = "${var.project_name}-orders-db-sg"
  description = "Security group for PostgreSQL order database"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-orders-db-sg"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}/frontend"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-frontend-logs"
  }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-backend-logs"
  }
}

resource "aws_cloudwatch_dashboard" "agent" {
  dashboard_name = local.monitoring_dashboard_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Chat Traffic and Agent Latency"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AgentMetrics", "ChatRequests", "Endpoint", "chat", { stat = "Sum", label = "ChatRequests", yAxis = "right" }],
            [".", "AgentLatency", ".", ".", { stat = "p50", label = "Latency p50" }],
            [".", "AgentLatency", ".", ".", { stat = "p95", label = "Latency p95" }],
            [".", "AgentLatency", ".", ".", { stat = "p99", label = "Latency p99" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "RAG and Order Store Latency"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AgentMetrics", "RAGRetrievalTime", "Component", "FAISS", { stat = "Average", label = "RAG avg" }],
            [".", "RAGRetrievalTime", ".", ".", { stat = "p95", label = "RAG p95" }],
            ["AgentMetrics", "OrderStoreLatency", "Backend", "postgres", { stat = "Average", label = "Order store avg" }],
            [".", "OrderStoreLatency", ".", ".", { stat = "p95", label = "Order store p95" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Conversation Store Latency"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AgentMetrics", "ConversationReadLatency", "Backend", "dynamodb", { stat = "Average", label = "Read avg" }],
            [".", "ConversationWriteLatency", ".", ".", { stat = "Average", label = "Write avg" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Service Health"
          region = var.aws_region
          view   = "timeSeries"
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.frontend.name, { stat = "Average", label = "Frontend CPU" }],
            [".", ".", ".", ".", "ServiceName", aws_ecs_service.backend.name, { stat = "Average", label = "Backend CPU" }],
            ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", aws_lb_target_group.frontend.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix, { stat = "Average", label = "Frontend healthy hosts", yAxis = "right" }]
          ]
        }
      }
    ]
  })
}

# Conversation history store
resource "aws_dynamodb_table" "conversation_history" {
  name         = local.conversation_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "message_key"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "message_key"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-conversation-history"
  }
}

# Operational order/customer store
resource "random_password" "order_database" {
  length  = 24
  special = false
}

resource "random_password" "pii_hash_salt" {
  length  = 32
  special = false
}

resource "aws_db_instance" "orders" {
  identifier                      = "${var.project_name}-orders"
  engine                          = "postgres"
  instance_class                  = var.order_database_instance_class
  allocated_storage               = var.order_database_allocated_storage
  max_allocated_storage           = var.order_database_max_allocated_storage
  storage_type                    = "gp3"
  storage_encrypted               = true
  db_name                         = local.order_database_name
  username                        = local.order_database_username
  password                        = random_password.order_database.result
  db_subnet_group_name            = aws_db_subnet_group.orders.name
  vpc_security_group_ids          = [aws_security_group.orders_db.id]
  backup_retention_period         = var.order_database_backup_retention_days
  multi_az                        = var.order_database_multi_az
  publicly_accessible             = false
  skip_final_snapshot             = var.order_database_skip_final_snapshot
  deletion_protection             = false
  auto_minor_version_upgrade      = true
  copy_tags_to_snapshot           = true
  delete_automated_backups        = true
  performance_insights_enabled    = false
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name = "${var.project_name}-orders"
  }
}

resource "aws_secretsmanager_secret" "order_database_url" {
  name = "${var.project_name}/backend/order-database-url"

  tags = {
    Name = "${var.project_name}-order-database-url"
  }
}

resource "aws_secretsmanager_secret_version" "order_database_url" {
  secret_id     = aws_secretsmanager_secret.order_database_url.id
  secret_string = "postgresql+psycopg://${local.order_database_username}:${random_password.order_database.result}@${aws_db_instance.orders.address}:${aws_db_instance.orders.port}/${local.order_database_name}"
}

resource "aws_secretsmanager_secret" "pii_hash_salt" {
  name = "${var.project_name}/backend/pii-hash-salt"

  tags = {
    Name = "${var.project_name}-pii-hash-salt"
  }
}

resource "aws_secretsmanager_secret_version" "pii_hash_salt" {
  secret_id     = aws_secretsmanager_secret.pii_hash_salt.id
  secret_string = random_password.pii_hash_salt.result
}

# IAM Roles
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "ecs-task-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        aws_secretsmanager_secret.order_database_url.arn,
        aws_secretsmanager_secret.pii_hash_salt.arn
      ]
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "conversation_store_access" {
  name = "conversation-store-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:BatchWriteItem",
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query"
      ]
      Resource = [
        aws_dynamodb_table.conversation_history.arn,
        "${aws_dynamodb_table.conversation_history.arn}/index/*"
      ]
    }]
  })
}

# Internal service discovery for backend
resource "aws_service_discovery_service" "backend" {
  name = local.backend_service_discovery_name

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# Application Load Balancer for frontend only
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.project_name}-frontend"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/_stcore/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name = "${var.project_name}-frontend"
  }
}

resource "aws_lb_listener" "frontend" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# ECS Task Definitions
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = local.frontend_container_definitions
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = local.backend_container_definitions
}

# ECS Services
resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.backend_tasks.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.frontend_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8501
  }

  depends_on = [
    aws_lb_listener.frontend,
    aws_ecs_service.backend
  ]
}

resource "aws_cloudwatch_metric_alarm" "agent_latency_high" {
  alarm_name          = "${var.project_name}-agent-latency-p99-high"
  alarm_description   = "Chat agent p99 latency exceeded the configured threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.agent_latency_p99_threshold_ms
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.monitoring_alarm_actions
  ok_actions          = local.monitoring_alarm_actions

  metric_query {
    id          = "latency"
    return_data = true
    metric {
      namespace   = "AgentMetrics"
      metric_name = "AgentLatency"
      period      = 300
      stat        = "p99"
      dimensions = {
        Endpoint = "chat"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "rag_retrieval_latency_high" {
  alarm_name          = "${var.project_name}-rag-retrieval-p95-high"
  alarm_description   = "RAG retrieval p95 latency exceeded the configured threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.rag_retrieval_p95_threshold_ms
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.monitoring_alarm_actions
  ok_actions          = local.monitoring_alarm_actions

  metric_query {
    id          = "rag"
    return_data = true
    metric {
      namespace   = "AgentMetrics"
      metric_name = "RAGRetrievalTime"
      period      = 300
      stat        = "p95"
      dimensions = {
        Component = "FAISS"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "order_store_latency_high" {
  alarm_name          = "${var.project_name}-order-store-p95-high"
  alarm_description   = "Order store p95 latency exceeded the configured threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.order_store_latency_p95_threshold_ms
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.monitoring_alarm_actions
  ok_actions          = local.monitoring_alarm_actions

  metric_query {
    id          = "orders"
    return_data = true
    metric {
      namespace   = "AgentMetrics"
      metric_name = "OrderStoreLatency"
      period      = 300
      stat        = "p95"
      dimensions = {
        Backend = "postgres"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "chat_stream_errors" {
  alarm_name          = "${var.project_name}-chat-stream-errors"
  alarm_description   = "Chat stream failures were emitted by the backend."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.monitoring_alarm_actions
  ok_actions          = local.monitoring_alarm_actions

  metric_query {
    id          = "errors"
    return_data = true
    metric {
      namespace   = "AgentMetrics"
      metric_name = "ErrorRate"
      period      = 300
      stat        = "Sum"
      dimensions = {
        Endpoint  = "chat"
        ErrorType = "sse_stream_failed"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "frontend_unhealthy_hosts" {
  alarm_name          = "${var.project_name}-frontend-unhealthy"
  alarm_description   = "ALB target group has fewer than one healthy frontend task."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = local.monitoring_alarm_actions
  ok_actions          = local.monitoring_alarm_actions

  namespace   = "AWS/ApplicationELB"
  metric_name = "HealthyHostCount"
  period      = 60
  statistic   = "Average"
  dimensions = {
    TargetGroup  = aws_lb_target_group.frontend.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
}
