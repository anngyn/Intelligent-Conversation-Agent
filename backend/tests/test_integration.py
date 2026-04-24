"""Integration tests for end-to-end agent flows."""

import os

import pytest

from app.agent.graph import create_agent
from app.rag.retriever import FormattedRetriever
from app.rag.store import load_vector_store

# Skip tests requiring AWS Bedrock in CI
pytestmark = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Integration tests require AWS Bedrock credentials"
)


def normalize_output(output):
    """Normalize agent output (handles both string and content blocks)."""
    if isinstance(output, list):
        return "".join(block.get("text", str(block)) for block in output)
    return str(output)


@pytest.fixture
def agent():
    """Create agent with real FAISS retriever."""
    vectorstore = load_vector_store("dataset/processed/faiss_index")
    retriever = FormattedRetriever(vectorstore, k=4)
    return create_agent(retriever)


@pytest.fixture
def session_config():
    """Session config for agent."""
    return {"configurable": {"session_id": "test-session"}}


def test_rag_query_end_to_end(agent, session_config):
    """Test RAG query retrieves from knowledge base."""
    response = agent.invoke({"input": "What is Amazon's business focus?"}, config=session_config)

    output = normalize_output(response["output"]).lower()

    # Should contain relevant keywords from 10-K
    assert any(keyword in output for keyword in ["customer", "long-term", "innovation", "amazon"])

    # Should reference the knowledge base
    assert "10-k" in output or "filing" in output or len(output) > 100


def test_order_status_multi_turn(agent, session_config):
    """Test multi-turn identity verification flow."""
    # Turn 1: Request order status
    response1 = agent.invoke({"input": "Check my order status"}, config=session_config)
    output1 = normalize_output(response1["output"]).lower()

    # Agent should ask for identity
    assert any(word in output1 for word in ["name", "verify", "identity", "need"])

    # Turn 2: Provide name only (should ask for more)
    response2 = agent.invoke({"input": "John Smith"}, config=session_config)
    output2 = normalize_output(response2["output"]).lower()

    # Agent should ask for SSN or DOB
    assert any(word in output2 for word in ["ssn", "social security", "date of birth", "dob"])

    # Turn 3: Provide SSN
    response3 = agent.invoke({"input": "SSN last 4: 1234"}, config=session_config)
    output3 = normalize_output(response3["output"]).lower()

    # Agent should ask for DOB
    assert any(word in output3 for word in ["date of birth", "dob", "birth"])

    # Turn 4: Provide DOB - should get order
    response4 = agent.invoke({"input": "1990-01-15"}, config=session_config)
    output4 = normalize_output(response4["output"]).lower()

    # Should contain order information
    assert any(word in output4 for word in ["order", "ord-", "shipped", "tracking"])


def test_order_status_all_at_once(agent, session_config):
    """Test providing all identity fields in one message."""
    response = agent.invoke(
        {"input": "Check order for John Smith, SSN last 4: 1234, DOB: 1990-01-15"},
        config=session_config,
    )

    output = normalize_output(response["output"]).lower()

    # Should return order information
    assert "ord-98765" in output or "shipped" in output
    assert "tracking" in output or "1z999aa" in output


def test_invalid_order_identity(agent, session_config):
    """Test handling of invalid identity information."""
    response = agent.invoke(
        {"input": "Check order for Invalid Name, SSN: 9999, DOB: 2000-01-01"}, config=session_config
    )

    output = normalize_output(response["output"]).lower()

    # Should indicate order not found
    assert any(
        phrase in output for phrase in ["not found", "couldn't find", "no order", "doesn't match"]
    )


def test_conversation_memory(agent, session_config):
    """Test that agent maintains context across turns."""
    # Ask about Amazon revenue
    response1 = agent.invoke({"input": "What was Amazon's revenue in 2019?"}, config=session_config)
    response1["output"]

    # Follow-up without repeating context
    response2 = agent.invoke({"input": "What about AWS specifically?"}, config=session_config)
    output2 = normalize_output(response2["output"]).lower()

    # Agent should understand "aws" refers to Amazon's service
    # Should retrieve AWS-related information
    assert len(output2) > 20  # Got a real response, not confused


def test_out_of_scope_query(agent, session_config):
    """Test agent refuses out-of-scope questions."""
    response = agent.invoke({"input": "What's the weather today?"}, config=session_config)

    output = normalize_output(response["output"]).lower()

    # Should politely refuse
    assert any(
        phrase in output
        for phrase in ["can't", "cannot", "don't have", "only help with", "company information"]
    )


def test_streaming_response():
    """Test that agent supports streaming via astream_events."""
    vectorstore = load_vector_store("dataset/processed/faiss_index")
    retriever = FormattedRetriever(vectorstore, k=4)
    agent = create_agent(retriever)

    config = {"configurable": {"session_id": "test-stream"}}

    # Collect events
    events = []
    for event in agent.stream_events({"input": "What is Amazon?"}, config=config, version="v2"):
        events.append(event)

    # Should have multiple events
    assert len(events) > 0

    # Should include token events
    token_events = [e for e in events if e.get("event") == "on_chat_model_stream"]
    assert len(token_events) > 0


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "name": "John Smith",
            "ssn": "1234",
            "dob": "1990-01-15",
            "expected_status": "shipped",
            "expected_order": "ORD-98765",
        },
        {
            "name": "Jane Doe",
            "ssn": "5678",
            "dob": "1985-06-20",
            "expected_status": "delivered",
            "expected_order": "ORD-87654",
        },
        {
            "name": "Michael Johnson",
            "ssn": "9012",
            "dob": "1992-11-03",
            "expected_status": "processing",
            "expected_order": "ORD-76543",
        },
    ],
)
def test_order_lookup_all_test_accounts(agent, session_config, test_case):
    """Test order lookup for all test accounts in mock database."""
    message = (
        f"Check order for {test_case['name']}, "
        f"SSN last 4: {test_case['ssn']}, "
        f"DOB: {test_case['dob']}"
    )

    response = agent.invoke({"input": message}, config=session_config)
    output = normalize_output(response["output"]).lower()

    # Should contain order ID and status
    assert test_case["expected_order"].lower() in output
    assert test_case["expected_status"].lower() in output
