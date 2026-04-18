"""Tests for RAG components."""

import pytest
from langchain_core.documents import Document

from app.rag.ingest import detect_section, load_and_chunk_pdf


def test_detect_section_item():
    """Test detection of ITEM sections."""
    text = "ITEM 1. Business\n\nOur company..."
    section = detect_section(text)
    assert section == "ITEM 1. Business"


def test_detect_section_uppercase():
    """Test detection of all-caps sections."""
    text = "RISK FACTORS\n\nThe following are risks..."
    section = detect_section(text)
    assert section == "RISK FACTORS"


def test_detect_section_none():
    """Test when no section header is present."""
    text = "This is regular paragraph text without a header."
    section = detect_section(text)
    assert section is None


@pytest.mark.skipif(
    True,
    reason="Requires PDF file and AWS credentials - run manually",
)
def test_load_and_chunk_pdf():
    """Integration test for PDF loading (requires actual PDF)."""
    from pathlib import Path

    pdf_path = Path(__file__).parents[2] / "dataset" / "raw" / "Company-10k-18pages.pdf"

    if not pdf_path.exists():
        pytest.skip("PDF file not found")

    chunks = load_and_chunk_pdf(pdf_path)

    assert len(chunks) > 0
    assert all(isinstance(chunk, Document) for chunk in chunks)
    assert all("page" in chunk.metadata for chunk in chunks)
    assert all("source" in chunk.metadata for chunk in chunks)
