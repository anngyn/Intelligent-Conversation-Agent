"""PDF ingestion and chunking pipeline for RAG."""

import re
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Common 10-K section headers for metadata extraction
SECTION_PATTERNS = [
    r"^ITEM\s+\d+[A-Z]?[\.\:]",  # ITEM 1, ITEM 1A, etc.
    r"^PART\s+[IVX]+",  # PART I, PART II, etc.
    r"^(BUSINESS|RISK FACTORS|FINANCIAL|MANAGEMENT|MARKET|SELECTED FINANCIAL)",
]


def detect_section(text: str) -> str | None:
    """Detect if text contains a section header."""
    lines = text.strip().split("\n")[:3]  # Check first 3 lines

    for line in lines:
        line = line.strip()
        if not line:
            continue

        for pattern in SECTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return line

        if line.isupper() and len(line) > 5 and len(line) < 100:
            return line

    return None


def load_and_chunk_pdf(
    pdf_path: str | Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """
    Load PDF and split into chunks with metadata.

    Args:
        pdf_path: Path to PDF file
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Overlap between chunks in characters

    Returns:
        List of Document objects with text and metadata
    """
    loader = PyPDFLoader(str(pdf_path))
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = []
    current_section = None

    for page in pages:
        page_chunks = splitter.split_documents([page])

        for chunk in page_chunks:
            section = detect_section(chunk.page_content)
            if section:
                current_section = section

            if current_section:
                chunk.metadata["section"] = current_section

            chunk.metadata["source"] = "Amazon 10-K Filing"

            chunks.append(chunk)

    return chunks
