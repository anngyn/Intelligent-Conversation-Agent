"""
Standalone script to ingest PDF and build FAISS index.

Usage:
    python scripts/ingest_pdf.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.rag.ingest import load_and_chunk_pdf
from app.rag.store import build_vector_store, save_vector_store


def main():
    """Main ingestion pipeline."""
    pdf_path = Path(__file__).parents[2] / "dataset" / "raw" / "Company-10k-18pages.pdf"

    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}")
        sys.exit(1)

    print(f"Loading PDF from: {pdf_path}")
    chunks = load_and_chunk_pdf(pdf_path)
    print(f"Created {len(chunks)} chunks")

    print("Building FAISS index...")
    vectorstore = build_vector_store(chunks)

    output_path = Path(__file__).parents[2] / settings.faiss_index_path
    print(f"Saving index to: {output_path}")
    save_vector_store(vectorstore, output_path)

    print("✓ Ingestion complete!")


if __name__ == "__main__":
    main()
