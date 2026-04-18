"""LangChain tool definitions for the agent."""

from langchain_core.tools import tool

from app.mock.order_api import format_order_status, lookup_order
from app.rag.retriever import FormattedRetriever


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
        return retriever.retrieve(query)

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
        if not full_name or not full_name.strip():
            return "Error: Full name is required for verification."

        if not last4_ssn or len(last4_ssn) != 4 or not last4_ssn.isdigit():
            return "Error: Last 4 digits of SSN must be exactly 4 digits."

        if not date_of_birth or len(date_of_birth) != 10:
            return "Error: Date of birth must be in YYYY-MM-DD format."

        order = lookup_order(full_name, last4_ssn, date_of_birth)

        if order is None:
            return (
                "I apologize, but I couldn't find an order matching the provided "
                "verification information. Please verify that your full name, last 4 "
                "digits of SSN, and date of birth are correct."
            )

        return format_order_status(order)

    return [search_knowledge_base, check_order_status]
