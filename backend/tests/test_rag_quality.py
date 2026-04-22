"""RAG quality evaluation tests (groundedness and retrieval accuracy)."""

import pytest

from app.rag.retriever import FormattedRetriever
from app.rag.store import load_vector_store


# Golden dataset (hand-labeled test cases)
EVAL_DATASET = [
    {
        "question": "What is Amazon's business focus?",
        "expected_keywords": ["customer", "long-term", "innovation"],
    },
    {
        "question": "What are Amazon's primary revenue sources?",
        "expected_keywords": ["online stores", "AWS", "advertising"],
    },
    {
        "question": "What are Amazon's main risk factors?",
        "expected_keywords": ["competition", "regulatory", "cybersecurity"],
    },
]


@pytest.fixture
def retriever():
    """Load FAISS retriever for testing."""
    vectorstore = load_vector_store("dataset/processed/faiss_index")
    return FormattedRetriever(vectorstore, k=4)


def test_retrieval_returns_results(retriever):
    """Test that retriever returns non-empty results for valid queries."""
    for item in EVAL_DATASET:
        result = retriever.retrieve(item["question"])

        # Should return results
        assert result is not None
        assert len(result) > 0
        assert result != "No relevant information found in the knowledge base."


def test_retrieval_contains_expected_keywords(retriever):
    """Test that retrieved results contain expected keywords (basic relevance check)."""
    for item in EVAL_DATASET:
        result = retriever.retrieve(item["question"])

        # At least one expected keyword should appear (case-insensitive)
        result_lower = result.lower()
        keyword_found = any(kw.lower() in result_lower for kw in item["expected_keywords"])

        assert keyword_found, (
            f"Query: {item['question']}\n"
            f"Expected keywords: {item['expected_keywords']}\n"
            f"Retrieved result: {result[:200]}..."
        )


def test_retrieval_includes_citations(retriever):
    """Test that retrieved results include page citations."""
    for item in EVAL_DATASET:
        result = retriever.retrieve(item["question"])

        # Should include page citations in format "[Source X - Page Y]"
        assert "[Source" in result, f"Missing citation in result: {result[:200]}"
        assert "Page" in result, f"Missing page number in result: {result[:200]}"


def test_empty_query_handling(retriever):
    """Test that retriever handles empty queries gracefully."""
    result = retriever.retrieve("")

    # Should return something (either results or error message)
    assert result is not None
    assert len(result) > 0


def test_nonsense_query_handling(retriever):
    """Test that retriever handles nonsense queries gracefully."""
    result = retriever.retrieve("xyzabc123 nonsense query that should not match anything")

    # Should return results or graceful message (FAISS may still return results)
    assert result is not None
    assert len(result) > 0


# Note: Full RAGAS evaluation (faithfulness, answer_relevancy) requires
# installing ragas package and running inference, which is expensive for CI.
# For production, add these tests in a separate evaluation suite.
