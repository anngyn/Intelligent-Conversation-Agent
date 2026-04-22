# Demo Slides Outline

## Slide 1: Title

**Agentic Conversational System**  
Cloud Kinetics SA AI/Data Intern Assignment

Subtitle:
- grounded RAG
- secure order lookup
- AWS-native deployment

## Slide 2: Problem

Business need:
- answer questions from company documents
- handle secure order status requests
- keep experience conversational and operationally safe

Key architecture question:
- how to choose right data store for each workload instead of forcing one storage model everywhere

## Slide 3: Solution Summary

Implemented:
- Streamlit frontend
- FastAPI backend
- Bedrock Claude 3 Haiku
- FAISS retrieval
- DynamoDB conversation history
- PostgreSQL operational data
- ECS deployment
- CloudWatch observability baseline

## Slide 4: AWS Architecture

Show diagram from:
- [system-architecture-aws.drawio](/D:/An/Project/Assignment/docs/system-architecture-aws.drawio)

Talking points:
- ALB in front of frontend service
- backend private
- ECS frontend and backend split
- Bedrock for generation and embeddings
- CloudWatch for logs and monitoring

## Slide 5: Data Split By Access Pattern

| Data type | Store | Why |
|---|---|---|
| Conversation history | DynamoDB | Append by session, ordered replay, TTL |
| Customer and order operations | PostgreSQL | Relational integrity and indexed lookup |
| Vector retrieval corpus | FAISS | Small corpus, lowest cost floor |

Core message:
- right store for right workload

## Slide 6: Feature 1 - Grounded RAG

Flow:
1. user asks document question
2. backend retrieves relevant chunks from FAISS
3. agent calls Bedrock with grounded context
4. answer streams back to frontend

What to emphasize:
- grounded answer
- reduced hallucination risk
- current vector choice is cost-aware

## Slide 7: Feature 2 - Secure Order Lookup

Flow:
1. user asks for order status
2. agent collects full name, SSN last 4, DOB
3. backend uses PostgreSQL for operational lookup
4. order status returned only after verification

What to emphasize:
- multi-turn identity collection
- defense-in-depth validation
- separation between session data and operational data

## Slide 8: Why DynamoDB For Conversation History

Structure:
- `session_id`
- ordered message key
- message content, role, metadata, TTL

Reasons:
- matches chat access pattern exactly
- easy horizontal scale
- low idle cost
- better fit than relational DB for session replay

## Slide 9: Why PostgreSQL For Orders

Structure:
- `customers`
- `orders`
- `order_items`

Reasons:
- relational business data
- indexed identity verification lookup
- integrity matters
- stronger operational fit than DynamoDB

## Slide 10: Why FAISS Now, OpenSearch Later

Current:
- FAISS implemented
- enough for small corpus
- lowest cost

Future:
- OpenSearch optional when corpus size, filtering, or concurrency justify managed vector search

Message:
- not anti-OpenSearch
- just not worth current cost floor

## Slide 11: Observability Baseline

Implemented:
- structured JSON logs
- PII redaction
- custom CloudWatch metrics
- dashboard
- alarms

Metrics worth naming:
- `AgentLatency`
- `RAGRetrievalTime`
- `OrderStoreLatency`
- `ConversationReadLatency`
- `ConversationWriteLatency`

## Slide 12: Cost and Scale Story

Current design:
- AWS-native where it adds value
- avoid premature managed vector cost
- preserve migration path

Scale path:
- DynamoDB handles conversation growth
- PostgreSQL handles operational data growth
- ECS scales frontend/backend horizontally
- OpenSearch reserved for larger retrieval workload

## Slide 13: Demo Flow

Demo sequence:
1. RAG question
2. out-of-scope question
3. order status workflow
4. follow-up question using session context
5. short architecture explanation

## Slide 14: Key Design Decisions

Messages to land:
- separated data by access pattern
- kept current implementation cost-aware
- implemented baseline observability, not just functional features
- production path documented without overbuilding now

## Slide 15: Current State vs Future State

Implemented now:
- DynamoDB conversation persistence
- PostgreSQL operational store
- FAISS retrieval
- CloudWatch baseline observability

Future options:
- OpenSearch
- X-Ray
- LangSmith
- richer evaluation and alert routing

## Slide 16: Closing

Strong closing line:

`Main architecture decision was to separate conversation state, operational business data, and retrieval data by access pattern, then keep current implementation cost-aware while preserving a clear path to production scale.`

## Presenter Notes

Do:
- explain trade-offs directly
- separate implemented items from optional next steps
- emphasize structure, indexing, scalability, and cost

Do not:
- say order data is still mock-only
- say conversation history is in-memory only
- say OpenSearch is already implemented
- say Level 300 was skipped
