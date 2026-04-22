# Level 300: Observability & Monitoring Design

## Implemented Baseline In This Repo

This repo now includes a working observability baseline that is intentionally sized for an intern-assignment scope.

**Implemented now**
- Structured JSON logging in the backend runtime
- Basic PII redaction before logs leave the application
- CloudWatch Embedded Metric Format (EMF) emission without extra sidecars
- HTTP request latency and error metrics at the FastAPI entrypoint
- End-to-end agent latency metrics for streaming chat requests
- RAG retrieval latency and document count metrics
- Tool-call latency and success/failure metrics
- PostgreSQL order lookup latency and success/failure metrics
- DynamoDB conversation read/write latency metrics
- Terraform-provisioned CloudWatch dashboard for traffic, latency, store latency, and service health
- Terraform-provisioned CloudWatch alarms for chat latency, RAG latency, order-store latency, chat stream failures, and unhealthy frontend tasks

**Implemented metric names**
- `HttpRequestLatency`
- `HttpRequestCount`
- `HttpServerError`
- `AgentLatency`
- `ChatRequests`
- `ConversationTurns`
- `RAGRetrievalTime`
- `RAGDocumentsRetrieved`
- `ToolCallLatency`
- `ToolCallSuccess`
- `OrderLookupSuccess`
- `OrderLookupFailure`
- `OrderStoreLatency`
- `OrderStoreLookup`
- `ConversationReadLatency`
- `ConversationWriteLatency`

**Not implemented yet**
- X-Ray distributed tracing
- LangSmith traces
- SNS, Slack, or PagerDuty alert routing
- Cost-specific Bedrock token and spend metrics

The rest of this document describes the target production state beyond the baseline already implemented in code and Terraform.

## Previous State (Before This Baseline)

Before this baseline, the system only had container logs in CloudWatch and generic Python logging. That meant:
- No structured request correlation
- No custom metrics for agent, retrieval, or storage latency
- No alarms to detect degraded service before users reported it
- No dashboard view to separate frontend health from backend latency

That was acceptable for local development, but weak for a production-oriented architecture discussion.

## Why This Observability Scope

The goal for this assignment is not to build a full enterprise observability platform. The goal is to prove three architecture decisions:

1. The system is debuggable when an agent workflow fails.
2. The system exposes the right latency and failure signals for AI-specific operations.
3. The baseline cost stays small enough for a demo-scale deployment.

This is why the repo currently uses:
- CloudWatch logs and EMF metrics as the baseline
- Terraform-managed dashboards and alarms
- Optional future upgrades for X-Ray and LangSmith

## Current Instrumentation Map

### HTTP layer
- Request completion and failure logs
- Request latency metric
- Server error count

### Agent layer
- End-to-end streaming latency
- Conversation turn count
- Tool-call count and latency

### Retrieval layer
- RAG retrieval latency
- Number of documents returned per query

### Operational data layer
- Order lookup latency
- Order lookup success/failure

### Conversation state layer
- DynamoDB conversation read latency
- DynamoDB conversation write latency
- Number of messages read and written

## Dashboard Design

The CloudWatch dashboard in Terraform focuses on the signals that matter most for this system:
- Traffic and chat request volume
- Agent latency trend
- RAG retrieval latency
- Order store latency
- Conversation store latency
- ECS CPU and ALB healthy target count

This is intentional. For an AI/data workload, the first operational question is usually not "is the container up?" but:
- Is the agent slow?
- Is retrieval slow?
- Is operational data lookup failing?
- Is the user-facing service still healthy?

## Alarm Design

The implemented alarms cover the highest-value failure modes:

| Alarm | Signal | Why it matters |
|---|---|---|
| `agent_latency_high` | `AgentLatency` p99 | User-facing degradation |
| `rag_retrieval_latency_high` | `RAGRetrievalTime` p95 | Retrieval bottleneck or index issue |
| `order_store_latency_high` | `OrderStoreLatency` p95 | Operational lookup degradation |
| `chat_stream_errors` | `ErrorRate` sum | Streaming/API failure path |
| `frontend_unhealthy_hosts` | ALB healthy hosts | User-facing outage |

These alarms intentionally avoid overfitting to every possible edge case. They cover latency, correctness path, and service health with minimal noise.

## Production Target State

If this system moved beyond assignment scope, the next observability upgrades would be:

### 1. X-Ray
Use X-Ray to trace:
- ALB to frontend
- Frontend to backend
- Backend to Bedrock
- Backend to DynamoDB
- Backend to PostgreSQL

This would answer bottleneck questions faster than logs alone.

### 2. LangSmith
Use LangSmith to inspect:
- Tool selection behavior
- Prompt and response traces
- Retrieval grounding quality
- Token usage and agent loop details

This is more valuable for agent-debugging than for generic API monitoring.

### 3. Alert routing
Attach SNS to alarms and route:
- Critical alarms to PagerDuty
- Warning alarms to Slack
- Informational notifications to email

## Design Decision Summary

### Why CloudWatch first
- Native to ECS, ALB, DynamoDB, and RDS
- Minimal operational overhead
- Good enough for assignment-scale production reasoning
- Demonstrates AWS-native SA thinking

### Why not start with Datadog/New Relic
- Higher cost floor
- More integration work
- Less relevant than AWS-native tooling for this assignment

### Why not jump straight to LangSmith
- Useful, but not necessary to prove baseline production readiness
- Better positioned as a next-step enhancement once baseline metrics and alarms exist

## Cost Framing

The current observability baseline is intentionally low-cost:
- CloudWatch logs
- A small set of custom metrics
- One dashboard
- A handful of alarms

That keeps the baseline significantly cheaper than introducing a full commercial APM stack, while still proving the architecture is observable and operable.

## SA AI/Data Talking Point

The key message is:

`I treated observability as part of the system design, not as an afterthought.`

For an AI/data workload, that means exposing signals for:
- response latency
- retrieval quality proxies
- tool execution behavior
- operational data lookup health

The repo now implements that baseline and documents a clear upgrade path to deeper tracing and agent-level evaluation.
