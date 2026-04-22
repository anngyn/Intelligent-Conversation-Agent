# Design Decisions & Trade-offs Analysis

**Project:** Agentic Conversational System  
**Role:** Data-AI Solution Architect Intern  
**Purpose:** Document all architectural choices with rationale for interview discussion

---

## Current Repo Decisions

- `DynamoDB` is the implemented store for conversation history because the hot path is `append by session` and `read ordered history by session`, with TTL-based retention.
- `PostgreSQL` is the implemented store for customer and order operations because identity verification and order relationships need indexes, constraints, and transactional updates.
- `FAISS` remains the implemented vector store because the corpus is still small enough that managed vector infrastructure would be cost-heavy over-engineering.
- `OpenSearch` is kept as an optional future path, not a current dependency, because it only becomes defensible when metadata filtering, hybrid search, or larger corpus size justify its cost floor.

---

## 1. Vector Store Selection

### Decision: FAISS (local, in-memory)

| Option | Pros | Cons | Cost | When to Use |
|--------|------|------|------|-------------|
| **FAISS (local)** | • Zero cost<br>• Native LangChain support<br>• Fast (<10ms queries)<br>• No network latency<br>• Simple deployment (baked in image) | • No horizontal scaling<br>• No metadata filtering<br>• Requires re-deploy for index updates<br>• Memory footprint grows with docs | $0/mo | <100 documents, single replica, demo/MVP |
| **FAISS + S3** | • Still cheap ($0.50/mo)<br>• Index updates without redeploy<br>• Separation of data/compute | • Startup time penalty (download index)<br>• Still no horizontal scaling<br>• S3 API latency | $0.50/mo | 10-100 documents, frequent updates |
| **Aurora pgvector** | • SQL metadata filtering<br>• Horizontal read replicas<br>• ACID transactions<br>• Concurrent access<br>• Built-in backup/HA | • More expensive<br>• Requires DB management<br>• Complex queries harder than Python<br>• RDS Serverless min cost | $40-80/mo | 100-1K documents, need SQL filtering, >10 QPS |
| **Pinecone** | • Fully managed<br>• Scales to billions<br>• Multi-region<br>• Built-in reranking | • Vendor lock-in<br>• Most expensive<br>• Network latency<br>• Overkill for small scale | $200/mo+ | >1K documents, global scale, don't want ops |
| **OpenSearch Serverless** | • AWS-native<br>• Full-text + vector hybrid<br>• Kibana dashboards<br>• Complex aggregations | • $700/mo minimum (2 OCU)<br>• Massive overkill for 18 pages<br>• Complex setup | $700/mo | >10K documents, need analytics, Kibana, full-text |

**Rationale:** 18-page PDF = ~100 chunks = 5MB index. FAISS perfect fit. OpenSearch would waste $700/mo. Document migration path: FAISS → FAISS+S3 → pgvector → Pinecone as scale grows.

**Interview Answer:** "I chose FAISS because at this document scale, managed services are massive over-engineering. The entire index fits in memory. OpenSearch Serverless costs $700 per month minimum for a 5-megabyte index. That's a 140x cost multiplier for zero performance benefit. When we hit 100 documents, we migrate to Aurora pgvector for SQL filtering. When we hit 1000 documents, we consider Pinecone if we need global scale."

---

## 2. LLM Model Selection

### Decision: AWS Bedrock Claude 3 Haiku

| Model | Input $/MTok | Output $/MTok | Use Case | Pros | Cons |
|-------|--------------|---------------|----------|------|------|
| **Claude 3 Haiku** | $0.25 | $1.25 | This project | • Cheapest Bedrock chat<br>• Tool calling supported<br>• Fast (1-2s latency)<br>• Sufficient for RAG+tools | • Lower reasoning<br>• 200K context limit |
| **Claude 3.5 Sonnet** | $3.00 | $15.00 | Complex reasoning | • Better tool planning<br>• Stronger reasoning<br>• Same context window | • 12x more expensive<br>• Overkill for demo |
| **Claude 3 Opus** | $15.00 | $75.00 | Mission-critical | • Best reasoning<br>• Highest accuracy | • 60x cost<br>• Not justified |
| **GPT-4o** | $5.00 | $15.00 | OpenAI alternative | • Good reasoning<br>• Vision support | • Not AWS-native<br>• Requires API key mgmt |
| **Llama 3.1 70B** | $0.99 | $0.99 | Cost optimization | • Cheaper than Haiku<br>• Open source | • Lower quality tool calling<br>• Needs testing |

**Cost Analysis (3000 queries/month, 1K input, 100 tokens output each):**
- Haiku: $0.75 + $0.38 = $1.13/mo
- Sonnet: $9.00 + $4.50 = $13.50/mo (12x more)
- Opus: $45.00 + $22.50 = $67.50/mo (60x more)

**Rationale:** Haiku handles tool calling perfectly. This is a structured task (RAG retrieval, order lookup), not creative writing. Sonnet would provide marginal quality gain at 12x cost. We have RAGAS evaluation to verify quality stays above threshold.

**Interview Answer:** "I chose Haiku because it's the cheapest model that supports tool calling on Bedrock. This is a structured retrieval task, not open-ended reasoning. The system prompt constrains behavior tightly. If quality metrics drop below 0.8 faithfulness in RAGAS evaluation, we upgrade to Sonnet. But I'd rather spend the budget on more comprehensive testing than over-provisioning compute."

**When to Upgrade:**
- Haiku → Sonnet: RAGAS faithfulness <0.8, complex multi-hop reasoning required
- Sonnet → Opus: Mission-critical decisions, regulatory approval needed

---

## 3. Embedding Model Selection

### Decision: AWS Bedrock Titan Embed Text v2

| Model | Dimensions | Cost $/MTok | Max Tokens | Pros | Cons |
|-------|-----------|-------------|------------|------|------|
| **Titan Embed v2** | 1024 | $0.02 | 8K | • AWS-native (no keys)<br>• Cheap<br>• Good quality<br>• Long context | • Not SOTA |
| **text-embedding-3-large** | 3072 | $0.13 | 8K | • Better retrieval<br>• Higher dimensions | • 6.5x cost<br>• OpenAI API key<br>• Not AWS-native |
| **Cohere Embed v3** | 1024 | $0.10 | 512 | • Good quality | • Shorter context<br>• 5x cost |

**Rationale:** Titan sufficient for 18-page PDF. Chunks are <1000 chars. Retrieval quality tested with golden dataset (recall@4 >0.7). No need for expensive embeddings when bottleneck is document quality, not embedding model.

**Interview Answer:** "Titan Embed v2 is the cost-optimized choice for AWS-native embeddings. At 18 pages, retrieval quality depends more on chunking strategy than embedding model. We're not hitting the limits of 1024 dimensions. If RAGAS metrics show poor retrieval, I'd first optimize chunking (semantic splitting, better metadata), then consider upgrading embeddings. Embedding model is usually not the bottleneck."

---

## 4. Compute Platform Selection

### Decision: ECS Fargate (0.25 vCPU, 0.5 GB)

| Platform | Cold Start | Cost (8h/day) | Scaling | Complexity | Use Case |
|----------|-----------|---------------|---------|------------|----------|
| **ECS Fargate** | 0s (warm) | $2/mo | Manual/auto | Medium | This project |
| **Lambda** | 5-10s | $1/mo | Auto | Low | Event-driven, <15min runtime |
| **EC2 t3.micro** | N/A | $6/mo | Manual | High | Long-running, need OS control |
| **App Runner** | 0s | $5/mo | Auto | Very low | Simple web apps, no VPC control |

**Pros/Cons:**

**ECS Fargate:**
- ✅ No cold start (keep 1 task warm)
- ✅ Streaming works natively
- ✅ Can run indefinitely
- ✅ VPC control for private subnets
- ❌ More Terraform complexity than Lambda
- ❌ Pay for idle time (can scale to 0)

**Lambda:**
- ✅ True pay-per-invoke
- ✅ Simple deployment
- ❌ 5-10s cold start (Python + FAISS + LangChain)
- ❌ 15min timeout (blocks long conversations)
- ❌ Streaming requires response streaming (complex)
- ❌ 512MB-10GB memory (FAISS index + runtime)

**Rationale:** Lambda cold starts kill UX. User sends message → waits 10s → first token appears. Unacceptable. Fargate keeps 1 task warm = instant response. Streaming is native (SSE over HTTP). Cost difference minimal at demo scale ($2 vs $1).

**Interview Answer:** "Lambda would save $1 per month but creates a 5-10 second cold start penalty. That's a 5-10 second wait before the first token streams to the user. Unacceptable UX for a chat interface. Fargate costs $2 per month to keep one task warm and gives us instant response times. The marginal cost is worth the 10x better user experience. If this were batch processing or event-driven, Lambda would be the right choice."

**Scaling Thresholds:**
- 1-10 concurrent users: 1 Fargate task
- 10-50 users: 2-3 tasks (auto-scaling on CPU)
- 50-100 users: 5-10 tasks + consider caching
- 100+ users: Re-architect with async processing (SQS queue)

---

## 5. Session Memory Storage

### Decision: DynamoDB for conversation history

| Option | Latency | Cost | Persistence | Scaling | Use Case |
|--------|---------|------|-------------|---------|----------|
| **DynamoDB** | 5-10ms | Very low, pay-per-request | Persistent + TTL | Automatic | Current implementation |
| **In-memory (dict)** | <1ms | $0 | Lost on restart | Single instance | Local fallback only |
| **Redis (ElastiCache)** | 1-2ms | Higher fixed cost | Persistent (optional) | High | High-throughput, <1s latency SLA |
| **RDS PostgreSQL** | 10-20ms | Higher fixed cost | Persistent | Moderate | Complex queries, analytics |

**Current implementation:**
- Primary key: `session_id`
- Sort key: `message_key = {timestamp_ms}#{uuid}`
- Attributes: `created_at`, `message_type`, serialized `message`, `ttl`
- TTL auto-expires old sessions
- In-memory history remains only as a fallback when no table is configured

**Rationale:** Conversation history is append-heavy and almost always read back by `session_id` in chronological order. DynamoDB fits that access pattern better than PostgreSQL because it avoids joins, scales without capacity planning, and keeps cost proportional to actual chat volume. The sort key embeds time ordering, so no secondary index is needed for the hot path.

**Interview Answer:** "I moved conversation memory to DynamoDB because the access pattern is narrow and predictable: append message, load ordered history for one session, and expire it automatically after retention. That is a DynamoDB problem, not a relational problem. I kept an in-memory fallback for local development, but production memory is now durable, horizontally scalable, and TTL-managed."

---

## 6. Frontend Framework Selection

### Decision: Streamlit

| Framework | LOC | Development Time | Streaming Support | Deployment | Use Case |
|-----------|-----|------------------|-------------------|------------|----------|
| **Streamlit** | ~200 | 2 hours | Native (async) | Single file | This project |
| **React + Vite** | ~1000 | 2 days | Manual (EventSource) | Webpack, routing | Production web app |
| **Next.js** | ~800 | 1.5 days | Built-in (Server Actions) | Complex | Full-stack app |
| **Gradio** | ~150 | 1 hour | Native | Single file | ML demos |

**Streamlit Pros:**
- ✅ Chat UI in <200 lines
- ✅ Native async streaming (httpx + st.write_stream)
- ✅ Session state built-in
- ✅ No frontend build step
- ✅ Production-quality UI

**Streamlit Cons:**
- ❌ Less customizable than React
- ❌ Websocket overhead (bigger than REST)
- ❌ Not ideal for complex multi-page apps

**Rationale:** Assignment evaluates backend architecture, not frontend skills. Streamlit delivers production-quality chat UI in 2 hours. React would take 2 days for same functionality. Time better spent on agent quality, testing, documentation.

**Interview Answer:** "I chose Streamlit because this assignment evaluates solution architecture, not frontend engineering. Streamlit delivers a production-quality chat interface in 200 lines of Python. The alternative — React with SSE handling, state management, and UI components — would be 1000 lines and two days of work. That's two days not spent on RAG quality, testing, or infrastructure. Streamlit's streaming support is native. For a customer-facing production app, we'd build React. For internal tools and demos, Streamlit is the right tool."

---

## 7. Network Architecture

### Decision: VPC with Private Subnets + (NAT Gateway OR VPC Endpoints)

| Option | Security | Cost | Latency | Complexity | Use Case |
|--------|----------|------|---------|------------|----------|
| **Public Subnets** | ❌ Low | $65/mo | Lowest | Low | Dev/test only |
| **Private + NAT** | ✅ High | $112/mo | Medium | Medium | General production |
| **Private + VPC Endpoints** | ✅✅ Highest | $93/mo | Lowest | High | Production (recommended) |

### Option A: Public Subnets (NOT RECOMMENDED)
```
ECS Task (public IP) → Internet Gateway → AWS Services
```
**Cost:** $65/mo  
**Security:** ❌ Tasks have public IPs (attack surface)  
**Use case:** Development only

### Option B: Private Subnets + NAT Gateway
```
ECS Task (private) → NAT Gateway → Internet Gateway → AWS
```
**Cost:** $112/mo ($47 NAT + $65 services)  
**Security:** ✅ Tasks in private subnet  
**Pros:**
- Simple (1 NAT resource)
- Can reach any internet destination
- Well-documented pattern

**Cons:**
- Expensive ($32 fixed + $0.045/GB)
- Traffic leaves AWS network
- Single point of failure
- Higher latency (extra hop)

### Option C: Private Subnets + VPC Endpoints (RECOMMENDED)
```
ECS Task (private) → VPC Endpoint (PrivateLink) → AWS Service
```
**Cost:** $93/mo ($28 endpoints + $65 services)  
**Security:** ✅✅ Traffic never leaves AWS network  
**Required endpoints:**
- `bedrock-runtime` (Interface, $7/mo)
- `ecr.api` + `ecr.dkr` (Interface, $14/mo)
- `logs` (Interface, $7/mo)
- `s3` (Gateway, FREE)
- `dynamodb` (Gateway, FREE)

**Pros:**
- ✅ Cheaper than NAT ($28 vs $47, saves $20/mo)
- ✅ Lower latency (no NAT hop, stay in AWS backbone)
- ✅ More secure (traffic never exits AWS network)
- ✅ No data transfer charges
- ✅ No single point of failure (multi-AZ by default)

**Cons:**
- ❌ More Terraform resources (5-6 endpoint blocks)
- ❌ Requires `enableDnsSupport=true` in VPC
- ❌ Can't reach arbitrary internet (no pip install from PyPI at runtime)

**Hybrid Option:** VPC endpoints for AWS services + NAT (scaled to 0 by default) for rare external needs

**Rationale:** VPC endpoints cost less, perform better, and are more secure than NAT. Only downside is Terraform complexity (5 extra resources vs 1). For production, always use VPC endpoints.

**Interview Answer:** "I recommend VPC endpoints over NAT Gateway for three reasons: cost, performance, and security. VPC endpoints cost $28 per month versus $47 for NAT — that's a $20 monthly saving. More importantly, traffic stays on the AWS backbone instead of routing through the internet, giving us lower latency and eliminating external attack surface. The trade-off is Terraform complexity: we need to define five endpoint resources instead of one NAT Gateway. But that's a one-time engineering cost for ongoing operational benefits."

**Decision Matrix:**
- **Dev/prototype:** Public subnets (simplicity)
- **Demo/pilot:** NAT Gateway (balance of simplicity and security)
- **Production:** VPC Endpoints (cost + security + performance)

---

## 8. CI/CD Pipeline Design

### Decision: GitHub Actions with OIDC (no static credentials)

| Platform | Cost | Integration | Terraform | AWS Auth | Use Case |
|----------|------|-------------|-----------|----------|----------|
| **GitHub Actions** | Free (2000 min/mo) | Native | ✅ | OIDC | This project |
| **GitLab CI** | Free (400 min/mo) | Native | ✅ | Static IAM | GitLab users |
| **AWS CodePipeline** | $1/pipeline | AWS-native | ✅ | IAM role | AWS-centric orgs |
| **CircleCI** | $30/mo | External | ✅ | Static IAM | Enterprise |

**GitHub Actions Advantages:**
1. **OIDC authentication** (no long-lived AWS credentials)
2. **Free tier** sufficient (2000 minutes/month)
3. **Matrix builds** (test Python 3.11, 3.12, 3.13 in parallel)
4. **Native GitHub integration** (PR checks, branch protection)

**Pipeline:**
```yaml
CI (on PR):
1. Lint (ruff)
2. Type check (mypy)
3. Unit tests (pytest)
4. Docker build (test)
5. Terraform validate + plan

CD (on push to main):
1. Build images (backend, frontend)
2. Push to ECR
3. Terraform apply (with approval)
4. ECS force deployment
5. Health check
```

**Rationale:** OIDC eliminates need for long-lived IAM access keys in GitHub Secrets. Temporary credentials issued per workflow run. More secure than static credentials.

**Interview Answer:** "GitHub Actions with OIDC is the modern approach to CI/CD on AWS. Instead of storing static IAM credentials in GitHub Secrets — which can leak or be over-permissioned — we use OpenID Connect to issue temporary credentials per workflow run. The IAM role trusts GitHub's OIDC provider, verifies the repository and branch, and issues 1-hour credentials. When the workflow finishes, credentials expire. This eliminates the risk of credential leakage."

---

## 9. Chunking Strategy

### Decision: RecursiveCharacterTextSplitter (1000 chars, 200 overlap)

| Strategy | Chunk Size | Overlap | Pros | Cons | Use Case |
|----------|-----------|---------|------|------|----------|
| **Fixed (char)** | 1000 | 200 | Simple | Splits mid-sentence | Don't use |
| **Recursive (char)** | 1000 | 200 | Respects paragraphs | May split mid-concept | General purpose (chosen) |
| **Sentence-based** | ~5 sentences | 1 sentence | Clean boundaries | Variable size | Short docs |
| **Semantic (LLM)** | Variable | Smart | Concept-aware | Expensive, slow | Critical docs |
| **Markdown-aware** | By header | None | Structure-preserving | Only for markdown | Docs with headers |

**Current Approach:**
```python
RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]  # Prefer paragraph breaks
)
```

**Why 1000 chars:**
- ~250 tokens (4:1 char:token ratio)
- Fits in Bedrock context with room for 4 chunks + query + prompt
- Small enough for specific answers, large enough for context

**Why 200 overlap:**
- Prevents concept split across boundaries
- 20% overlap = queries near boundaries still retrieve context

**Alternative (Semantic Chunking):**
```python
SemanticChunker(
    embeddings=BedrockEmbeddings(),
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=90
)
```
- Uses embeddings to detect topic shifts
- More expensive (2x embedding calls)
- Better for complex docs

**Rationale:** Recursive character splitting with 1000/200 is proven pattern. Semantic chunking would add latency and cost without clear benefit for 18-page PDF. If RAGAS recall <0.7, try semantic chunking.

**Interview Answer:** "1000 characters with 200-character overlap is the industry-standard starting point. It maps to about 250 tokens, which fits comfortably in context windows. The 20% overlap prevents information loss when concepts span chunk boundaries. The recursive approach respects paragraph breaks instead of splitting mid-sentence. If retrieval quality metrics drop below 0.7 recall, we'd experiment with semantic chunking using LLM-based boundary detection. But for this document type — structured financial filing — character-based chunking with good separators works well."

---

## 10. Infrastructure as Code

### Decision: Terraform (HCL)

| Tool | Language | State | Drift | AWS Support | Use Case |
|------|----------|-------|-------|-------------|----------|
| **Terraform** | HCL | Remote (S3) | Manual | ✅ | Multi-cloud, this project |
| **CloudFormation** | YAML/JSON | AWS-managed | Auto | ✅✅ | AWS-only, native |
| **CDK** | TypeScript/Python | CloudFormation | Auto | ✅✅ | Devs want real code |
| **Pulumi** | Python/TS/Go | Remote | Manual | ✅ | Dev-first teams |

**Terraform Advantages:**
- ✅ Industry standard (more job-relevant than CFN)
- ✅ Module ecosystem (reusable components)
- ✅ Multi-cloud (can add GCP later)
- ✅ Better IDE support than CFN
- ✅ Expressive (for_each, count, dynamic blocks)

**CloudFormation Advantages:**
- ✅ Native AWS (no third-party tools)
- ✅ Drift detection built-in
- ✅ StackSets for multi-account
- ✅ No state file to manage

**CDK Advantages:**
- ✅ Real programming language (Python/TS)
- ✅ Type checking
- ✅ Loops, conditionals, abstractions
- ✅ Compiles to CloudFormation

**Rationale:** Terraform is standard for SA role. Module structure shows architectural thinking. CloudFormation is verbose (3x lines for same resources). CDK adds complexity (requires npm, build step).

**Interview Answer:** "Terraform is the industry standard for infrastructure as code. It's more marketable than CloudFormation, supports multiple clouds, and has a rich module ecosystem. The state management is handled by S3 backend with DynamoDB locking. For an AWS-only shop with strong CloudFormation expertise, I'd use CFN. For a greenfield project evaluating multi-cloud, Terraform gives us flexibility. The module structure — splitting networking, compute, and storage into separate modules — demonstrates infrastructure design thinking, not just 'everything in one file' scripting."

---

## 11. Error Handling & Resilience

### Strategies Implemented

**1. Bedrock Rate Limiting**
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(ClientError)
)
```
- 3 retries with exponential backoff (2s, 4s, 8s)
- Only retry transient errors (429, 5xx)
- Don't retry 4xx client errors

**2. DynamoDB Fallback (Optional Enhancement)**
```python
@circuit(failure_threshold=3, recovery_timeout=60)
def get_dynamodb_history(session_id):
    return DynamoDBChatMessageHistory(...)

def get_session_history(session_id):
    try:
        return get_dynamodb_history(session_id)
    except Exception:
        # Fall back to in-memory
        return _in_memory_store[session_id]
```
- Circuit breaker pattern
- Graceful degradation (lose history persistence, but don't block users)

**3. SSE Keepalive**
```python
last_event_time = time.time()

if time.time() - last_event_time > 15:
    yield ": keepalive\n\n"  # Prevent ALB timeout
```
- ALB/proxy timeout often 30-60s
- Keepalive every 15s keeps connection alive during slow LLM responses

**4. Tool Validation**
```python
def check_order_status(name: str, ssn: str, dob: str):
    if not name or len(ssn) != 4 or not valid_date(dob):
        return {"error": "Invalid input"}
```
- Defense-in-depth (prompt + tool validation)
- Return errors, don't raise exceptions (keeps conversation flowing)

**When to Add More:**
- **Quotas:** If hitting Bedrock throttles, add Bedrock Provisioned Throughput
- **Timeouts:** If queries >30s, add async processing (SQS queue)
- **Monitoring:** If production incidents, add X-Ray tracing + CloudWatch alarms

---

## 12. Testing Strategy

### Pyramid

```
       ╱╲
      ╱  ╲  E2E Tests (2)
     ╱────╲  - Full API flow
    ╱      ╲  - Bedrock calls (expensive)
   ╱────────╲
  ╱          ╲ Integration Tests (8)
 ╱────────────╲ - Agent + tools
╱              ╲ - Memory
────────────────
Unit Tests (20+)
- RAG chunking
- Tool validation
- Mock order lookup
```

**Why This Balance:**
- **Unit tests:** Fast (<1s), no external deps, run in CI every commit
- **Integration tests:** Moderate (10-30s), call Bedrock, run before deploy
- **E2E tests:** Slow (60s+), full stack, run manually before release

**Cost Consideration:**
- Bedrock charges per token
- Running full integration suite costs ~$0.10
- Limit to 10-20 test cases, not 1000

**Interview Answer:** "Testing strategy balances coverage with cost. Unit tests are free and fast — we run them on every commit. Integration tests call Bedrock and cost about 10 cents per full suite run, so we limit those to pre-deployment checks. End-to-end tests exercise the full HTTP stack and are primarily for debugging SSE streaming issues. The testing pyramid prevents runaway AWS costs while maintaining confidence in core functionality."

---

## Summary: Key Decision Framework

| Decision | Primary Driver | Trade-off Accepted |
|----------|---------------|-------------------|
| FAISS | Cost ($0 vs $700) | No horizontal scaling (yet) |
| Haiku | Cost ($1 vs $13) | Lower reasoning quality |
| Titan Embed | AWS-native | Not SOTA embeddings |
| Fargate | UX (0s cold start) | $1/mo more than Lambda |
| In-memory | Simplicity | No persistence (demo scope) |
| Streamlit | Development speed | Less customizable than React |
| VPC Endpoints | Cost + Security | Terraform complexity |
| GitHub Actions | OIDC security | Vendor lock-in to GitHub |
| Terraform | Industry standard | More verbose than CDK |

**Overarching Principle:** Optimize for cost and simplicity at current scale, with documented migration paths for future scale. Don't over-engineer for hypothetical 1000x growth.

**Interview Positioning:** Show decision-making process, understand trade-offs, know when to scale up. "Right tool for right scale" beats "enterprise pattern for 18-page PDF."
