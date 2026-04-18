# CLAUDE.md - Agentic Conversational System

## WHY (Project Purpose)
We are building a scalable, production-ready Agentic Conversational system for a US-based e-commerce company [3].
The agent performs two core tasks:
1. **Knowledge-based Q&A:** Uses RAG to answer queries based on internal documents (e.g., the company's 10-K financial reports) while minimizing hallucinations [4, 5].
2. **Tool-Based Workflow:** Checks order shipment status. The agent MUST securely verify the user's Full Name, Last 4 digits of SSN, and Date of Birth before executing the tool [3, 6].
The system supports multi-turn conversations and maintains context memory across turns [7].

## WHAT (Tech Stack & Structure)
- **Backend/AI:** Python, FastAPI, LangChain/LlamaIndex (Model inference & core agent logic).
- **Infrastructure:** AWS via Infrastructure as Code (e.g., CDK, Terraform, or CloudFormation) [7].
- **Data/Observability:** Vector Store for retrieval, Relational/NoSQL database for conversation history [7, 8].

**Monorepo Map:**
- `/backend` - Core conversational agent, memory handling, and RAG implementation.
- `/infrastructure` - AWS IaC scripts for deploying the web app, inference layer, and vector store [7].
- `/dataset` - Internal documents and data preprocessing pipelines for RAG [9].
- `/frontend` - (Optional) Web app layer with streaming response support [10].

## HOW (Working on this Project)

### Development Commands
```bash
# Setup
cd backend && pip install -e ".[dev]"

# Build FAISS index (required before first run)
python backend/scripts/ingest_pdf.py

# Run backend
cd backend && python -m app.main

# Run frontend (separate terminal)
cd frontend && streamlit run app.py

# Run tests
cd backend && pytest -v

# Lint
cd backend && ruff check . && ruff format .

# Docker (alternative)
docker-compose up --build
```

### Key Implementation Files
- `backend/app/agent/graph.py` - Agent construction (LangChain ReAct)
- `backend/app/agent/prompts.py` - System prompt (critical for behavior)
- `backend/app/rag/ingest.py` - PDF chunking and metadata extraction
- `backend/app/api/routes.py` - FastAPI SSE streaming
- `backend/app/mock/order_api.py` - Mock order database
- `infrastructure/main.tf` - Complete AWS infrastructure

### Testing Accounts
| Name | Last 4 SSN | DOB | Order Status |
|------|------------|-----|--------------|
| John Smith | 1234 | 1990-01-15 | Shipped |
| Jane Doe | 5678 | 1985-06-20 | Delivered |
| Michael Johnson | 9012 | 1992-11-03 | Processing |
| Emily Chen | 3456 | 1988-03-12 | Out for Delivery |

### Guidelines
- Run `ruff` for linting, not manual formatting
- FAISS index must be built before backend starts
- AWS credentials with Bedrock access required
- Verify your changes by running tests locally before committing

## Progressive Disclosure (Task-Specific Context)
For detailed setup instructions, see `docs/SETUP.md`

**Implementation Status:**
- ✅ Level 100: Core agent, RAG, tools, memory, streaming
- ✅ Level 200: Terraform IaC, GitHub Actions CI/CD, Docker
- ❌ Level 300: Not implemented (out of chosen scope)