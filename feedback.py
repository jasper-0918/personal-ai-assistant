"""
Feedback Loop — Engine 3: Learning from Mistakes
- Thumbs up = marks answer as correct
- Thumbs down = stores your correction as a HIGH-PRIORITY knowledge chunk
- Corrections are ALWAYS retrieved first on similar future questions
- Over time the AI stops repeating the same mistakes
"""

import sqlite3
import hashlib
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DB_PATH        = "./chroma_db"
CORRECTIONS_COLLECTION = "jasper_corrections"
DB_PATH               = "./skill_data.db"


def _get_corrections_collection():
    """Corrections live in their own collection — always retrieved with priority."""
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_or_create_collection(
        name=CORRECTIONS_COLLECTION,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def init_feedback_db():
    """Create the feedback table if it doesn't exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            question TEXT,
            ai_answer TEXT,
            rating INTEGER,
            correction TEXT,
            stored_in_db INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()


def record_thumbs_up(question: str, ai_answer: str):
    """Mark an answer as correct."""
    _insert(question, ai_answer, rating=1, correction=None)


def record_correction(question: str, ai_answer: str, correction: str):
    """
    Store a correction permanently.
    The correct answer is added as a high-priority chunk in ChromaDB
    so future similar questions retrieve it first.
    """
    _insert(question, ai_answer, rating=-1, correction=correction)

    col = _get_corrections_collection()
    chunk = (
        f"CORRECTION\n"
        f"Question: {question}\n\n"
        f"Wrong answer: {ai_answer}\n\n"
        f"Correct answer: {correction}"
    )
    doc_id = f"correction_{hashlib.md5((question + correction).encode()).hexdigest()[:12]}"
    col.upsert(
        documents=[chunk],
        ids=[doc_id],
        metadatas=[{
            "source": "user_correction",
            "question": question[:200],
            "corrected_at": datetime.now().isoformat(),
            "priority": "critical",
        }],
    )
    return doc_id


def get_corrections(query: str, top_k: int = 3) -> list[dict]:
    """
    Retrieve stored corrections relevant to a query.
    Always call this before the main knowledge retrieval.
    """
    col = _get_corrections_collection()
    if col.count() == 0:
        return []
    results = col.query(
        query_texts=[query],
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        if dist < 0.6:
            chunks.append({
                "text": doc,
                "source": "correction (verified by Jasper)",
                "preview": doc[:120].replace("\n", " ") + "...",
                "relevance": round(1 - dist, 3),
                "is_correction": True,
            })
    return chunks


def get_feedback_stats() -> dict:
    """Return summary stats for the sidebar."""
    init_feedback_db()
    con = sqlite3.connect(DB_PATH)
    row = con.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN rating =  1 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as corrections
        FROM feedback
    """).fetchone()
    con.close()
    total = row[0] or 0
    pos   = row[1] or 0
    accuracy = round(pos / total * 100, 1) if total > 0 else 0
    return {
        "total_ratings":      total,
        "thumbs_up":          pos,
        "corrections":        row[2] or 0,
        "accuracy_pct":       accuracy,
        "corrections_stored": _get_corrections_collection().count(),
    }


def _insert(question, ai_answer, rating, correction):
    init_feedback_db()
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO feedback (ts, question, ai_answer, rating, correction, stored_in_db)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        question[:500],
        ai_answer[:1000],
        rating,
        correction[:1000] if correction else None,
        1 if correction else 0,
    ))
    con.commit()
    con.close()
