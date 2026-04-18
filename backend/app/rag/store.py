"""FAISS vector store initialization and management."""

from pathlib import Path

from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.config import settings


def create_embeddings() -> BedrockEmbeddings:
    """Create Bedrock embeddings model."""
    return BedrockEmbeddings(
        model_id=settings.bedrock_embedding_model_id,
        region_name=settings.aws_region,
    )


def build_vector_store(documents: list[Document]) -> FAISS:
    """
    Build FAISS vector store from documents.

    Args:
        documents: List of Document objects to index

    Returns:
        FAISS vector store
    """
    embeddings = create_embeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)
    return vectorstore


def save_vector_store(vectorstore: FAISS, path: str | Path) -> None:
    """Save FAISS index to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(path))


def load_vector_store(path: str | Path) -> FAISS:
    """
    Load FAISS index from disk.

    Args:
        path: Path to saved FAISS index

    Returns:
        FAISS vector store
    """
    embeddings = create_embeddings()
    vectorstore = FAISS.load_local(
        str(path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vectorstore
