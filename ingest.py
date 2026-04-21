"""
Knowledge Ingestion Script
Run this whenever you add new files to the knowledge/ folder:
    python ingest.py

Supported file types: .txt, .md, .pdf, .docx, .json
"""

import os
import json
import hashlib
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# PDF support
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠️  pdfplumber not installed. PDF files will be skipped.")
    print("   Install with: pip install pdfplumber")

# DOCX support
try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False
    print("⚠️  python-docx not installed. DOCX files will be skipped.")
    print("   Install with: pip install python-docx")

# ── Config ────────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR = Path("./knowledge")
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "jasper_knowledge"
CHUNK_SIZE = 400        # characters per chunk
CHUNK_OVERLAP = 80      # overlap between chunks for context continuity


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks for better retrieval."""
    chunks = []
    start = 0
    text = text.strip()
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def extract_text(filepath: Path) -> str:
    """Extract text content from a file based on its extension."""
    ext = filepath.suffix.lower()

    if ext in (".txt", ".md"):
        return filepath.read_text(encoding="utf-8", errors="replace")

    elif ext == ".pdf":
        if not PDF_SUPPORT:
            print(f"  ⚠️  Skipping {filepath.name} — pdfplumber not installed")
            return ""
        with pdfplumber.open(filepath) as pdf:
            return "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            )

    elif ext == ".docx":
        if not DOCX_SUPPORT:
            print(f"  ⚠️  Skipping {filepath.name} — python-docx not installed")
            return ""
        doc = docx.Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    elif ext == ".json":
        data = json.loads(filepath.read_text(encoding="utf-8"))
        # Expect either a list of strings or list of {"q": ..., "a": ...} dicts
        if isinstance(data, list):
            parts = []
            for item in data:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    q = item.get("question", item.get("q", ""))
                    a = item.get("answer", item.get("a", ""))
                    if q and a:
                        parts.append(f"Q: {q}\nA: {a}")
                    else:
                        parts.append(json.dumps(item))
            return "\n\n".join(parts)
        return json.dumps(data, indent=2)

    else:
        print(f"  ⚠️  Unsupported file type: {ext}. Skipping {filepath.name}")
        return ""


def file_hash(filepath: Path) -> str:
    """Generate a hash for a file to detect changes."""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def main():
    print("🧠 Jasper AI — Knowledge Ingestion")
    print("=" * 45)

    # Create knowledge dir if it doesn't exist
    KNOWLEDGE_DIR.mkdir(exist_ok=True)

    # List files
    all_files = [
        f for f in KNOWLEDGE_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in (".txt", ".md", ".pdf", ".docx", ".json")
    ]

    if not all_files:
        print(f"\n⚠️  No files found in {KNOWLEDGE_DIR}/")
        print("Add .txt, .md, .pdf, .docx, or .json files and run again.\n")
        print("Example file structure:")
        print("  knowledge/")
        print("    cv.pdf")
        print("    notes.md")
        print("    qa_pairs.json   ← {\"question\": \"...\", \"answer\": \"...\"}")
        return

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"\n📁 Found {len(all_files)} file(s) in {KNOWLEDGE_DIR}/\n")

    total_chunks = 0
    for filepath in all_files:
        print(f"  📄 Processing: {filepath.name}")
        text = extract_text(filepath)

        if not text.strip():
            print(f"     ⚠️  Empty or unreadable — skipped\n")
            continue

        chunks = chunk_text(text)
        print(f"     → {len(chunks)} chunks extracted")

        # Create unique IDs using filename + chunk index + hash
        fhash = file_hash(filepath)[:8]
        ids = [f"{filepath.stem}_{fhash}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filepath.name, "chunk_index": i} for i in range(len(chunks))]

        # Upsert (add or update) into ChromaDB
        collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)
        total_chunks += len(chunks)
        print(f"     ✅ Stored successfully\n")

    print("=" * 45)
    print(f"✅ Done! {total_chunks} total chunks stored.")
    print(f"📦 Total in DB: {collection.count()} chunks")
    print("\nYou can now run: streamlit run app.py\n")


if __name__ == "__main__":
    main()
