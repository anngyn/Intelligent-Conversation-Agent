# Agentic Conversational System

**Cloud Kinetics Data-AI Solution Architect Intern Assignment**

An intelligent conversational agent for e-commerce that combines RAG-based knowledge retrieval with secure tool-based workflows.

## Features

### Level 100: Core Agent
- **Knowledge-Based Q&A**: RAG system using Amazon 10-K filing (FAISS + Bedrock embeddings)
- **Order Status Tool**: Identity-verified order lookup (requires name, SSN last 4, DOB)
- **Multi-Turn Memory**: Session-based conversation history
- **Streaming Responses**: Real-time token-by-token responses

### Level 200: Cloud Deployment
- **AWS Infrastructure**: Terraform IaC for VPC, ECS Fargate, ALB
- **CI/CD Pipeline**: GitHub Actions for automated testing and deployment
- **Scalable Architecture**: Serverless compute, containerized services

## Tech Stack

- **Backend**: Python 3.11, FastAPI, LangChain
- **LLM**: AWS Bedrock (Claude 3 Haiku)
- **Vector Store**: FAISS (local)
- **Frontend**: Streamlit
- **Infrastructure**: Terraform, AWS ECS Fargate
- **CI/CD**: GitHub Actions

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  Streamlit  │─────▶│   FastAPI    │─────▶│   Bedrock   │
│   Frontend  │◀─────│   Backend    │◀─────│   Claude    │
└─────────────┘ SSE  └──────────────┘      └─────────────┘
                            │
                            ├──────▶ FAISS Vector Store
                            │        (10-K Embeddings)
                            │
                            └──────▶ Mock Order DB
```

## Quick Start

### Prerequisites
- Python 3.11+
- AWS credentials configured with Bedrock access
- Docker (optional, for containerized deployment)

### 1. Install Dependencies

```bash
cd backend
pip install -e .
pip install -e ".[dev]"  # For development tools
```

### 2. Configure AWS

Ensure AWS credentials are available:
```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### 3. Build FAISS Index

```bash
cd backend
python scripts/ingest_pdf.py
```

This processes the 10-K PDF and creates the vector index in `dataset/processed/`.

### 4. Run Backend

```bash
cd backend
python -m app.main
# Or: uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`

### 5. Run Frontend

In a separate terminal:
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Frontend runs at `http://localhost:8501`

## Usage

### Example Conversations

**Knowledge-Based Q&A:**
```
User: What were Amazon's total net sales in 2019?
Agent: [Searches 10-K] According to the filing, Amazon's total net sales were...
```

**Order Status Check:**
```
User: Can you check my order status?
Agent: I'll need to verify your identity first. What is your full name?
User: John Smith
Agent: Thank you. What are the last 4 digits of your SSN?
User: 1234
Agent: And your date of birth? (YYYY-MM-DD format)
User: 1990-01-15
Agent: [Verifies and retrieves order]
      Order ID: ORD-98765
      Status: Shipped
      Tracking: 1Z999AA10123456784
      Estimated Delivery: 2026-04-22
```

### Test Accounts

| Name | Last 4 SSN | DOB | Status |
|------|------------|-----|--------|
| John Smith | 1234 | 1990-01-15 | Shipped |
| Jane Doe | 5678 | 1985-06-20 | Delivered |
| Michael Johnson | 9012 | 1992-11-03 | Processing |
| Emily Chen | 3456 | 1988-03-12 | Out for Delivery |

## Development

### Running Tests

```bash
cd backend
pytest
```

### Linting

```bash
ruff check .
ruff format .
```

### Docker Compose (Local)

```bash
docker-compose up --build
```

## Cloud Deployment

### Prerequisites
- AWS account with appropriate permissions
- Terraform 1.5+
- Docker images pushed to ECR

### Deploy Infrastructure

```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

This creates:
- VPC with public/private subnets
- ECS Fargate cluster and service
- Application Load Balancer
- ECR repositories
- IAM roles with Bedrock permissions

### CI/CD

Push to `main` branch triggers:
1. Lint and test
2. Build Docker images
3. Push to ECR
4. Deploy to ECS via Terraform

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **FAISS (local)** | 18-page PDF is tiny (~5MB). Managed vector stores (OpenSearch Serverless, pgvector) add $15-700/mo cost for no benefit at this scale. |
| **Bedrock Claude Haiku** | Cheapest Bedrock model ($0.25/MTok). Sufficient for this use case. Supports tool calling. |
| **In-memory sessions** | Demo scope. Easy upgrade path to DynamoDB via LangChain's `DynamoDBChatMessageHistory`. |
| **ECS Fargate** | Avoids Lambda cold starts and streaming complexity. ~$0.01/hr, can scale to 0. |
| **Streamlit** | Production-quality chat UI in one Python file. Avoids React complexity. |

## Cost Estimate

Running 8 hours/day for demos:
- Bedrock inference: ~$2-5/mo
- ECS Fargate: ~$2.40/mo
- ALB: ~$4.80/mo
- NAT Gateway: ~$10.80/mo
- **Total: ~$20-23/mo**

Can reduce by $15/mo by using public subnets (less production-like).

## Security

- **Identity Verification**: Defense-in-depth — system prompt AND tool validation require all 3 fields
- **RAG Grounding**: Agent instructed to only answer from retrieved docs, minimizing hallucinations
- **IAM Least Privilege**: ECS task role has only `bedrock:InvokeModel*` permissions
- **No Secrets in Code**: AWS credentials via IAM roles, not hardcoded

## Future Enhancements (Level 300)

- **Persistent Memory**: DynamoDB for conversation history
- **Observability**: CloudWatch dashboards, X-Ray tracing, LangSmith
- **Data Model**: SQL schema for orders, customers, conversation logs
- **Request Classification**: Pre-routing layer to classify intent before agent execution
- **Advanced RAG**: Reranking, HyDE, query decomposition

## License

MIT

## Contact

For questions about this assignment, contact Cloud Kinetics VN.
