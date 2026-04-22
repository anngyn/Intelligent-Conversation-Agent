# Plan: Agentic Conversational System (Cloud Kinetics Intern Assignment)

## Context

This is a **Data-AI Solution Architect Intern** interview assignment for Cloud Kinetics. The task is to build a scalable Agentic Conversational system for a US-based e-commerce company. The agent performs two tasks: (1) RAG-based Q&A on a provided Amazon 10-K filing (18 pages), and (2) order shipment status lookup with identity verification.

**Scope:** Level 100 (Core Agent) + Level 200 (AWS Deployment)
**Stack:** Python, FastAPI, LangChain, AWS Bedrock (Claude), FAISS, Streamlit, Terraform

---

## Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Vector store | **FAISS (local)** | 18-page PDF is tiny (~5 MB index). OpenSearch Serverless costs ~$700/mo minimum. FAISS has zero cost, native LangChain integration. Document managed service as upgrade path. |
| LLM | **Bedrock Claude 3 Haiku** | Cheapest Bedrock chat model ($0.25/MTok input). Supports tool calling via Converse API. Sufficient for this scope. |
| Embeddings | **Bedrock Titan Embed v2** | $0.00002/1K tokens. AWS-native, no external API keys. |
| Frontend | **Streamlit** | Chat UI in one Python file. Native streaming support. Avoids React/webpack overhead. |
| Memory | **In-memory `ChatMessageHistory`** | Sufficient for demo. LangChain's `DynamoDBChatMessageHistory` is a drop-in replacement for production. |
| Compute | **ECS Fargate (single container)** | Serverless, ~$0.01/hr. Avoids Lambda cold starts and streaming complexity. Scale to 0 when not demoing. |
| CI/CD | **GitHub Actions** | Free tier, first-class Docker + Terraform + AWS OIDC support. |
| Chunking | **RecursiveCharacterTextSplitter** | 1000 chars, 200 overlap. Section-aware metadata from 10-K headings. |

**Estimated AWS cost:** ~$20/month running 8 hrs/day for demos.

---

## Implementation Phases

### Phase 0: Project Scaffolding
Create monorepo structure, dependencies, Docker setup, and `.gitignore`.

```
Assignment/
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/
│       ├── main.py              # FastAPI entry point + lifespan
│       ├── config.py            # pydantic-settings (AWS_REGION, MODEL_ID, etc.)
│       ├── api/
│       │   ├── routes.py        # POST /api/chat (SSE), GET /api/health
│       │   └── schemas.py       # ChatRequest, ChatEvent models
│       ├── agent/
│       │   ├── graph.py         # LangChain ReAct agent construction
│       │   ├── tools.py         # @tool: check_order_status, search_knowledge_base
│       │   ├── prompts.py       # System prompt (RAG grounding + identity verification rules)
│       │   └── memory.py        # Session store: dict[str, ChatMessageHistory]
│       ├── rag/
│       │   ├── ingest.py        # PyPDFLoader → RecursiveCharacterTextSplitter → FAISS
│       │   ├── retriever.py     # vectorstore.as_retriever(k=4)
│       │   └── store.py         # FAISS load/save lifecycle
│       └── mock/
│           └── order_api.py     # Mock order DB keyed by (name, last4_ssn, dob)
├── dataset/
│   ├── raw/Company-10k-18pages.pdf
│   ├── processed/               # FAISS index (gitignored)
│   └── mock/orders.json
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                   # Streamlit chat UI with streaming
├── infrastructure/
│   ├── main.tf                  # Root: compose modules
│   ├── variables.tf / outputs.tf / providers.tf
│   └── modules/
│       ├── networking/          # VPC, subnets, SGs, NAT
│       ├── ecr/                 # Docker image repos
│       └── ecs/                 # Fargate task, ALB, IAM roles (incl. Bedrock access)
├── .github/workflows/
│   ├── ci.yml                   # Lint (ruff) + test (pytest) + Docker build
│   └── cd.yml                   # Push to ECR + terraform apply + ECS deploy
├── docker-compose.yml           # Local dev: backend + frontend
└── .gitignore
```

**Key deps:** `fastapi`, `uvicorn`, `langchain>=0.3`, `langchain-aws`, `langchain-community`, `faiss-cpu`, `pypdf`, `pydantic-settings`, `boto3`, `httpx`, `pytest`

### Phase 1: RAG Pipeline
1. **Ingest** (`rag/ingest.py`): Load PDF with `PyPDFLoader` → chunk with `RecursiveCharacterTextSplitter(1000, 200)` → attach page/section metadata
2. **Embed & Index** (`rag/store.py`): `BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")` → `FAISS.from_documents()` → `save_local()`
3. **Retriever** (`rag/retriever.py`): `vectorstore.as_retriever(search_kwargs={"k": 4})`
4. **Ingestion script** (`backend/scripts/ingest_pdf.py`): CLI to build the FAISS index from the PDF

### Phase 2: Agent with Tool Use
1. **Mock orders** (`mock/order_api.py`): Dict of 4-5 sample orders keyed by `(full_name, last4_ssn, dob)`
2. **Tools** (`agent/tools.py`):
   - `check_order_status(full_name, last4_ssn, date_of_birth)` — validates all 3 fields present, looks up mock DB
   - `search_knowledge_base(query)` — invokes the FAISS retriever, returns formatted context
3. **System prompt** (`agent/prompts.py`): Defines agent role, RAG grounding rules ("only answer from retrieved info"), identity verification rules ("MUST collect all 3 fields before calling order tool"), tone/boundaries
4. **Agent graph** (`agent/graph.py`): `ChatBedrockConverse` + `create_tool_calling_agent` + `AgentExecutor` + `RunnableWithMessageHistory`
5. **Memory** (`agent/memory.py`): `dict[str, ChatMessageHistory]` with `get_session_history(session_id)` factory

### Phase 3: FastAPI Backend
1. **Config** (`config.py`): `BaseSettings` loading `AWS_REGION`, `BEDROCK_MODEL_ID`, `FAISS_INDEX_PATH`
2. **Routes** (`api/routes.py`): `POST /api/chat` with SSE streaming via `agent.astream_events(version="v2")` → `StreamingResponse`
3. **App** (`main.py`): CORS middleware, lifespan loading FAISS index, route registration
4. **Dockerfile**: `python:3.11-slim`, multi-stage build, bake FAISS index into image

### Phase 4: Streamlit Frontend
1. **Chat UI** (`frontend/app.py`): `st.chat_message` + `st.chat_input`, session_id in `st.session_state`
2. **Streaming**: `httpx.AsyncClient` calling `/api/chat` SSE endpoint, incremental token display
3. **UX**: Tool call indicators ("Verifying identity..."), "New Conversation" button in sidebar

### Phase 5: Terraform Infrastructure
1. **Networking**: VPC, 2 public + 2 private subnets, NAT Gateway, security groups
2. **ECR**: Two repos (`backend`, `frontend`) with lifecycle policy (keep 5 images)
3. **ECS**: Fargate cluster, task definition (0.25 vCPU / 0.5 GB), task role with `bedrock:InvokeModel*`, ALB with target group, CloudWatch Logs
4. **Root**: Compose modules, variables, outputs

### Phase 6: CI/CD
1. **CI** (`.github/workflows/ci.yml`): On push/PR → lint (ruff), test (pytest), docker build, terraform validate + plan
2. **CD** (`.github/workflows/cd.yml`): On push to main → build+push images to ECR, terraform apply, ECS force deploy

---

## Critical Integration Points
- **Streaming chain**: Bedrock → LangChain `astream_events` → FastAPI SSE → Streamlit httpx → UI. Each link must handle errors.
- **Agent tool routing**: System prompt must be precise enough for correct tool selection (RAG vs order status).
- **Identity verification**: Defense-in-depth — both the system prompt AND the tool function validate all 3 fields are present.
- **FAISS lifecycle**: Built offline, baked into Docker image. PDF/chunking changes require re-ingestion + rebuild.
- **Bedrock IAM**: ECS task role must have `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` permissions.

---

## Verification Plan
1. **Unit tests**: RAG retrieval accuracy, tool input validation, mock order lookup
2. **Integration test**: Full agent flow — ask a 10-K question, then check order status with identity verification
3. **Local test**: `docker-compose up` → open Streamlit → test both RAG Q&A and order status workflow with streaming
4. **Infra test**: `terraform plan` validates, `terraform apply` creates resources, ECS task starts and passes health check
5. **Demo recording**: Show (1) RAG Q&A with source grounding, (2) order status with multi-turn identity collection, (3) streaming responses, (4) error handling for missing/invalid inputs
