"""LangChain tool definitions for the agent."""

import hashlib
import logging
import time

from langchain_core.tools import tool

from app.observability import emit_metrics
from app.rag.retriever import FormattedRetriever
from app.storage.orders import format_order_status, lookup_order

logger = logging.getLogger(__name__)


def create_tools(retriever: FormattedRetriever) -> list:
    """
    Create tool list for the agent.

    Args:
        retriever: Initialized FormattedRetriever instance

    Returns:
        List of tool functions
    """

    @tool
    def search_knowledge_base(query: str) -> str:
        """
        Search the company's 10-K financial filing to answer questions about the company.

        Use this tool for questions about:
        - Company financials (revenue, expenses, profit)
        - Business operations and strategy
        - Risk factors
        - Market information
        - Any other information from the company's official filings

        Args:
            query: The question or search query

        Returns:
            Relevant information from the 10-K filing with source citations
        """
        start_time = time.perf_counter()
        try:
            result = retriever.retrieve(query)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Check if retrieval returned results
            if not result or result.strip() == "":
                logger.warning("rag_no_results", extra={"query": query[:100]})
                emit_metrics(
                    metrics=[
                        {"Name": "ToolCallLatency", "Unit": "Milliseconds", "Value": latency_ms},
                        {"Name": "ToolCallSuccess", "Unit": "Count", "Value": 0},
                    ],
                    dimensions={"Tool": "search_knowledge_base"},
                    properties={"query_length": len(query), "result": "no_context"},
                )
                return (
                    "NO_CONTEXT_FOUND: I don't have information about this in our knowledge base."
                )

            # Add instruction for LLM to enforce grounding
            emit_metrics(
                metrics=[
                    {"Name": "ToolCallLatency", "Unit": "Milliseconds", "Value": latency_ms},
                    {"Name": "ToolCallSuccess", "Unit": "Count", "Value": 1},
                ],
                dimensions={"Tool": "search_knowledge_base"},
                properties={"query_length": len(query), "result_length": len(result)},
            )
            return f"""{result}

Remember: Answer ONLY based on this context. If it doesn't answer the question, say "I don't have that information."
"""
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error("rag_retrieval_failed", extra={"error": str(e)})
            emit_metrics(
                metrics=[
                    {"Name": "ToolCallLatency", "Unit": "Milliseconds", "Value": latency_ms},
                    {"Name": "ToolCallSuccess", "Unit": "Count", "Value": 0},
                    {"Name": "ErrorRate", "Unit": "Count", "Value": 1},
                ],
                dimensions={"Tool": "search_knowledge_base", "ErrorType": "rag_retrieval_failed"},
                properties={"query_length": len(query)},
            )
            return "Knowledge base temporarily unavailable. Please try again."

    @tool
    def check_order_status(
        full_name: str,
        last4_ssn: str,
        date_of_birth: str,
    ) -> str:
        """
        Check the shipment status of a customer's order.

        IMPORTANT: This tool requires customer identity verification. You MUST collect
        ALL THREE pieces of information before calling this tool:
        1. full_name: Customer's full name (e.g., "John Smith")
        2. last4_ssn: Last 4 digits of Social Security Number (e.g., "1234")
        3. date_of_birth: Date of birth in YYYY-MM-DD format (e.g., "1990-01-15")

        Do NOT call this tool if any of these fields are missing. Ask the customer for
        the missing information first.

        Args:
            full_name: Customer's full name
            last4_ssn: Last 4 digits of SSN (exactly 4 digits)
            date_of_birth: Date of birth in YYYY-MM-DD format

        Returns:
            Order status information if verification succeeds, error message otherwise
        """
        start_time = time.perf_counter()
        # Validate inputs
        if not full_name or not full_name.strip():
            return "Error: Full name is required for verification."

        if not last4_ssn or len(last4_ssn) != 4 or not last4_ssn.isdigit():
            return "Error: Last 4 digits of SSN must be exactly 4 digits."

        if not date_of_birth or len(date_of_birth) != 10:
            return "Error: Date of birth must be in YYYY-MM-DD format."

        # CRITICAL: Hash PII for logging (one-way, never store raw PII)
        identity_hash = hashlib.sha256(
            f"{full_name}:{last4_ssn}:{date_of_birth}".encode()
        ).hexdigest()[:16]

        # Log ONLY the hash, never raw PII
        logger.info(
            "order_verification_attempt",
            extra={"identity_hash": identity_hash, "event_type": "identity_verification"},
        )

        # Lookup in mock DB
        order = lookup_order(full_name, last4_ssn, date_of_birth)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if order is None:
            logger.info(
                "order_verification_failed",
                extra={"identity_hash": identity_hash, "reason": "not_found"},
            )
            emit_metrics(
                metrics=[
                    {"Name": "ToolCallLatency", "Unit": "Milliseconds", "Value": latency_ms},
                    {"Name": "ToolCallSuccess", "Unit": "Count", "Value": 0},
                    {"Name": "OrderLookupFailure", "Unit": "Count", "Value": 1},
                ],
                dimensions={"Tool": "check_order_status"},
                properties={"result": "not_found"},
            )
            return (
                "I apologize, but I couldn't find an order matching the provided "
                "verification information. Please verify that your full name, last 4 "
                "digits of SSN, and date of birth are correct."
            )

        # Return ONLY order info, never identity fields
        logger.info(
            "order_verification_success",
            extra={"identity_hash": identity_hash, "order_id": order["order_id"]},
        )
        emit_metrics(
            metrics=[
                {"Name": "ToolCallLatency", "Unit": "Milliseconds", "Value": latency_ms},
                {"Name": "ToolCallSuccess", "Unit": "Count", "Value": 1},
                {"Name": "OrderLookupSuccess", "Unit": "Count", "Value": 1},
            ],
            dimensions={"Tool": "check_order_status"},
            properties={"order_id": order["order_id"]},
        )
        return format_order_status(order)

    return [search_knowledge_base, check_order_status]
