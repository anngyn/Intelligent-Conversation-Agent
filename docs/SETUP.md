# Setup Guide

Complete step-by-step setup instructions for the Agentic Conversational System.

## Prerequisites

### Required
- Python 3.11 or higher
- AWS Account with:
  - Bedrock access (Claude models enabled)
  - Sufficient permissions for ECS, VPC, IAM
- AWS CLI configured (`aws configure`)
- Git

### Optional
- Docker and Docker Compose (for containerized local development)
- Terraform 1.5+ (for cloud deployment)

## Local Development Setup

### 1. Clone and Navigate

```bash
git clone <your-repo-url>
cd Assignment
```

### 2. Set Up Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
pip install -e ".[dev]"  # Development tools (pytest, ruff)
```

### 3. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
```

Or export as environment variables:

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### 4. Enable Bedrock Models

In the AWS Console:
1. Navigate to Amazon Bedrock
2. Go to "Model access"
3. Request access to:
   - Anthropic Claude 3 Haiku
   - Amazon Titan Embeddings v2

Wait for approval (usually instant for Titan, may take minutes for Claude).

### 5. Build FAISS Index

This processes the 10-K PDF and creates the vector embeddings:

```bash
python scripts/ingest_pdf.py
```

Expected output:
```
Loading PDF from: D:/An/Project/Assignment/dataset/raw/Company-10k-18pages.pdf
Created 47 chunks
Building FAISS index...
Saving index to: D:/An/Project/Assignment/dataset/processed/faiss_index
✓ Ingestion complete!
```

### 6. Run Backend

```bash
python -m app.main
# Or: uvicorn app.main:app --reload
```

Backend should start at `http://localhost:8000`

Test health endpoint:
```bash
curl http://localhost:8000/api/health
```

### 7. Run Frontend (Separate Terminal)

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Streamlit should open automatically at `http://localhost:8501`

## Testing

### Run Unit Tests

```bash
cd backend
pytest -v
```

### Run Linter

```bash
ruff check .
ruff format .
```

### Manual Testing

Use the test accounts in the Streamlit UI:

| Name | Last 4 SSN | DOB | Expected Result |
|------|------------|-----|-----------------|
| John Smith | 1234 | 1990-01-15 | Order ORD-98765, Shipped |
| Jane Doe | 5678 | 1985-06-20 | Order ORD-54321, Delivered |
| Michael Johnson | 9012 | 1992-11-03 | Order ORD-11223, Processing |

Test RAG with questions like:
- "What were Amazon's total net sales?"
- "What are the main risk factors mentioned?"
- "Tell me about Amazon's business segments"

## Docker Compose Setup (Alternative)

If you prefer containerized local development:

```bash
# Build FAISS index first (outside container)
cd backend
python scripts/ingest_pdf.py
cd ..

# Start services
docker-compose up --build
```

Access:
- Frontend: `http://localhost:8501`
- Backend: `http://localhost:8000`

## Cloud Deployment

### Prerequisites

- Terraform installed
- AWS credentials with admin-level permissions
- Docker images built

### 1. Create ECR Repositories

```bash
cd infrastructure
terraform init
terraform plan
terraform apply -target=module.ecr
```

Note the ECR repository URLs from the output.

### 2. Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push backend
cd backend
docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/agentic-system-backend:latest .
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/agentic-system-backend:latest

# Build and push frontend
cd ../frontend
docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/agentic-system-frontend:latest .
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/agentic-system-frontend:latest
```

### 3. Deploy Infrastructure

```bash
cd infrastructure

# Deploy all resources
terraform apply

# Get ALB URL
terraform output alb_dns_name
```

Access your application at the ALB DNS name (e.g., `agentic-system-alb-123456.us-east-1.elb.amazonaws.com`)

### 4. Cost Management

To stop incurring charges:

```bash
# Scale service to 0
aws ecs update-service --cluster agentic-system-cluster --service agentic-system-service --desired-count 0

# Or destroy everything
terraform destroy
```

## CI/CD Setup

### GitHub Actions

1. Create GitHub repository secrets:
   - `AWS_ROLE_ARN`: ARN of IAM role for OIDC authentication

2. Set up OIDC provider in AWS:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

3. Create IAM role for GitHub Actions with trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:<org>/<repo>:*"
      }
    }
  }]
}
```

4. Push to `main` to trigger deployment

## Troubleshooting

### Docker build errors

**Error**: `exec /bin/sh: exec format error` or `exec /usr/local/bin/python: exec format error`
- **Cause**: Docker Desktop / WSL backend is in a bad state, or the local builder cannot execute the requested Linux platform correctly.
- **Solution**:
  - Restart Docker Desktop
  - Run `wsl --shutdown` and then reopen Docker Desktop
  - Verify the runtime with:
    ```bash
    docker run --rm --platform linux/amd64 python:3.11-slim python -V
    ```
  - If the default builder still fails, create a clean Buildx builder:
    ```bash
    docker buildx create --name ckbuilder --driver docker-container --use
    docker buildx inspect --bootstrap
    ```

### Backend won't start

**Error**: `FileNotFoundError: FAISS index not found`
- **Solution**: Run `python scripts/ingest_pdf.py` to build the index

**Error**: `An error occurred (AccessDeniedException) when calling the InvokeModel operation`
- **Solution**: Enable Bedrock model access in AWS Console → Bedrock → Model access

### Frontend can't connect

**Error**: `Failed to connect to backend`
- **Solution**: Ensure backend is running at `http://localhost:8000`
- Check firewall rules
- Verify CORS settings in `backend/app/config.py`

### Terraform errors

**Error**: `Error creating ECS Service: InvalidParameterException: No Container Instances`
- **Solution**: Fargate requires no container instances. Check that `launch_type = "FARGATE"` is set

**Error**: `Error creating VPC: VpcLimitExceeded`
- **Solution**: Delete unused VPCs or request limit increase

**Error**: `ClientException: Container.image contains invalid characters`
- **Cause**: ECS rejected the rendered `container_definitions` payload during `RegisterTaskDefinition`. In this project, the image URI itself may still look valid in `terraform console`; the actual issue was the JSON payload generated for the task definition.
- **Solution**:
  - Use the JSON template-based task definition payload in `infrastructure/templates/`
  - Re-run:
    ```bash
    terraform plan
    terraform apply
    ```
  - If it happens again, verify the resolved image strings with:
    ```bash
    terraform console
    local.frontend_image
    local.backend_image
    ```
  - A valid image string should look like:
    ```text
    503130572927.dkr.ecr.us-east-1.amazonaws.com/agentic-system-frontend:latest
    ```

### High AWS Costs

- NAT Gateway is ~$32/month. For dev, consider putting ECS tasks in public subnets
- Remember to scale ECS service to 0 when not demoing
- Use `terraform destroy` when done

## Next Steps

After successful setup:

1. Test both RAG and order status workflows
2. Review logs in CloudWatch (if deployed to AWS)
3. Experiment with different queries
4. Consider implementing Level 300 features (data model, observability)

## Support

For issues specific to this assignment, refer to:
- `CLAUDE.md` - Project overview
- `README.md` - General documentation
- GitHub Issues (if repository is public)
