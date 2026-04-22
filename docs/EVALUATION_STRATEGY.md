# Level 300: Evaluation & Quality Assurance Strategy

## Current State (Level 100+200)

**Testing approach:**
- Manual spot checks: "Does this answer look right?"
- Basic unit tests: `test_mock_order.py`, `test_rag.py`
- No systematic quality measurement
- No regression detection
- No production monitoring

**What we can't answer:**
- Is RAG accuracy improving or degrading over time?
- Which queries does the agent handle poorly?
- Did the new prompt change break anything?
- What's the baseline quality for comparison?
- How do users rate the responses?

**Interview weakness:** "I built it and it works" vs "I measured quality and proved it works."

## Design Goals

1. **Regression prevention:** Detect when code changes break existing behavior
2. **Quality measurement:** Quantify RAG accuracy, tool success rate, user satisfaction
3. **Continuous improvement:** Identify weak spots, measure fix impact
4. **A/B testing framework:** Compare variants (prompts, models, techniques)
5. **Production monitoring:** Real-time quality tracking, alert on degradation

## Evaluation Framework Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Offline Evaluation (Pre-deployment)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Golden Dataset  │────────▶│  Test Runner     │             │
│  │  (30 test cases) │         │  (pytest)        │             │
│  └──────────────────┘         └────────┬─────────┘             │
│                                         │                        │
│                                         ▼                        │
│                              ┌──────────────────┐               │
│                              │  Metrics:        │               │
│                              │  • Accuracy      │               │
│                              │  • Coverage      │               │
│                              │  • Latency       │               │
│                              └──────────────────┘               │
│                                         │                        │
│                                         ▼                        │
│                              [Pass/Fail Gate for CI/CD]         │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Online Evaluation (Production)                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Real Traffic    │────────▶│  Sample 5%       │             │
│  │  (30K req/day)   │         │  for eval        │             │
│  └──────────────────┘         └────────┬─────────┘             │
│                                         │                        │
│                                         ▼                        │
│                              ┌──────────────────┐               │
│                              │  Automated:      │               │
│                              │  • Citation check│               │
│                              │  • Tool success  │               │
│                              │  • Latency       │               │
│                              └──────────────────┘               │
│                                         │                        │
│                                         ▼                        │
│                              ┌──────────────────┐               │
│                              │  Human Label:    │               │
│                              │  • Relevance     │               │
│                              │  • Helpfulness   │               │
│                              │  • Hallucination │               │
│                              └──────────────────┘               │
│                                         │                        │
│                                         ▼                        │
│                              [Quality Dashboard + Alarms]       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  A/B Testing (Optimization)                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  Variant A       │         │  Variant B       │             │
│  │  (Control)       │         │  (Treatment)     │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
│           │         Traffic Split      │                        │
│           └──────────────┬─────────────┘                        │
│                          │                                      │
│                          ▼                                      │
│              ┌──────────────────────┐                          │
│              │  Compare Metrics:    │                          │
│              │  • Accuracy          │                          │
│              │  • Latency           │                          │
│              │  • Cost              │                          │
│              │  • User satisfaction │                          │
│              └──────────────────────┘                          │
│                          │                                      │
│                          ▼                                      │
│              [Statistical Significance Test]                   │
│                          │                                      │
│                          ▼                                      │
│              [Ship Winner to 100%]                             │
└─────────────────────────────────────────────────────────────────┘
```

## Golden Dataset Design

### Test Case Structure

```json
{
  "id": "rag-revenue-001",
  "category": "rag_qa",
  "query": "What was Amazon's total net sales in 2023?",
  "expected_answer_contains": ["574.8", "billion", "2023"],
  "expected_citations": ["Page 3"],
  "expected_tool": "search_knowledge_base",
  "difficulty": "easy",
  "notes": "Simple fact lookup, should always work"
}
```

### Test Case Categories

**1. RAG Q&A (15 cases)**

| Difficulty | Count | Examples |
|------------|-------|----------|
| Easy | 5 | Simple fact lookup ("What was 2023 revenue?") |
| Medium | 5 | Requires reasoning ("How did margins change?") |
| Hard | 5 | Multi-hop ("Compare AWS vs retail growth and explain") |

**2. Order Status (10 cases)**

| Flow Type | Count | Examples |
|-----------|-------|----------|
| Happy path | 3 | User provides all info, order found |
| Missing info | 3 | Agent collects name → SSN → DOB step by step |
| Invalid input | 2 | Wrong SSN format, non-existent order |
| Edge cases | 2 | Multiple orders, recent order |

**3. Conversational (5 cases)**

| Type | Count | Examples |
|------|-------|----------|
| Multi-turn | 3 | Follow-up questions without context repetition |
| Context switch | 2 | Switch from RAG to order status mid-conversation |

### Golden Dataset Implementation

```python
# backend/tests/golden_dataset.json
[
  {
    "id": "rag-revenue-001",
    "category": "rag_qa",
    "query": "What was Amazon's total net sales in 2023?",
    "expected_answer_contains": ["574.8", "billion"],
    "expected_citations": ["Page 3"],
    "must_not_contain": ["I don't have", "I'm not sure"],
    "expected_tool": "search_knowledge_base",
    "max_latency_ms": 3000
  },
  {
    "id": "rag-comparison-001",
    "category": "rag_qa",
    "query": "How did international sales compare to North America in 2023?",
    "expected_answer_contains": ["international", "North America", "segment"],
    "expected_citations": ["Page"],
    "expected_tool": "search_knowledge_base",
    "max_latency_ms": 3000
  },
  {
    "id": "order-happy-001",
    "category": "order_status",
    "conversation": [
      {
        "user": "Track my order",
        "expected_response_contains": ["full name", "verification"],
        "must_not_contain": ["order", "shipped"]
      },
      {
        "user": "John Smith",
        "expected_response_contains": ["last 4 digits", "SSN"],
        "must_not_contain": ["order"]
      },
      {
        "user": "1234",
        "expected_response_contains": ["date of birth", "YYYY-MM-DD"],
        "must_not_contain": ["order"]
      },
      {
        "user": "1990-01-15",
        "expected_response_contains": ["order", "ORD-2024-001", "shipped", "tracking"],
        "expected_tool": "check_order_status"
      }
    ],
    "max_latency_ms": 5000
  },
  {
    "id": "order-invalid-001",
    "category": "order_status",
    "conversation": [
      {
        "user": "Check my order for Jane Doe, SSN 999, DOB 1985-06-20",
        "expected_response_contains": ["SSN must be exactly 4 digits", "error"],
        "must_not_contain": ["order", "shipped"]
      }
    ]
  },
  {
    "id": "multi-turn-001",
    "category": "conversational",
    "conversation": [
      {
        "user": "What was Amazon's 2023 revenue?",
        "expected_answer_contains": ["574.8", "billion"]
      },
      {
        "user": "How does that compare to 2022?",
        "expected_answer_contains": ["2022", "increase", "growth"],
        "notes": "Agent should understand 'that' refers to revenue"
      }
    ]
  }
]
```

### Test Runner Implementation

```python
# backend/tests/test_golden.py
import json
import pytest
from app.agent.graph import create_agent
from app.rag.retriever import FormattedRetriever
from app.rag.store import load_vector_store

@pytest.fixture
def agent():
    """Load agent for testing."""
    vectorstore = load_vector_store("dataset/processed/faiss_index")
    retriever = FormattedRetriever(vectorstore, k=4)
    return create_agent(retriever)

@pytest.fixture
def golden_dataset():
    """Load golden dataset."""
    with open("tests/golden_dataset.json") as f:
        return json.load(f)

def test_golden_dataset(agent, golden_dataset):
    """Run all golden test cases."""
    results = {
        "total": len(golden_dataset),
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    for case in golden_dataset:
        try:
            if case["category"] in ["rag_qa", "order_status"]:
                result = run_single_turn_test(agent, case)
            elif case["category"] == "conversational":
                result = run_multi_turn_test(agent, case)
            
            if result["passed"]:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "id": case["id"],
                    "reason": result["reason"]
                })
        
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "id": case["id"],
                "reason": f"Exception: {str(e)}"
            })
    
    # Assert at least 90% pass rate
    pass_rate = results["passed"] / results["total"]
    assert pass_rate >= 0.9, f"Golden dataset pass rate {pass_rate:.1%} < 90%. Failures: {results['errors']}"

def run_single_turn_test(agent, case):
    """Run single-turn test case."""
    import time
    
    start = time.time()
    response = agent.invoke({"input": case["query"]})
    latency_ms = (time.time() - start) * 1000
    
    output = response["output"]
    
    # Check expected content
    for keyword in case.get("expected_answer_contains", []):
        if keyword.lower() not in output.lower():
            return {
                "passed": False,
                "reason": f"Missing expected keyword: '{keyword}'"
            }
    
    # Check must-not-contain
    for keyword in case.get("must_not_contain", []):
        if keyword.lower() in output.lower():
            return {
                "passed": False,
                "reason": f"Contains forbidden keyword: '{keyword}'"
            }
    
    # Check citations
    for citation in case.get("expected_citations", []):
        if citation not in output:
            return {
                "passed": False,
                "reason": f"Missing expected citation: '{citation}'"
            }
    
    # Check latency
    if latency_ms > case.get("max_latency_ms", 5000):
        return {
            "passed": False,
            "reason": f"Latency {latency_ms}ms > {case['max_latency_ms']}ms"
        }
    
    return {"passed": True}

def run_multi_turn_test(agent, case):
    """Run multi-turn conversation test."""
    from app.agent.memory import get_session_history
    
    session_id = f"test-{case['id']}"
    
    for turn in case["conversation"]:
        response = agent.invoke(
            {"input": turn["user"]},
            config={"configurable": {"session_id": session_id}}
        )
        
        output = response["output"]
        
        # Check expected content
        for keyword in turn.get("expected_response_contains", []):
            if keyword.lower() not in output.lower():
                return {
                    "passed": False,
                    "reason": f"Turn '{turn['user'][:50]}': Missing '{keyword}'"
                }
        
        # Check must-not-contain
        for keyword in turn.get("must_not_contain", []):
            if keyword.lower() in output.lower():
                return {
                    "passed": False,
                    "reason": f"Turn '{turn['user'][:50]}': Contains forbidden '{keyword}'"
                }
    
    return {"passed": True}
```

### CI/CD Integration

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[dev]"
      
      - name: Build FAISS index
        run: |
          cd backend
          python scripts/ingest_pdf.py
      
      - name: Run golden dataset tests
        env:
          AWS_REGION: us-east-1
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          cd backend
          pytest tests/test_golden.py -v
      
      - name: Fail if pass rate < 90%
        run: |
          # pytest will fail if assertion fails
          echo "Golden dataset tests passed!"
```

## Production Quality Monitoring

### Automated Metrics Collection

```python
# backend/app/observability/quality_metrics.py
from aws_embedded_metrics import metric_scope

@metric_scope
def emit_quality_metrics(
    metrics,
    session_id: str,
    query: str,
    response: str,
    tools_used: list[str],
    latency_ms: float,
    citations_present: bool
):
    """Emit quality metrics for production monitoring."""
    
    metrics.set_namespace("AgentQuality")
    
    # Citation compliance (RAG queries should have citations)
    if "search_knowledge_base" in tools_used:
        has_citation = "[Source" in response and "Page" in response
        metrics.put_metric("RAGCitationPresent", 1 if has_citation else 0, "Count")
    
    # Tool success (did tool call succeed?)
    tool_success = "error" not in response.lower() and "apologize" not in response.lower()
    metrics.put_metric("ToolCallSuccess", 1 if tool_success else 0, "Count")
    
    # Response length (very short may indicate failure)
    metrics.put_metric("ResponseLength", len(response), "Count")
    
    # Latency
    metrics.put_metric("ResponseLatency", latency_ms, "Milliseconds")
    
    # Properties for filtering
    metrics.set_property("SessionId", session_id)
    metrics.set_property("QueryLength", len(query))
    metrics.set_property("ToolsUsed", ",".join(tools_used))

# Usage in routes.py
@router.post("/chat")
async def chat(request: ChatRequest):
    start = time.time()
    
    # ... agent invocation ...
    
    emit_quality_metrics(
        session_id=request.session_id,
        query=request.message,
        response=agent_response,
        tools_used=tools_used,
        latency_ms=(time.time() - start) * 1000,
        citations_present=has_citations
    )
```

### Quality Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent Quality Dashboard (Last 24h)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [RAG Citation Compliance]    [Tool Call Success Rate]         │
│   92% have citations          96% successful                    │
│   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░          ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░              │
│   Target: >90%                 Target: >95%                     │
│                                                                  │
├──────────────────────────┬──────────────────────────────────────┤
│  [Avg Response Latency]  │  [Low Quality Response Rate]        │
│   P50: 1.8s  P99: 3.2s   │   4% (responses <50 chars)          │
│   ▁▂▃▄▅▆▅▄▃▂▁            │   Target: <5%                       │
│                          │                                      │
├──────────────────────────┴──────────────────────────────────────┤
│  [Quality Trend (7 days)]                                       │
│   Citation Rate:  89% → 92% ✅                                  │
│   Tool Success:   94% → 96% ✅                                  │
│   Avg Latency:    2.1s → 1.8s ✅                                │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Recent Low-Quality Samples] (for manual review)               │
│   • Session abc-123: No citation, query "What was revenue?"     │
│   • Session def-456: Tool failed, "I apologize, error occurred" │
│   • Session ghi-789: Very short response (12 chars)             │
└─────────────────────────────────────────────────────────────────┘
```

### Quality Alarms

```hcl
# infrastructure/modules/monitoring/quality_alarms.tf
resource "aws_cloudwatch_metric_alarm" "low_citation_rate" {
  alarm_name          = "agent-low-citation-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RAGCitationPresent"
  namespace           = "AgentQuality"
  period              = 3600  # 1 hour
  statistic           = "Average"
  threshold           = 0.85  # 85%
  alarm_description   = "RAG responses lack citations"
  alarm_actions       = [aws_sns_topic.quality_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "low_tool_success" {
  alarm_name          = "agent-low-tool-success-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ToolCallSuccess"
  namespace           = "AgentQuality"
  period              = 3600
  statistic           = "Average"
  threshold           = 0.90  # 90%
  alarm_description   = "Tool call success rate dropped"
  alarm_actions       = [aws_sns_topic.quality_alerts.arn]
}
```

## Human Labeling Loop

### Weekly Sampling Process

```python
# backend/scripts/sample_for_labeling.py
import random
from datetime import datetime, timedelta

def sample_conversations_for_labeling(n=50):
    """
    Sample conversations for human quality assessment.
    
    Stratified sampling:
    - 20 from RAG Q&A
    - 20 from order status
    - 10 from edge cases (errors, very long/short responses)
    """
    
    # Query CloudWatch Logs or analytics DB
    yesterday = datetime.now() - timedelta(days=1)
    
    # Get RAG conversations
    rag_conversations = query_logs(
        event_type="agent_response",
        tool_used="search_knowledge_base",
        date=yesterday,
        limit=100
    )
    rag_sample = random.sample(rag_conversations, 20)
    
    # Get order status conversations
    order_conversations = query_logs(
        event_type="agent_response",
        tool_used="check_order_status",
        date=yesterday,
        limit=100
    )
    order_sample = random.sample(order_conversations, 20)
    
    # Get edge cases
    edge_cases = query_logs(
        event_type="agent_response",
        filters=["error OR response_length < 50 OR latency > 5000"],
        date=yesterday,
        limit=10
    )
    
    # Export to CSV for labeling
    export_to_csv(rag_sample + order_sample + edge_cases, "labeling_batch.csv")
```

### Labeling Interface (Simple CSV)

```csv
session_id,query,response,label_relevance,label_hallucination,label_helpfulness,notes
abc-123,"What was revenue?","According to our 10-K (Page 3)...",5,no,5,""
def-456,"Track order","I need your full name for verification",5,no,5,""
ghi-789,"What's the weather?","I can only help with company info...",4,no,3,"Correct rejection"
```

**Labeling rubric:**
- **Relevance** (1-5): Does response address the query?
- **Hallucination** (yes/no): Any made-up facts not in context?
- **Helpfulness** (1-5): Would this satisfy the user?

### Feedback Integration

```python
# backend/app/api/routes.py
@router.post("/feedback")
async def submit_feedback(
    session_id: str,
    message_id: str,
    thumbs_up: bool,
    feedback_text: Optional[str] = None
):
    """Collect user feedback on responses."""
    
    # Store in analytics DB
    store_feedback({
        "session_id": session_id,
        "message_id": message_id,
        "satisfaction": 1 if thumbs_up else 0,
        "feedback_text": feedback_text,
        "timestamp": datetime.utcnow()
    })
    
    # Emit metric
    emit_metric("UserSatisfaction", 1 if thumbs_up else 0, "Count")
    
    return {"status": "recorded"}
```

## A/B Testing Framework

### Variant Assignment

```python
# backend/app/experiments/ab_test.py
import hashlib
from enum import Enum

class Variant(str, Enum):
    CONTROL = "control"           # Haiku, basic prompt
    TREATMENT_A = "sonnet"         # Sonnet model
    TREATMENT_B = "reranking"      # Haiku + reranking

def assign_variant(session_id: str) -> Variant:
    """
    Assign user to variant based on session_id hash.
    
    Ensures consistent assignment: same session always gets same variant.
    """
    hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
    
    # 50% control, 25% treatment A, 25% treatment B
    remainder = hash_val % 100
    
    if remainder < 50:
        return Variant.CONTROL
    elif remainder < 75:
        return Variant.TREATMENT_A
    else:
        return Variant.TREATMENT_B

# Usage in routes.py
@router.post("/chat")
async def chat(request: ChatRequest):
    variant = assign_variant(request.session_id)
    
    # Configure agent based on variant
    if variant == Variant.CONTROL:
        agent = create_agent(retriever_basic, model="haiku")
    elif variant == Variant.TREATMENT_A:
        agent = create_agent(retriever_basic, model="sonnet")
    elif variant == Variant.TREATMENT_B:
        agent = create_agent(retriever_rerank, model="haiku")
    
    # Log variant
    emit_metric("ABTestVariant", 1, dimensions={"Variant": variant})
    
    # ... rest of handler ...
```

### Metrics Comparison

```python
# backend/scripts/analyze_ab_test.py
def analyze_ab_test(start_date, end_date, min_samples=500):
    """
    Compare variants on key metrics.
    
    Returns statistical significance of differences.
    """
    
    variants = [Variant.CONTROL, Variant.TREATMENT_A, Variant.TREATMENT_B]
    results = {}
    
    for variant in variants:
        # Query metrics from CloudWatch or analytics DB
        data = query_variant_metrics(variant, start_date, end_date)
        
        results[variant] = {
            "sample_size": len(data),
            "avg_latency_ms": mean(data["latency"]),
            "citation_rate": mean(data["has_citation"]),
            "tool_success_rate": mean(data["tool_success"]),
            "user_satisfaction": mean(data["thumbs_up"]),
            "cost_per_query": mean(data["cost"])
        }
    
    # Statistical significance test (t-test)
    for metric in ["avg_latency_ms", "citation_rate", "tool_success_rate"]:
        p_value = ttest(results[Variant.CONTROL][metric], results[Variant.TREATMENT_A][metric])
        print(f"{metric}: p-value = {p_value} ({'significant' if p_value < 0.05 else 'not significant'})")
    
    return results
```

**Example A/B test results:**

| Metric | Control (Haiku) | Treatment A (Sonnet) | Treatment B (Haiku+Rerank) | Winner |
|--------|-----------------|----------------------|----------------------------|---------|
| Sample size | 5000 | 2500 | 2500 | - |
| Avg latency | 1.8s | 2.5s | 2.0s | Control |
| Citation rate | 89% | 94% | 93% | Treatment A |
| Tool success | 95% | 97% | 96% | Treatment A |
| User satisfaction | 82% | 88% | 85% | Treatment A |
| Cost per query | $0.005 | $0.025 | $0.006 | Control |

**Decision framework:**
- If Treatment A wins on quality but costs 5x → depends on business value
- If Treatment B wins on quality with only +20% cost → ship it
- If no variant significantly better → keep Control (simplicity)

## RAGAS Integration (Advanced)

**When to use:** Production system with budget for deep evaluation.

```python
# backend/tests/test_ragas_eval.py (optional, expensive)
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall

def run_ragas_evaluation(sample_size=50):
    """
    Run RAGAS evaluation on sample of RAG queries.
    
    Cost: ~$0.10 per sample (uses LLM for scoring)
    """
    
    # Sample production RAG queries
    samples = sample_rag_conversations(n=sample_size)
    
    eval_dataset = {
        "question": [s["query"] for s in samples],
        "contexts": [s["retrieved_chunks"] for s in samples],
        "answer": [s["agent_response"] for s in samples],
        "ground_truth": [s["expected_answer"] for s in samples]  # From golden dataset
    }
    
    results = evaluate(
        eval_dataset,
        metrics=[faithfulness, answer_relevancy, context_recall]
    )
    
    return results

# Run weekly, not in CI (too expensive)
# python -m backend.tests.test_ragas_eval
```

## Cost Analysis

| Component | Frequency | Cost per Run | Monthly Cost |
|-----------|-----------|--------------|--------------|
| **Golden dataset tests** | Every commit (CI) | $0 (local FAISS) | $0 |
| **Production sampling** | Continuous | $0 (metric collection) | $0 |
| **Human labeling** | Weekly (50 samples) | $0.50/sample × 50 | $25 |
| **A/B test analysis** | Ad-hoc | $0 (query metrics) | $0 |
| **RAGAS evaluation** | Monthly (50 samples) | $0.10/sample × 50 | $5 |
| **Total** | | | **$30/mo** |

**Optional:**
- Skip human labeling → save $25/mo (rely on user feedback + automated metrics)
- Skip RAGAS → save $5/mo (use simpler keyword-based metrics)
- **Minimal eval cost: $0/mo** (golden dataset + automated metrics only)

## Implementation Priority

**Phase 1: Golden Dataset (Day 1, 0.5 days)**
1. Create 30 test cases covering RAG, order status, edge cases
2. Implement test runner (`test_golden.py`)
3. Add to CI/CD pipeline
4. Achieve 90% pass rate baseline

**Phase 2: Production Metrics (Day 1.5, 0.5 days)**
1. Add quality metric emission to routes.py
2. Create CloudWatch dashboard
3. Set up alarms (citation rate, tool success)

**Phase 3: Human Labeling (Ongoing)**
1. Weekly sampling script
2. CSV export for labeling
3. Track trends over time

**Phase 4: A/B Testing (As needed)**
1. Implement variant assignment
2. Run experiment for 1-2 weeks
3. Analyze results, ship winner

## Summary

**Current:** Manual testing, no quality metrics, no regression detection

**Designed:**
- Golden dataset: 30 test cases, 90% pass rate gate in CI/CD
- Production monitoring: Citation rate, tool success, latency, user satisfaction
- Human labeling: 50 samples/week for deep quality assessment
- A/B testing: Framework for comparing variants (models, prompts, techniques)

**Cost:** $0-30/mo (depending on human labeling budget)

**Effort:** 1 day implementation (golden dataset + metrics), ongoing maintenance (pattern updates)

**SA value demonstrated:**
- Quality-first mindset (measure before/after changes)
- Pragmatic approach (start with golden dataset, add advanced eval later)
- Production thinking (regression prevention, continuous monitoring)
- Data-driven optimization (A/B tests prove improvements)
- Cost-conscious design (golden dataset is free, RAGAS optional)

**Production checklist:**
- [ ] Create golden dataset with 30 test cases
- [ ] Achieve 90% baseline pass rate
- [ ] Add to CI/CD (block deployment if <90%)
- [ ] Emit quality metrics in production
- [ ] Set up CloudWatch dashboard + alarms
- [ ] Weekly sampling for human labeling
- [ ] Run first A/B test (prompt variant)
- [ ] Iterate: add test cases when bugs found

**Next steps:**
- Review golden dataset with stakeholders (are test cases representative?)
- Set SLA targets (citation rate >90%, tool success >95%)
- Plan first A/B test (reranking vs baseline)
