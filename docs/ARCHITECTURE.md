# System Architecture

## Overview

The Agentic Conversational System is built on a three-tier architecture: frontend (Streamlit), backend (FastAPI + LangChain), and AI services (AWS Bedrock).

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Layer                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │             Streamlit Chat Interface                     │  │
│  │  - Session management (UUID-based)                       │  │
│  │  - Real-time token streaming display                     │  │
│  │  - Tool call indicators                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/SSE
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  FastAPI Backend                         │  │
│  │                                                          │  │
│  │  ┌─────────────────────────────────────────────────┐    │  │
│  │  │  API Routes                                     │    │  │
│  │  │  - POST /api/chat (SSE streaming)              │    │  │
│  │  │  - GET /api/health                             │    │  │
│  │  │  - DELETE /api/session/{id}                    │    │  │
│  │  └─────────────────────────────────────────────────┘    │  │
│  │                         │                                 │  │
│  │                         ▼                                 │  │
│  │  ┌─────────────────────────────────────────────────┐    │  │
│  │  │         LangChain Agent Orchestration           │    │  │
│  │  │                                                 │    │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐   │    │  │
│  │  │  │  Agent Graph     │  │   Memory Store   │   │    │  │
│  │  │  │  (ReAct)         │  │  (ChatHistory)   │   │    │  │
│  │  │  └──────────────────┘  └──────────────────┘   │    │  │
│  │  │                                                 │    │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐   │    │  │
│  │  │  │   Tools          │  │  System Prompt   │   │    │  │
│  │  │  │  - RAG Search    │  │  - Grounding     │   │    │  │
│  │  │  │  - Order Check   │  │  - Verification  │   │    │  │
│  │  │  └──────────────────┘  └──────────────────┘   │    │  │
│  │  └─────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────┬──────────────────────────┬─────────────────────────────┘
         │                          │
         ▼                          ▼
┌──────────────────────┐   ┌───────────────────────────────────┐
│    Data Layer        │   │       AI Services Layer           │
│                      │   │                                   │
│  ┌────────────────┐  │   │  ┌─────────────────────────────┐ │
│  │  FAISS Index   │  │   │  │    AWS Bedrock              │ │
│  │  - 10-K Chunks │  │   │  │                             │ │
│  │  - Embeddings  │  │   │  │  ┌────────────────────────┐ │ │
│  │  - Metadata    │  │   │  │  │ Claude 3 Haiku         │ │ │
│  └────────────────┘  │   │  │  │ (Tool Calling)         │ │ │
│                      │   │  │  └────────────────────────┘ │ │
│  ┌────────────────┐  │   │  │                             │ │
│  │  Mock Orders   │  │   │  │  ┌────────────────────────┐ │ │
│  │  (JSON)        │  │   │  │  │ Titan Embeddings v2    │ │ │
│  └────────────────┘  │   │  │  │ (Vectorization)        │ │ │
│                      │   │  │  └────────────────────────┘ │ │
└──────────────────────┘   │  └─────────────────────────────┘ │
                           └───────────────────────────────────┘
```

## Request Flow

### RAG Query Flow
```
1. User: "What were Amazon's total net sales?"
   ↓
2. Streamlit → POST /api/chat with session_id
   ↓
3. FastAPI → LangChain Agent with message + chat_history
   ↓
4. Agent analyzes query → decides to use search_knowledge_base tool
   ↓
5. Tool invokes FAISS retriever
   ↓
6. FAISS → retrieves top-4 chunks (semantic similarity)
   ↓
7. Retriever formats chunks with source citations
   ↓
8. Agent receives formatted context
   ↓
9. Agent → calls Bedrock Claude with context + query
   ↓
10. Claude generates answer grounded in retrieved docs
    ↓
11. Response streams back (Bedrock → LangChain → FastAPI SSE → Streamlit)
    ↓
12. User sees answer with source citations, token by token
```

### Order Status Flow
```
1. User: "Check my order status"
   ↓
2. Agent: "What is your full name?"
   ↓
3. User: "John Smith"
   ↓
4. Agent stores in memory, asks: "Last 4 digits of SSN?"
   ↓
5. User: "1234"
   ↓
6. Agent stores, asks: "Date of birth (YYYY-MM-DD)?"
   ↓
7. User: "1990-01-15"
   ↓
8. Agent now has all 3 fields → decides to call check_order_status tool
   ↓
9. Tool validates inputs (format, presence)
   ↓
10. Tool → looks up in mock order database
    ↓
11. Returns order info (ID, status, tracking, delivery date)
    ↓
12. Agent → formats response for user
    ↓
13. User sees order details
```

## AWS Deployment Architecture

```
                              Internet
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Application Load      │
                    │  Balancer (ALB)        │
                    │  - Public subnets      │
                    └────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
    ┌─────────────────┐                  ┌─────────────────┐
    │  Availability   │                  │  Availability   │
    │  Zone 1         │                  │  Zone 2         │
    │                 │                  │                 │
    │  ┌───────────┐  │                  │  ┌───────────┐  │
    │  │ ECS Task  │  │                  │  │ ECS Task  │  │
    │  │ (Fargate) │  │                  │  │ (Fargate) │  │
    │  │           │  │                  │  │           │  │
    │  │ Backend + │  │                  │  │ Backend + │  │
    │  │ Frontend  │  │                  │  │ Frontend  │  │
    │  │ Container │  │                  │  │ Container │  │
    │  └───────────┘  │                  │  └───────────┘  │
    │  Private Subnet │                  │  Private Subnet │
    └─────────────────┘                  └─────────────────┘
              │                                     │
              └──────────────┬──────────────────────┘
                             ▼
                    ┌────────────────┐
                    │  NAT Gateway   │
                    └────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  AWS Bedrock     │         │  ECR             │
    │  - Claude        │         │  - Docker Images │
    │  - Titan Embed   │         └──────────────────┘
    └──────────────────┘
              │
              ▼
    ┌──────────────────┐
    │  CloudWatch Logs │
    └──────────────────┘
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Security Layers                      │
│                                                         │
│  1. Network Security                                    │
│     ├─ VPC isolation (public/private subnets)          │
│     ├─ Security groups (least-privilege ingress)       │
│     └─ NAT Gateway for outbound traffic                │
│                                                         │
│  2. Identity & Access                                   │
│     ├─ IAM roles (no long-term credentials)            │
│     ├─ Task execution role: ECR + CloudWatch           │
│     └─ Task role: Bedrock InvokeModel only             │
│                                                         │
│  3. Application Security                                │
│     ├─ CORS restrictions (Streamlit origin only)       │
│     ├─ Input validation (SSN format, DOB format)       │
│     └─ Defense-in-depth identity verification          │
│                                                         │
│  4. Data Security                                       │
│     ├─ No PII in logs                                  │
│     ├─ Ephemeral session data (in-memory)              │
│     └─ Mock data only (no real customer info)          │
└─────────────────────────────────────────────────────────┘
```

## Data Flow: Identity Verification

```
┌──────────────────────────────────────────────────────────────┐
│               Defense-in-Depth Verification                  │
│                                                              │
│  Layer 1: System Prompt                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ "MUST collect ALL THREE before calling tool:          │ │
│  │  1. Full name                                          │ │
│  │  2. Last 4 SSN                                         │ │
│  │  3. Date of birth"                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  Layer 2: Agent Logic (LangChain)                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ - Multi-turn conversation                              │ │
│  │ - Maintains verification state in memory               │ │
│  │ - Only calls tool when all fields present              │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  Layer 3: Tool Function Validation                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ def check_order_status(name, ssn, dob):                │ │
│  │   if not name: return error                            │ │
│  │   if len(ssn) != 4: return error                       │ │
│  │   if not valid_date(dob): return error                 │ │
│  │   return lookup_order(name, ssn, dob)                  │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Streaming Architecture

```
Bedrock Streaming Response
         │
         ▼
┌────────────────────────┐
│ LangChain astream_events│
│ - on_chat_model_stream │
│ - on_tool_start        │
│ - on_tool_end          │
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│ FastAPI StreamingResponse│
│ - Server-Sent Events    │
│ - event: data\n\n format│
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│ httpx.AsyncClient     │
│ - aiter_lines()        │
│ - Parse SSE events     │
└────────────────────────┘
         │
         ▼
┌────────────────────────┐
│ Streamlit UI           │
│ - Incremental display  │
│ - Token-by-token       │
└────────────────────────┘
```

## Scalability Considerations

### Current (Demo) Scale
- Single ECS task
- In-memory session storage
- Local FAISS index (baked into container)
- ~20 concurrent users max

### Production Scale (Future)
```
┌────────────────────────────────────────────────────────┐
│                Production Enhancements                 │
│                                                        │
│  Compute:                                              │
│  - ECS Auto Scaling (2-10 tasks based on CPU/memory)  │
│  - Multiple AZs for high availability                  │
│                                                        │
│  Memory:                                               │
│  - DynamoDB for conversation history (persistent)      │
│  - ElastiCache for session caching                     │
│                                                        │
│  RAG:                                                  │
│  - OpenSearch Serverless for vector store              │
│  - S3 for document storage                             │
│  - Lambda for document preprocessing pipeline          │
│                                                        │
│  Observability:                                        │
│  - LangSmith for agent tracing                         │
│  - X-Ray for distributed tracing                       │
│  - CloudWatch dashboards + alarms                      │
│  - Application insights                                │
│                                                        │
│  Security:                                             │
│  - WAF on ALB                                          │
│  - Secrets Manager for API keys                        │
│  - KMS for data encryption                             │
│  - VPC endpoints (no internet egress)                  │
└────────────────────────────────────────────────────────┘
```

## Cost Breakdown

### Per-Request Cost Model
```
Single RAG Query:
- Titan Embedding (query): ~$0.000004 (200 tokens)
- Titan Embedding (4 chunks retrieved): ~$0.000080 (4000 tokens)
- Claude Haiku (input): ~$0.00025 (1000 tokens context)
- Claude Haiku (output): ~$0.000125 (100 tokens response)
───────────────────────────────────────────────────────────
Total per query: ~$0.00046

Order Status Check (no RAG):
- Claude Haiku (input): ~$0.000125 (500 tokens)
- Claude Haiku (output): ~$0.000125 (100 tokens)
───────────────────────────────────────────────────────────
Total per check: ~$0.00025

Infrastructure (monthly, 8 hrs/day):
- ECS Fargate: $2.40
- ALB: $4.80
- NAT Gateway: $10.80
- CloudWatch + ECR: $0.60
───────────────────────────────────────────────────────────
Fixed: ~$18.60/month
Variable: ~$2-5/month (inference at demo volumes)
Total: ~$20-23/month
```

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit 1.40+ | Chat UI, async streaming |
| **Backend** | FastAPI 0.115+ | REST API, SSE streaming |
| **Agent** | LangChain 0.3+ | ReAct agent orchestration |
| **LLM** | Bedrock Claude 3 Haiku | Chat generation, tool calling |
| **Embeddings** | Bedrock Titan v2 | Text vectorization |
| **Vector Store** | FAISS (CPU) | Semantic search |
| **Memory** | LangChain ChatMessageHistory | Session state |
| **IaC** | Terraform 1.5+ | Infrastructure provisioning |
| **Compute** | ECS Fargate | Serverless containers |
| **CI/CD** | GitHub Actions | Automated deployment |
| **Monitoring** | CloudWatch | Logs and basic metrics |

## Next: Level 300 Architecture

If implementing Level 300, the architecture would add:

1. **Data Layer**: PostgreSQL (RDS) with conversation history table
2. **Observability**: LangSmith + X-Ray for full request tracing
3. **Classification**: Pre-routing Lambda for intent classification
4. **Preprocessing**: Step Functions pipeline for document ingestion
5. **Evaluation**: Offline RAGAS pipeline for RAG quality metrics

See `SUBMISSION_SUMMARY.md` for details.
