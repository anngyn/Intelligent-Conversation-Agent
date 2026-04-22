# CLAUDE.md - Agentic Conversational System

## WHY (Project Purpose)
We are building a scalable, production-ready Agentic Conversational system for a US-based e-commerce company.
The agent performs two core tasks:
1. **Knowledge-based Q&A:** Uses RAG to answer queries based on internal documents (e.g., the company's 10-K financial reports) while minimizing hallucinations.
2. **Tool-Based Workflow:** Checks order shipment status. The agent MUST securely verify the user's Full Name, Last 4 digits of SSN, and Date of Birth before executing the tool.
The system supports multi-turn conversations and maintains context memory across turns.

## WHAT (Tech Stack & Structure)
- **Backend/AI:** Python, FastAPI, LangChain/LlamaIndex (Model inference & core agent logic).
- **Infrastructure:** AWS via Infrastructure as Code (e.g., CDK, Terraform, or CloudFormation) [7].
- **Data/Observability:** Vector Store for retrieval, Relational/NoSQL database for conversation history [7, 8].

**Monorepo Map:**
- `/backend` - Core conversational agent, memory handling, and RAG implementation.
- `/infrastructure` - AWS IaC scripts for deploying the web app, inference layer, and vector store [7].
- `/dataset` - Internal documents and data preprocessing pipelines for RAG [9].
- `/frontend` - (Optional) Web app layer with streaming response support [10].


### Key Implementation Files
- `backend/app/agent/graph.py` - Agent construction (LangChain ReAct)
- `backend/app/agent/prompts.py` - System prompt (critical for behavior)
- `backend/app/rag/ingest.py` - PDF chunking and metadata extraction
- `backend/app/api/routes.py` - FastAPI SSE streaming
- `backend/app/mock/order_api.py` - Mock order database
- `infrastructure/main.tf` - Complete AWS infrastructure


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
- ✅ Level 300 (Partial): Security, failure handling, RAG quality, memory management
  - ✅ PII security (hash SSN/DOB, log redaction)
  - ✅ Failure handling (Bedrock retry, SSE keepalive, graceful degradation)
  - ✅ RAG quality (strict grounding prompts, citations, basic eval tests)
  - ✅ Memory strategy (token counting, summarization at 6K tokens)