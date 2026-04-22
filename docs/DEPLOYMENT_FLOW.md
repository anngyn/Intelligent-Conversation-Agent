# Deployment Flow

This document explains how deployment works in this repo today.

## 1. Goal

Deployment pipeline does three things:

1. build backend and frontend container images
2. push those images to Amazon ECR
3. deploy updated infrastructure and services on AWS through Terraform and ECS

Main workflow file:
- [`.github/workflows/cd.yml`](/D:/An/Project/Assignment/.github/workflows/cd.yml:1)

## 2. When Deployment Runs

Deployment is triggered when code is pushed to:
- `main`

That means:
- local changes do nothing by themselves
- only a push to `main` starts the CD workflow

## 3. High-Level Flow

Current deployment flow:

1. GitHub Actions checks out the repository
2. workflow assumes AWS role through OIDC
3. Terraform is initialized
4. ECR repositories are created if needed
5. backend image is built and pushed
6. frontend image is built and pushed
7. Terraform is applied with the new image URIs
8. workflow reads Terraform outputs
9. ECS backend service is forced to redeploy
10. ECS frontend service is forced to redeploy

## 4. Why Two Services

Application is deployed as two ECS services:
- frontend ECS service
- backend ECS service

Reason:
- frontend and backend have different runtime roles
- frontend is internet-facing through ALB
- backend stays private
- deployment and scaling are cleaner when separated

This matches current architecture:
- `ALB -> frontend ECS service -> backend ECS service`

## 5. Detailed Step-by-Step Flow

### Step 1: Checkout code

GitHub Actions pulls the latest repository content so the runner can build images and apply Terraform.

### Step 2: Configure AWS credentials

Workflow uses:
- `aws-actions/configure-aws-credentials@v4`
- `secrets.AWS_ROLE_ARN`

This means the pipeline does **not** need long-lived AWS access keys in the repo.

Instead:
- GitHub OIDC identity assumes an AWS IAM role
- temporary credentials are used during the workflow

This is better than storing static AWS secrets.

### Step 3: Terraform init

Workflow runs:
- `terraform init`

Purpose:
- download providers
- initialize Terraform working directory
- prepare for later `apply`

### Step 4: Bootstrap ECR repositories

Workflow runs:
- `terraform apply -auto-approve -target=module.ecr`

Purpose:
- make sure ECR repositories already exist before Docker tries to push images

Without this step:
- Docker push could fail because repositories are missing

### Step 5: Login to ECR

Workflow uses:
- `aws-actions/amazon-ecr-login@v2`

Purpose:
- authenticate Docker client against Amazon ECR

### Step 6: Build and push backend image

Workflow builds:
- `backend/Dockerfile`

It pushes two tags:
- `${github.sha}`
- `latest`

Important detail:
- backend image is built from repo root as build context
- this is necessary because backend image needs repository-level files such as processed dataset assets

### Step 7: Build and push frontend image

Workflow builds:
- `frontend/Dockerfile`

It also pushes:
- `${github.sha}`
- `latest`

Frontend build context is:
- `./frontend`

### Step 8: Terraform apply with image variables

Workflow passes:
- `TF_VAR_backend_image`
- `TF_VAR_frontend_image`

Terraform then wires those image URIs into ECS task definitions.

Current logic in Terraform:
- if explicit image variable is passed, use it
- otherwise fall back to `:latest`

Relevant Terraform wiring:
- [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:12)
- [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:18)
- [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:24)

### Step 9: Read Terraform outputs

After apply, workflow reads:
- ECS cluster name
- backend service name
- frontend service name

These outputs come from:
- [infrastructure/outputs.tf](/D:/An/Project/Assignment/infrastructure/outputs.tf:13)

Purpose:
- CD workflow should not hardcode service names
- it gets actual deployed names from Terraform state

### Step 10: Force ECS deployment

Workflow calls:
- `aws ecs update-service --force-new-deployment`

for:
- backend service
- frontend service

Purpose:
- tell ECS to start a fresh deployment cycle
- ensure tasks pick up the latest task definition/image state

## 6. What Terraform Deploys

Main infrastructure pieces:
- VPC with public and private subnets
- ALB
- ECS cluster
- frontend ECS task definition
- backend ECS task definition
- frontend ECS service
- backend ECS service
- ECR repositories
- DynamoDB table for conversation history
- PostgreSQL instance for customer and order data
- CloudWatch dashboard and alarms

Relevant Terraform sections:
- ALB: [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:587)
- frontend task definition: [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:635)
- backend task definition: [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:647)
- backend ECS service: [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:660)
- frontend ECS service: [infrastructure/main.tf](/D:/An/Project/Assignment/infrastructure/main.tf:678)

## 7. Runtime After Deployment

After deployment completes:

### Frontend path
- user hits ALB
- ALB forwards request to frontend ECS service
- frontend renders Streamlit UI

### Backend path
- frontend calls backend through private service URL
- backend handles agent logic
- backend reads and writes conversation history in DynamoDB
- backend reads customer and order data from PostgreSQL
- backend calls Bedrock for generation and embeddings

### Operational visibility
- logs and metrics go to CloudWatch

## 8. Why Terraform Apply Happens After Image Push

Order matters.

Correct order:
1. make sure ECR exists
2. build images
3. push images
4. run Terraform apply using those exact image URIs

Reason:
- Terraform should reference real images that already exist
- if apply runs before image push, ECS may point to image tags that are not yet available

## 9. Current Caveats

Important caveats in current repo state:

- deployment flow is fully described in code and workflow
- Terraform configuration validates successfully
- targeted backend tests pass locally
- but full AWS smoke test has not been confirmed in this repo session

That means:
- deployment design is in place
- end-to-end cloud verification is still final step to run in a real AWS account

## 10. Manual Deployment Equivalent

If you wanted to do same flow manually, sequence would be:

1. `terraform init`
2. `terraform apply -target=module.ecr`
3. login to ECR
4. build and push backend image
5. build and push frontend image
6. `terraform apply` with `TF_VAR_backend_image` and `TF_VAR_frontend_image`
7. `aws ecs update-service --force-new-deployment` for backend
8. `aws ecs update-service --force-new-deployment` for frontend

## 11. Summary

Deployment flow in this repo is:

`push to main -> build images -> push to ECR -> terraform apply -> force ECS redeploy`

Key design idea:
- Terraform manages infrastructure and service wiring
- GitHub Actions supplies fresh image versions
- ECS performs actual rollout of frontend and backend services
