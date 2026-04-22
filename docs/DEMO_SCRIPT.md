# Demo Recording Script - Agentic Conversational System

**Assignment:** Cloud Kinetics SA AI/Data Intern  
**Duration:** 4-5 minutes  
**Goal:** Show the implemented system and explain the architecture decisions behind it

---

## Demo Storyline

The strongest demo for this repo is:

1. Show grounded knowledge Q&A through RAG
2. Show secure order lookup with identity verification
3. Show that the architecture is intentionally split by data access pattern
4. Close with cost, scale, and observability trade-offs

This aligns better with an SA AI/Data role than a feature-only walkthrough.

---

## Pre-Demo Setup

**Local runtime**
```powershell
# Terminal 1
cd backend
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend
streamlit run app.py
```

**Browser tabs**
- Frontend UI: `http://localhost:8501`
- Optional: AWS architecture diagram
- Optional: CloudWatch dashboard screenshot or Terraform files

---

## 1. Opening: 20-30 seconds

> "This project is an agentic conversational system for an e-commerce use case. It handles two tasks: grounded Q&A over company documents and secure order lookup with identity verification.
>
> I designed the data layer by access pattern: DynamoDB for conversation history, PostgreSQL for operational customer and order data, and FAISS for vector retrieval at the current scale. I also deployed a production-style AWS architecture with ECS, ALB, CloudWatch monitoring, and CI/CD."

**On screen**
- Start on the chat UI

---

## 2. RAG Demo: 60-90 seconds

**Prompt**
`What were Amazon's primary revenue sources in 2023?`

**Narration**
> "For document Q&A, the agent uses retrieval-augmented generation. The PDF is chunked, embedded with Bedrock embeddings, and retrieved from a FAISS index. The answer is grounded in retrieved context rather than free-form model memory."

**What to point out**
- Streaming response
- Tool-use indicator if visible
- Grounded answer with citations or source references

**Boundary check**
Prompt:
`What's the weather in Seattle today?`

> "If the question is outside the allowed scope, the system refuses rather than hallucinating. That behavior is enforced by both prompt design and tool boundaries."

---

## 3. Order Lookup Demo: 90 seconds

**Prompt**
`Check my order status`

**Narration**
> "The second workflow is an operational lookup flow. Before the tool runs, the agent must collect full name, last 4 digits of SSN, and date of birth."

**Walk through**
- Provide full name
- Provide last 4 digits
- Provide DOB

> "This is not just prompt-level guidance. The order lookup path is backed by PostgreSQL and validates identity through normalized and hashed fields before returning order status."

**Follow-up prompt**
`When will it arrive?`

> "The agent preserves session context across turns. That history is persisted in DynamoDB so it survives multi-task and multi-instance deployment, which is more production-appropriate than in-memory chat history."

---

## 4. Architecture Explanation: 60 seconds

Use the AWS diagram or the architecture doc.

> "The runtime is split into a frontend ECS service and a backend ECS service. The frontend sits behind an ALB, and the backend stays private.
>
> I separated storage by workload:
> - DynamoDB for conversation history, because the access pattern is session-based append and ordered read
> - PostgreSQL for customer and order operations, because that data benefits from relational integrity and indexed lookup
> - FAISS for vector retrieval, because the current corpus is small and FAISS has near-zero cost
>
> OpenSearch is the optional next step for production-scale vector retrieval, but I kept it out of the current implementation because its cost floor is high relative to this assignment."

---

## 5. Observability and Operations: 30-45 seconds

> "I also added a practical observability baseline:
> - structured JSON logs
> - custom CloudWatch metrics for agent latency, retrieval latency, order lookup latency, and conversation store latency
> - a CloudWatch dashboard
> - alarms for high latency, stream failures, and unhealthy frontend targets
>
> This is enough to show that the system is operable, not just functional."

If available, show:
- CloudWatch dashboard screenshot
- Terraform monitoring resources

---

## 6. Design Decisions and Trade-offs: 45 seconds

> "The key solution-architect decisions in this project are about choosing the right store for the right access pattern.
>
> DynamoDB is better than PostgreSQL for conversation history because it scales naturally for session-based append/read and keeps the cost floor low.
>
> PostgreSQL is better than DynamoDB for customer and order operations because the data is relational and benefits from indexed lookups and data integrity constraints.
>
> FAISS is the right vector store today because the document corpus is small. If the corpus or concurrency grows enough to justify managed vector infrastructure, OpenSearch is the next step."

---

## 7. Close: 15-20 seconds

> "So the main value of this project is not just that the agent works. It is that the architecture, data model, and operations choices are explicit and production-oriented for the scale of the problem.
>
> That is the mindset I wanted to demonstrate for the SA AI/Data role."

---

## Optional Talking Points If Asked

### Why DynamoDB for conversation history
- Access pattern is narrow and predictable
- Partition by `session_id`, sort by message key
- Natural fit for TTL and horizontal scale
- Lower idle cost than keeping a relational database just for chat history

### Why PostgreSQL for order and customer data
- Relational model fits customer to orders to order items
- Stronger integrity guarantees
- Easier operational queries and indexing for identity verification

### Why not OpenSearch right now
- Strong production option for vector search
- But cost floor is high for a small assignment-scale corpus
- FAISS is enough now; OpenSearch is a documented migration path

### Why ECS Fargate
- Better fit for always-on streaming app behavior than Lambda
- Cleaner deployment model for frontend and backend services

---

## Demo Checklist

- Backend runs on port `8000`
- Frontend runs on port `8501`
- RAG query returns a grounded answer
- Order lookup path works with known seed data
- Follow-up question shows conversation context
- Architecture diagram is ready
- Monitoring screenshot or Terraform file is ready

---

## What Not To Say

- Do not say the system still uses in-memory chat history
- Do not say the order system is still mock-only if you are describing the current design
- Do not claim OpenSearch is already implemented
- Do not over-claim LangSmith or X-Ray as completed

Be precise:
- `implemented now`
- `production next step`
- `optional due to cost`
