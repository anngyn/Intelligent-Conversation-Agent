# System Architecture

## Overview

System built around three concerns:
- user interaction
- agent runtime
- data stores chosen by access pattern

Current implementation already includes Level 300 baseline for persistence and observability.

## Runtime Topology

### User-facing flow
`User -> ALB -> frontend ECS service -> backend ECS service -> Bedrock`

### Service split
- frontend service: Streamlit UI
- backend service: FastAPI, LangChain agent, retrieval, tool execution
- backend stays private
- frontend reaches backend through internal service discovery

This split better matches production deployment than single-container demo topology.

## Data Architecture

### 1. Conversation history
- store: DynamoDB
- reason: session-based append and ordered read
- shape:
  - partition key: `session_id`
  - sort key: ordered message key
  - attributes: role, content, metadata, ttl

### 2. Customer and order operations
- store: PostgreSQL
- reason: relational operational data with indexed identity lookup
- shape:
  - `customers`
  - `orders`
  - `order_items`

### 3. Retrieval corpus
- store: FAISS
- reason: current corpus small, cost floor near zero
- future path: OpenSearch if corpus size or filtering needs justify managed vector search

## Component View

```
┌────────────────────────────────────────────────────────────┐
│ User                                                       │
└───────────────────────────────┬────────────────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ ALB                    │
                    │ public entrypoint      │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Frontend ECS Service   │
                    │ Streamlit              │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Backend ECS Service    │
                    │ FastAPI + LangChain    │
                    │ SSE streaming          │
                    └──────┬────────┬────────┘
                           │        │
                           │        └───────────────┐
                           │                        │
                           ▼                        ▼
                ┌──────────────────┐      ┌──────────────────┐
                │ DynamoDB         │      │ PostgreSQL       │
                │ conversation     │      │ customers/orders │
                │ history          │      │ operations       │
                └──────────────────┘      └──────────────────┘
                           │
                           ▼
                ┌──────────────────┐
                │ FAISS            │
                │ vector index     │
                └──────────────────┘
                           │
                           ▼
                ┌──────────────────┐
                │ AWS Bedrock      │
                │ Claude + Embed   │
                └──────────────────┘
```

## Request Flows

### Grounded RAG query
1. user sends question from frontend
2. backend receives request and loads conversation history from DynamoDB
3. agent decides retrieval needed
4. backend queries FAISS index
5. retrieved context sent to Bedrock
6. grounded answer streamed back to frontend
7. conversation state appended to DynamoDB

### Order status workflow
1. user asks to check order status
2. agent collects required identity fields across turns
3. backend reads and writes session history in DynamoDB
4. once all fields present, tool executes operational lookup in PostgreSQL
5. backend returns order status only
6. follow-up questions reuse session context

## Security Architecture

### Network
- frontend exposed through ALB
- backend private
- private compute in VPC

### Identity and access
- IAM least privilege for ECS tasks
- backend granted Bedrock access
- backend granted DynamoDB access for conversation table
- secrets handled outside source code

### PII handling
- order workflow requires identity verification before lookup
- logs use PII redaction
- operational identity matching uses normalized and hashed fields
- retrieval data, session data, and operational data remain separate

## Observability Architecture

Implemented now:
- structured JSON logs
- EMF custom metrics
- CloudWatch dashboard
- CloudWatch alarms

Main signals:
- HTTP request latency and error count
- agent latency
- RAG retrieval latency
- order store latency
- conversation store read/write latency
- unhealthy frontend targets

This gives enough baseline visibility for AI-specific runtime behavior without adding heavier tracing systems yet.

## Scalability

### Current state
- ECS services scale from current task settings
- DynamoDB conversation model supports concurrent sessions well
- PostgreSQL handles current operational lookup path
- FAISS remains acceptable for current corpus size

### Future state
- increase ECS desired count as traffic grows
- scale PostgreSQL vertically first, then replicas or Aurora-style path if needed
- move from FAISS to OpenSearch when vector workload justifies managed search

## Design Decisions

### Why DynamoDB for memory
- access pattern narrow and predictable
- better fit than relational storage for session history
- good horizontal scaling behavior

### Why PostgreSQL for orders
- operational data relational by nature
- joins, indexing, and integrity constraints matter
- stronger business-data fit than DynamoDB

### Why FAISS for retrieval
- assignment corpus small
- cost-aware
- simple local retrieval path

### Why not OpenSearch yet
- valid production option
- cost floor too high for current scale
- kept as optional future step, not forced into current implementation

## Current vs Future State

### Implemented now
- frontend/backend split on ECS
- DynamoDB-backed conversation persistence
- PostgreSQL-backed operational data
- FAISS retrieval
- CloudWatch logs, metrics, dashboard, alarms

### Future enhancements
- OpenSearch for managed vector retrieval
- X-Ray tracing
- LangSmith traces
- richer alert routing and evaluation pipeline

## Architecture Message For Review

`Main architecture choice was to separate session state, operational business data, and retrieval data by access pattern, then keep current implementation cost-aware while preserving a clear production migration path.`
