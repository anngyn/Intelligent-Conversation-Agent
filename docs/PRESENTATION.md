# Agentic Conversational System - Presentation Guide

## 1. Positioning

The best way to present this project for an SA AI/Data interview is:
- start from the problem and access patterns
- explain why each storage and compute choice was made
- show that the system is observable and deployable
- keep future-state items clearly separated from implemented items

This presentation guide is written to match the repo as it exists now.

## 2. One-Minute Summary

**Problem**
- Build an e-commerce conversational agent that can answer document-based questions and securely check order status

**Implemented solution**
- Streamlit frontend and FastAPI backend on ECS
- RAG over a company document corpus using FAISS
- DynamoDB-backed conversation history
- PostgreSQL-backed customer and order operations
- CloudWatch logging, metrics, dashboard, and alarms

**Architecture message**
- Use the right storage model for the right access pattern
- Keep the current design cost-aware
- Document the production-scale migration path instead of overbuilding too early

## 3. Architecture Summary

### Runtime topology
- ALB exposes the frontend ECS service
- Frontend calls a private backend ECS service
- Backend uses Bedrock for model inference
- Backend reads and writes conversation history in DynamoDB
- Backend reads customer and order operational data from PostgreSQL
- Backend performs vector retrieval from FAISS

### Data split

| Data type | Store | Why |
|---|---|---|
| Conversation history | DynamoDB | Session-based append and ordered read, low idle cost |
| Customer and order operations | PostgreSQL | Relational integrity, indexed operational lookup |
| Vector retrieval corpus | FAISS | Small current corpus, lowest cost floor |

### Optional future path
- Replace FAISS with OpenSearch when corpus size, filtering requirements, or concurrency justify a managed vector store

## 4. Key Design Decisions

### Decision 1: DynamoDB for conversation history

**Structure**
- Partition key: `session_id`
- Sort key: timestamp-based message key
- Attributes: role, content, metadata, ttl

**Why this works**
- Matches the dominant access pattern exactly:
  - append a message
  - fetch ordered messages for one session
  - expire old sessions

**Indexing**
- No secondary indexes are needed for the current workload
- Primary key alone supports the critical read path

**Scalability**
- Good fit for horizontal ECS scaling and concurrent chat sessions
- No connection-pool overhead
- TTL gives a simple retention model

**Why not PostgreSQL here**
- More operational overhead than necessary for chat history
- Higher cost floor if used only for session storage

### Decision 2: PostgreSQL for customer and order operations

**Structure**
- `customers`
- `orders`
- `order_items`

**Why this works**
- The domain is relational
- The operational lookup path benefits from consistency and data integrity
- It is easier to express customer-to-order relationships in SQL than in a key-value store

**Indexing**
- Identity verification uses normalized and hashed identity fields
- Orders are indexed for customer lookup and recency

**Scalability**
- Current scale fits a small RDS deployment
- Future scale path is straightforward: larger instance, replicas, or Aurora if needed

**Why not DynamoDB here**
- The access pattern is not a simple append/read session model
- Relational constraints and multi-table queries matter

### Decision 3: FAISS now, OpenSearch later

**Current choice**
- FAISS is the implemented vector store

**Why**
- Small corpus
- Near-zero cost
- Fast enough for the current document set

**Optional production path**
- OpenSearch becomes attractive when:
  - corpus size grows significantly
  - hybrid or filtered search becomes important
  - multiple services need to share managed vector infrastructure

**Why OpenSearch is optional**
- It is a good production vector option, but its cost floor is high for the current assignment scale

## 5. Observability Story

This project now has a practical AWS-native observability baseline.

### Implemented
- Structured JSON logs
- PII redaction
- EMF custom metrics
- CloudWatch dashboard
- CloudWatch alarms

### Metrics that matter
- `AgentLatency`
- `RAGRetrievalTime`
- `OrderStoreLatency`
- `ConversationReadLatency`
- `ConversationWriteLatency`
- request and error counts

### Why this matters for SA AI/Data
- AI systems fail in ways that plain infrastructure metrics do not explain
- Retrieval latency, tool behavior, and operational lookup health are first-class signals
- The system is easier to debug and safer to operate

## 6. Cost and Scale Narrative

### Current-state philosophy
- right-sized for assignment scale
- avoid premature managed-service cost where not justified
- still use AWS-native building blocks where they clearly fit

### Scale path by subsystem

**Conversation history**
- DynamoDB scales naturally with session volume

**Operational data**
- PostgreSQL can scale vertically first, then through replicas or Aurora-style evolution

**Vector search**
- FAISS is enough now
- OpenSearch is the next step when the corpus or concurrency grows

**Application layer**
- ECS services scale horizontally as traffic grows

## 7. Suggested Presentation Flow

1. Explain the problem in one sentence.
2. Show the running product with two workflows:
   - grounded RAG answer
   - identity-gated order lookup
3. Explain the data split and why it exists.
4. Explain observability and operations baseline.
5. Close with cost-aware scale path.

## 8. Good Interview Answers

### Why DynamoDB instead of PostgreSQL for chat history?
Because the access pattern is narrow and predictable: append by session and read ordered messages by session. DynamoDB fits that pattern with lower operational overhead and lower idle cost.

### Why PostgreSQL instead of DynamoDB for orders?
Because customer and order data is relational operational data. Data integrity and indexed identity-based lookup matter more than the elasticity benefits of a key-value store.

### Why not OpenSearch already?
Because the current corpus does not justify the additional managed-service cost. FAISS is enough today, and OpenSearch is reserved for the point where search scale or filtering requirements make it worth paying for.

### What shows production readiness here?
Separate frontend and backend services, storage chosen by access pattern, private backend path, CloudWatch dashboard and alarms, and explicit migration paths instead of hidden assumptions.

## 9. What To Avoid

- Do not say everything is fully production-hardened
- Do not claim OpenSearch, LangSmith, or X-Ray are already implemented
- Do not describe conversation memory as in-memory only
- Do not blur the difference between operational data and retrieval data

## 10. Closing Message

The strongest closing line is:

`The main architecture decision was to separate conversation state, operational business data, and retrieval data by access pattern, then keep the current implementation cost-aware while preserving a clear path to production scale.`
