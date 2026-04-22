# Agentic Conversational System

**Cloud Kinetics SA AI/Data Intern Assignment**

Agentic conversational system for e-commerce use cases:
- grounded document Q&A through RAG
- secure order status lookup through identity-verified tool use

## What This Repo Implements

### Core product
- RAG over the provided Amazon 10-K corpus using FAISS and Bedrock embeddings
- FastAPI backend with streaming chat responses
- Streamlit frontend
- Multi-turn conversation handling
- Secure order lookup workflow requiring full name, last 4 SSN digits, and date of birth

### AWS and operations
- Terraform-managed AWS infrastructure
- ECS deployment split into frontend and backend services
- ALB in front of the frontend service
- Private backend service for API traffic
- CloudWatch logs, custom metrics, dashboard, and alarms
- GitHub Actions CI/CD

### Level 300 baseline already implemented
- DynamoDB-backed conversation history
- PostgreSQL-backed customer and order operational data
- Observability baseline with structured logs and CloudWatch metrics

## Architecture Summary

### Runtime topology
- `ALB -> frontend ECS service -> backend ECS service`
- backend invokes Bedrock for generation and embeddings
- backend reads and writes conversation history in DynamoDB
- backend reads customer and order data from PostgreSQL
- backend performs vector retrieval from a FAISS index

### Data split by access pattern

| Data type | Store | Why |
|---|---|---|
| Conversation history | DynamoDB | Session-based append and ordered read, TTL-friendly, low idle cost |
| Customer and order operations | PostgreSQL | Relational model, indexed lookup, integrity constraints |
| Vector retrieval corpus | FAISS | Small current corpus, lowest cost floor |

### Vector database decision
- `FAISS` is current implementation
- `OpenSearch` is optional next step for production-scale vector retrieval
- reason: OpenSearch cost floor too high for current assignment-scale corpus

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI, LangChain |
| Model | AWS Bedrock Claude 3 Haiku |
| Embeddings | AWS Bedrock Titan Embed v2 |
| Conversation store | DynamoDB |
| Operational store | PostgreSQL |
| Vector store | FAISS |
| Infrastructure | Terraform, ECS Fargate, ALB |
| Observability | CloudWatch logs, EMF metrics, dashboard, alarms |
| CI/CD | GitHub Actions |

## Key Design Decisions

### 1. DynamoDB for conversation history
- schema fits session-based chat history naturally
- key pattern: `session_id` plus ordered message key
- good horizontal scale for multi-task ECS runtime
- lower operational overhead than using PostgreSQL for chat memory

### 2. PostgreSQL for customer and order operations
- customer, order, and order item data is relational
- identity verification path benefits from normalized and indexed lookup
- better fit than DynamoDB for operational business data

### 3. FAISS now, OpenSearch later
- current corpus small enough that FAISS is simplest and cheapest choice
- OpenSearch reserved for future state when corpus size, filtering, or shared search infrastructure justify managed vector search

### 4. ECS Fargate for app runtime
- good fit for always-on frontend/backend services and streaming behavior
- simpler than Lambda for this app shape

## Quick Start

### Prerequisites
- Python 3.11
- AWS credentials with Bedrock access
- Docker optional for containerized runs

### Backend setup
```powershell
cd backend
uv venv --python 3.11 .venv311
. .venv311\Scripts\Activate.ps1
uv pip install -e .
uv pip install -e ".[dev]"
```

### Build vector index
```powershell
cd backend
python scripts/ingest_pdf.py
```

### Run backend
```powershell
cd backend
.venv311\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

### Run frontend
```powershell
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Frontend: `http://localhost:8501`  
Backend: `http://localhost:8000`

## Example Workflows

### RAG question
```text
User: What were Amazon's primary revenue sources in 2023?
Agent: [retrieves relevant chunks]
Agent: returns grounded answer using retrieved context
```

### Order status workflow
```text
User: Check my order status
Agent: asks for full name
Agent: asks for last 4 digits of SSN
Agent: asks for date of birth
Agent: validates identity and returns order status
```

## Tests

### Backend tests
```powershell
& .\backend\.venv311\Scripts\pytest.exe .\backend\tests\test_conversation_history.py .\backend\tests\test_order_store.py .\backend\tests\test_mock_order.py -q
```

### Current validation status
- targeted backend tests pass
- `terraform validate` passes in `infrastructure/`

## Cloud Deployment

### Terraform
```powershell
cd infrastructure
terraform init
terraform plan
terraform apply
```

### Deployment shape
- VPC with public and private subnets
- ALB
- ECS cluster
- frontend ECS service
- backend ECS service
- ECR repositories
- DynamoDB table for conversation history
- PostgreSQL instance for operational data
- CloudWatch dashboard and alarms

### CI/CD
Push to `main` triggers:
1. build backend image
2. build frontend image
3. push both images to ECR
4. `terraform apply`
5. force backend and frontend ECS deployments

## Observability

Implemented baseline:
- structured JSON logs
- PII redaction
- HTTP latency and error metrics
- agent latency metrics
- RAG retrieval latency metrics
- order store latency metrics
- conversation store latency metrics
- CloudWatch dashboard
- CloudWatch alarms

See [docs/OBSERVABILITY_DESIGN.md](/D:/An/Project/Assignment/docs/OBSERVABILITY_DESIGN.md:1).

## Documentation Map

- [Submission Summary](/D:/An/Project/Assignment/docs/SUBMISSION_SUMMARY.md:1)
- [Design Decisions](/D:/An/Project/Assignment/docs/DESIGN_DECISIONS.md:1)
- [Data Design](/D:/An/Project/Assignment/docs/DATA_DESIGN.md:1)
- [Observability Design](/D:/An/Project/Assignment/docs/OBSERVABILITY_DESIGN.md:1)
- [Demo Script](/D:/An/Project/Assignment/docs/DEMO_SCRIPT.md:1)
- [Presentation Guide](/D:/An/Project/Assignment/docs/PRESENTATION.md:1)
- [AWS Architecture Diagram](/D:/An/Project/Assignment/docs/system-architecture-aws.drawio)

## Current Limitations

- OpenSearch vector database not implemented
- X-Ray and LangSmith not implemented
- full AWS deploy smoke test still depends on running `terraform apply` in a real account
- personal submission metadata and demo link still need to be filled before final submission package

## Submission Positioning

Strongest message for review:

`System separates conversation state, operational business data, and retrieval data by access pattern, then keeps current implementation cost-aware while preserving clear production migration paths.`
