"""RAG retriever wrapper with formatted output."""

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class FormattedRetriever:
    """Wrapper around FAISS retriever that formats results for agent consumption."""

    def __init__(self, vectorstore: FAISS, k: int = 4):
        """
        Initialize retriever.

        Args:
            vectorstore: FAISS vector store
            k: Number of documents to retrieve
        """
        self.retriever: BaseRetriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )

    def retrieve(self, query: str) -> str:
        """
        Retrieve and format relevant documents.

        Args:
            query: User query

        Returns:
            Formatted string with retrieved information and sources
        """
        docs: list[Document] = self.retriever.invoke(query)

        if not docs:
            return "No relevant information found in the knowledge base."

        formatted_parts = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content.strip()
            page = doc.metadata.get("page", "unknown")
            section = doc.metadata.get("section", "")

            formatted_parts.append(f"[Source {i} - Page {page}]")
            if section:
                formatted_parts.append(f"Section: {section}")
            formatted_parts.append(content)
            formatted_parts.append("")  # blank line

        return "\n".join(formatted_parts)
