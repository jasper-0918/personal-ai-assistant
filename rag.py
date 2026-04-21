"""
rag.py — Local RAG Pipeline
Runs entirely on your machine using Ollama. No API key needed.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
import config

def load_personality() -> str:
    p = Path("personality.txt")
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"You are {config.YOUR_NAME}'s personal AI assistant. Be direct and helpful."


def call_ollama(messages: list[dict], model: str = None,
                temperature: float = 0.3, max_tokens: int = 1024) -> str:
    model = model or config.OLLAMA_MODEL
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"temperature": temperature, "num_predict": max_tokens}},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        return ("⚠️ Ollama is not running.\n"
                "- Windows: click the Ollama icon in your taskbar\n"
                "- Mac/Linux: run `ollama serve` in a terminal")
    except Exception as e:
        return f"⚠️ Ollama error: {e}"


class RAGAssistant:
    def __init__(self, model: str = None):
        self.model = model or config.OLLAMA_MODEL
        self.personality = load_personality()
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name=config.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.corrections_col = self.client.get_or_create_collection(
            name=config.CORRECTIONS_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _retrieve_corrections(self, query: str, top_k: int = 2) -> list[dict]:
        if self.corrections_col.count() == 0:
            return []
        results = self.corrections_col.query(
            query_texts=[query],
            n_results=min(top_k, self.corrections_col.count()),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"text": doc, "source": "your correction (verified)",
             "preview": doc[:120].replace("\n", " ") + "...",
             "relevance": round(1 - dist, 3), "is_correction": True}
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ) if dist < 0.55
        ]

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"text": doc, "source": meta.get("source", "unknown"),
             "preview": doc[:120].replace("\n", " ") + "...",
             "relevance": round(1 - dist, 3), "is_correction": False}
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ) if dist < 0.75
        ]

    def query(self, question: str, chat_history: list[dict] | None = None,
              top_k: int = 3, temperature: float = 0.3,
              model: str | None = None, extra_context: list[dict] | None = None,
              ) -> tuple[str, list[dict]]:
        model = model or self.model
        corrections = self._retrieve_corrections(question, top_k=2)
        chunks = self.retrieve(question, top_k=top_k)
        all_sources = corrections + chunks

        system_text = self.personality
        if corrections:
            system_text += "\n\n## CORRECTIONS — use these first:\n"
            system_text += "\n\n".join(c["text"] for c in corrections)
        if chunks:
            system_text += "\n\n## Knowledge base:\n"
            for i, c in enumerate(chunks, 1):
                system_text += f"\n[{i}] From {c['source']}:\n{c['text']}\n"

        messages = [{"role": "system", "content": system_text}]
        if chat_history:
            for turn in chat_history[-6:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        answer = call_ollama(messages, model=model, temperature=temperature)
        return answer, all_sources
