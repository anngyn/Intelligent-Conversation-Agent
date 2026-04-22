# Level 300: Data Design & Persistent Storage

## Implemented In This Repo

**Current implemented data split:**
- `DynamoDB` for conversation history
- `PostgreSQL` for operational customer/order data
- `FAISS` for vector retrieval

**Why this split fits the workload:**

| Data Type | Current Store | Access Pattern | Why It Fits |
|-----------|---------------|----------------|-------------|
| Conversation history | DynamoDB | Append by session, read ordered history, TTL expiry | Key-value/time-ordered workload with low ops overhead |
| Customer + order operations | PostgreSQL | Identity verification, relational integrity, order-to-customer joins | Operational data needs schema, constraints, and indexing |
| Vector search | FAISS | Small local corpus, low QPS similarity search | Lowest-cost option at current scale |

**Optional production evolution:**
- Keep `FAISS` while corpus stays small and static
- Move to `OpenSearch` only when document volume, metadata filtering, or hybrid search justify the fixed cost

This document contains both the implemented baseline and a larger production target-state design. When discussing the current repo, treat DynamoDB + PostgreSQL + FAISS as the authoritative implementation.

## Previous State (Before This Baseline)

**Problem:**
```python
# backend/app/agent/memory.py
_session_store: dict[str, ChatMessageHistory] = {}  # In-memory only
```

**Limitations:**
- Conversations lost on container restart/redeploy
- No cross-container session sharing (can't scale horizontally)
- No conversation history for analytics
- No audit trail for compliance

**When this breaks:** First ECS task restart, user loses conversation mid-chat.

## Design Goals

1. **Persistence:** Survive restarts, redeploys, scaling events
2. **Performance:** <100ms read/write latency for chat history
3. **Cost:** <$10/mo for demo usage (1000 sessions/day, 10 turns/session, 7-day retention)
4. **Scalability:** Support horizontal scaling (multiple ECS tasks)
5. **Compliance:** PII handling, audit logs, data retention policies

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   FastAPI    │──────│    Agent     │──────│    RAG    │ │
│  │   Routes     │      │   Executor   │      │ Retriever │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                            │
│         │ Store/Load           │ Store/Load                 │
│         ▼                      ▼                            │
└─────────────────────────────────────────────────────────────┘
         │                      │
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│                                                              │
│  ┌──────────────────────┐        ┌──────────────────────┐  │
│  │   DynamoDB Table     │        │   PostgreSQL/RDS     │  │
│  │   conversations      │        │   orders DB          │  │
│  │   (chat history)     │        │   (operational)      │  │
│  └──────────────────────┘        └──────────────────────┘  │
│                                                              │
│  ┌──────────────────────┐        ┌──────────────────────┐  │
│  │   DynamoDB Table     │        │   S3 Bucket          │  │
│  │   analytics          │        │   conversation       │  │
│  │   (events)           │        │   archives           │  │
│  └──────────────────────┘        └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Schema Design

### 1. Conversation History (DynamoDB)

**Table:** `ecommerce-agent-conversations`

**Access pattern:** Fetch all messages for a session (single-item read)

**Schema:**
```
Partition Key: session_id (String)
Sort Key: timestamp (Number, epoch milliseconds)

Attributes:
- session_id: String           # UUID v4
- timestamp: Number            # Message creation time (epoch ms)
- message_id: String           # UUID v4 for each message
- role: String                 # "human" | "ai" | "tool"
- content: String              # Message text (up to 400KB)
- metadata: Map                # {tool_calls: [...], citations: [...], tokens: N}
- ttl: Number                  # Auto-delete epoch (7 days from creation)
```

**Indexes:**
- **Primary:** (session_id, timestamp) - Fetch conversation history in order
- **GSI (optional):** timestamp-index - Find all conversations by date range (analytics)

**DynamoDB capacity mode:** On-Demand (pay per request)

**Why DynamoDB:**
| Factor | DynamoDB | RDS PostgreSQL |
|--------|----------|----------------|
| **Latency** | <10ms single-digit | 10-50ms (network + query) |
| **Scaling** | Automatic, unlimited | Manual, vertical limit |
| **Cost (low traffic)** | $1.25/million reads | $15/mo minimum (db.t3.micro) |
| **Schema flexibility** | Schemaless, easy evolution | Migrations required |
| **Ops overhead** | Zero (serverless) | Backups, patching, monitoring |
| **LangChain support** | Native (`DynamoDBChatMessageHistory`) | Custom implementation |

**Decision:** DynamoDB wins for chat history. Low traffic, key-value access pattern, LangChain integration exists.

### 2. Order Database (PostgreSQL/Aurora)

**Current:** Mock JSON in `backend/app/mock/order_api.py`

**Production schema:**

```sql
-- Customers table
CREATE TABLE customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    ssn_hash TEXT NOT NULL,          -- SHA256(SSN + salt)
    dob_hash TEXT NOT NULL,          -- SHA256(DOB + salt)
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(ssn_hash, dob_hash)       -- Prevent duplicate identities
);

CREATE INDEX idx_identity ON customers(ssn_hash, dob_hash);

-- Orders table
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    status TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled')),
    tracking_number TEXT,
    order_date TIMESTAMP NOT NULL,
    estimated_delivery DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_customer_orders ON orders(customer_id, order_date DESC);

-- Order items (optional, for richer data)
CREATE TABLE order_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_name TEXT NOT NULL,
    quantity INT NOT NULL,
    price_cents INT NOT NULL
);
```

**Migration from mock:**
```python
# backend/scripts/migrate_orders.py
import json
import hashlib
from app.mock.order_api import ORDERS

def hash_pii(value: str, salt: str) -> str:
    return hashlib.sha256(f"{value}{salt}".encode()).hexdigest()

SALT = os.environ["PII_SALT"]  # Stored in AWS Secrets Manager

for order in ORDERS:
    # Insert customer (ON CONFLICT DO NOTHING)
    cursor.execute("""
        INSERT INTO customers (full_name, ssn_hash, dob_hash)
        VALUES (%s, %s, %s)
        ON CONFLICT (ssn_hash, dob_hash) DO NOTHING
        RETURNING customer_id
    """, (
        order["customer"]["name"],
        hash_pii(order["customer"]["last4_ssn"], SALT),
        hash_pii(order["customer"]["dob"], SALT)
    ))
    
    # Insert order
    cursor.execute("""
        INSERT INTO orders (order_id, customer_id, status, tracking_number, order_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (...))
```

**Why PostgreSQL:**
| Factor | Consideration |
|--------|---------------|
| **Relational integrity** | Orders → Customers foreign key |
| **Query flexibility** | "Find all orders for customer X", "Orders by status", analytics |
| **ACID transactions** | Critical for order updates |
| **Cost** | Aurora Serverless v2: ~$15/mo (0.5 ACU minimum) |

**Decision:** PostgreSQL for operational data. Relational model fits e-commerce domain.

### 3. Analytics Events (DynamoDB)

**Table:** `ecommerce-agent-analytics`

**Access pattern:** Write-heavy (every agent action), time-series queries (daily reports)

**Schema:**
```
Partition Key: date (String, "YYYY-MM-DD")
Sort Key: timestamp (Number, epoch milliseconds)

Attributes:
- event_id: String             # UUID v4
- session_id: String           # Link to conversation
- event_type: String           # "query" | "tool_call" | "rag_retrieval" | "error"
- tool_name: String            # (if event_type = tool_call)
- latency_ms: Number
- tokens_input: Number
- tokens_output: Number
- cost_usd: Number             # Calculated from tokens
- error_message: String        # (if event_type = error)
- metadata: Map                # Flexible event-specific data
```

**Indexes:**
- **Primary:** (date, timestamp) - Time-series queries
- **GSI:** session_id-index - Lookup all events for a session

**Why separate from conversations:**
- Different access patterns (time-series analytics vs single-session lookup)
- High write volume for analytics shouldn't impact chat history reads
- Can archive old analytics to S3, keep conversations in DynamoDB

### 4. Long-term Archive (S3)

**Bucket:** `ecommerce-agent-conversation-archives`

**Lifecycle:**
1. DynamoDB TTL deletes conversations after 7 days
2. DynamoDB Streams + Lambda export to S3 before deletion
3. S3 objects: `s3://bucket/year=2026/month=04/day=22/session_id.json.gz`
4. S3 Lifecycle: Transition to Glacier after 90 days, delete after 1 year

**Use cases:**
- Compliance: "Provide all conversations for customer X in 2025"
- Training data: Sample archived conversations for model fine-tuning
- Incident investigation: "What happened in production last quarter?"

**Cost:** $0.023/GB/month (S3 Standard) → 1000 conversations × 50KB × 30 days = 1.5GB = $0.03/mo

## Cost Analysis

**Assumptions:**
- 1000 sessions/day
- 10 turns per session (20 messages: 10 user + 10 AI)
- Avg message size: 500 bytes
- 7-day retention in DynamoDB
- 30-day retention in analytics

### DynamoDB Conversations

| Operation | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|--------------|
| **Writes** | 20k writes/day × 30 | $1.25/million | **$0.75** |
| **Reads** | 10k sessions × 20 msgs/session | $0.25/million | **$0.05** |
| **Storage** | 1000 sessions × 10KB × 7 days | $0.25/GB | **$0.02** |
| **Total** | | | **$0.82/mo** |

### DynamoDB Analytics

| Operation | Volume | Unit Cost | Monthly Cost |
|-----------|--------|-----------|--------------|
| **Writes** | 50k events/day × 30 | $1.25/million | **$1.88** |
| **Storage** | 1.5M events × 1KB × 30 days | $0.25/GB | **$0.38** |
| **Total** | | | **$2.26/mo** |

### PostgreSQL (Aurora Serverless v2)

| Resource | Config | Monthly Cost |
|----------|--------|--------------|
| **Compute** | 0.5 ACU minimum | **$43.80** |
| **Storage** | 5GB (orders DB) | **$0.50** |
| **Total** | | **$44.30/mo** |

**Alternative:** RDS PostgreSQL db.t3.micro = $15/mo (not auto-scaling)

### S3 Archives

| Resource | Volume | Monthly Cost |
|----------|--------|--------------|
| **Storage** | 1.5GB | **$0.03** |
| **PUT requests** | 1000/day | **$0.02** |
| **Total** | | **$0.05/mo** |

### Total Data Layer Cost

**DynamoDB-only approach (no RDS):**
- Conversations: $0.82
- Analytics: $2.26
- S3 Archives: $0.05
- **Total: $3.13/mo**

**With PostgreSQL for orders:**
- Above + Aurora Serverless: $47.43/mo
- Above + RDS db.t3.micro: $18.13/mo

**Decision for demo:** Keep mock orders, use DynamoDB for conversations only. Cost = **$3.13/mo**. Production adds RDS ($15-45/mo).

## Migration Plan

### Phase 1: Add DynamoDB persistence (0 downtime)

1. Create DynamoDB table via Terraform
2. Update `backend/app/agent/memory.py`:
```python
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    return DynamoDBChatMessageHistory(
        table_name="ecommerce-agent-conversations",
        session_id=session_id,
        ttl=7 * 24 * 3600  # 7 days
    )
```
3. Deploy: new sessions use DynamoDB, old in-memory sessions expire naturally
4. Test: verify messages persist across container restarts

### Phase 2: Analytics events (additive)

1. Create analytics DynamoDB table
2. Add event logging to `routes.py`, `tools.py`
3. Create CloudWatch dashboard querying analytics table

### Phase 3: Migrate orders to PostgreSQL (breaking change)

1. Provision RDS/Aurora via Terraform
2. Run `migrate_orders.py` script to populate DB
3. Update `backend/app/mock/order_api.py` → `backend/app/db/order_repository.py`
4. Deploy with database connection string in env vars

## Terraform Implementation

```hcl
# infrastructure/modules/dynamodb/main.tf
resource "aws_dynamodb_table" "conversations" {
  name           = "ecommerce-agent-conversations"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "session_id"
  range_key      = "timestamp"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = "prod"
    Component   = "agent-memory"
  }
}

# Grant ECS task role access
resource "aws_iam_policy" "dynamodb_access" {
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.conversations.arn
      }
    ]
  })
}
```

## PII Security Considerations

**Conversation history:**
- Contains user messages: may include SSN, DOB, names
- DynamoDB encryption at rest (AWS-managed keys)
- Access restricted to ECS task role only
- TTL ensures automatic deletion after 7 days

**Order database:**
- SSN/DOB hashed before storage (SHA256 + salt)
- Salt stored in AWS Secrets Manager (not in code)
- Full name stored plaintext (needed for verification)
- Consider: encrypt full_name column with KMS

**Analytics:**
- Use identity_hash (not raw PII)
- Session_id is UUID (no PII)
- Safe for long-term retention

## Success Metrics

**Performance:**
- DynamoDB read latency: p99 < 20ms
- Conversation load time: p99 < 100ms (including network)
- Write latency: p99 < 50ms

**Reliability:**
- Zero data loss on container restart
- 99.9% write success rate
- Automatic TTL cleanup (no manual intervention)

**Cost:**
- Actual spend < $5/mo for demo traffic
- Cost per session < $0.003

## Alternative Considered: PostgreSQL for Everything

**Why not use PostgreSQL for conversations too?**

| Factor | DynamoDB | PostgreSQL |
|--------|----------|------------|
| Chat history access pattern | Perfect (key-value) | Overkill (no joins needed) |
| Latency | Single-digit ms | 10-50ms |
| Scaling | Automatic | Manual scaling |
| Cost at low volume | $0.82/mo | $15/mo minimum |
| LangChain support | Native | Custom code |

**Decision:** DynamoDB for conversations (better fit), PostgreSQL for orders (relational model needed).

## Next Steps for Production

1. **Enable Point-in-Time Recovery** on DynamoDB (backups)
2. **Set up CloudWatch alarms** for DynamoDB throttling, high latency
3. **Implement DynamoDB Streams → S3 export** for archives
4. **Add database connection pooling** for PostgreSQL (pgbouncer)
5. **Rotate PII salt** periodically (Secrets Manager versioning)
6. **Test disaster recovery:** restore conversations from S3 backup

## Summary

**Current:** In-memory dict (not production-ready)

**Designed:** DynamoDB for conversations, PostgreSQL for orders, S3 for archives

**Cost:** $3.13/mo (demo) → $18-47/mo (production with RDS)

**Migration:** Backward-compatible, zero downtime

**SA value demonstrated:**
- Chose right database for each access pattern
- Cost-optimized architecture ($3 vs $50)
- Security-conscious design (PII hashing, encryption, TTL)
- Production migration path documented
