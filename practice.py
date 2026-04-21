"""
Practice Engine — Engine 2: Active Learning
- Generates quiz questions from YOUR knowledge base
- Grades your answers using the LLM as examiner
- Tracks scores and identifies knowledge gaps
- The harder you practice, the better the AI responds too

Uses Ollama locally — no API key, no credit card, no internet needed.
"""

import os
import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "jasper_knowledge"
DB_PATH = "./skill_data.db"

OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:14b"

# ── Skill domains — map to your actual fields ─────────────────────────────────
DOMAINS = {
    "cybersecurity":       "Cybersecurity, networking, vulnerabilities, threat analysis",
    "reverse_engineering": "Reverse engineering, binary analysis, disassembly, exploits",
    "machine_learning":    "ML, deep learning, neural networks, model training",
    "embedded_systems":    "Microcontrollers, firmware, RTOS, hardware interfaces",
    "python":              "Python programming, algorithms, data structures",
    "general_cs":          "Computer science fundamentals, OS, networking, databases",
}

DIFFICULTY_PROMPTS = {
    "beginner":      "Ask a basic conceptual question. Single correct answer. No code required.",
    "intermediate":  "Ask a question that requires applying knowledge. May involve a short code snippet or scenario.",
    "professional":  "Ask a difficult, scenario-based question a senior engineer or security professional would face. Requires deep understanding.",
    "expert":        "Ask a question at the level of a CTF challenge, research paper, or technical interview at a top company. Expect multi-step reasoning.",
}


def call_ollama(messages: list[dict], temperature: float = 0.3, max_tokens: int = 1000) -> str:
    """Call the local Ollama server and return the response text."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return '{"error": "Ollama is not running. Please start it first."}'
    except Exception as e:
        return f'{{"error": "Ollama error: {e}"}}'


class PracticeEngine:
    def __init__(self):
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database for tracking practice sessions."""
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                domain TEXT,
                difficulty TEXT,
                question TEXT,
                correct_answer TEXT,
                user_answer TEXT,
                score INTEGER,
                feedback TEXT,
                knowledge_source TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT,
                topic TEXT,
                detected_at TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)
        con.commit()
        con.close()

    def _get_context(self, domain: str, n: int = 5) -> tuple[str, str]:
        """Pull relevant knowledge chunks from a domain to base questions on."""
        count = self.collection.count()
        if count == 0:
            return "", ""
        results = self.collection.query(
            query_texts=[DOMAINS[domain]],
            n_results=min(n, count),
            include=["documents", "metadatas"],
        )
        docs = results["documents"][0]
        sources = [m.get("source", "unknown") for m in results["metadatas"][0]]
        context = "\n\n---\n\n".join(docs)
        source_str = "; ".join(set(s.split(":")[0] if ":" in s else s for s in sources))
        return context, source_str

    def generate_question(self, domain: str, difficulty: str = "intermediate") -> dict:
        """Generate a quiz question grounded in your actual knowledge base."""
        context, sources = self._get_context(domain)
        domain_desc = DOMAINS.get(domain, domain)
        diff_prompt = DIFFICULTY_PROMPTS.get(difficulty, DIFFICULTY_PROMPTS["intermediate"])

        system = """You are a rigorous technical examiner creating practice questions.
Return ONLY valid JSON with this exact structure, no extra text, no markdown fences:
{
  "question": "The full question text",
  "type": "multiple_choice",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "A",
  "explanation": "Why this is the correct answer",
  "difficulty": "the difficulty level"
}
For open ended questions set type to open_ended and options to [].
Base the question on the provided knowledge context when possible."""

        user = f"""Domain: {domain_desc}
Difficulty instruction: {diff_prompt}

Knowledge context to base the question on:
{context[:2000] if context else "Use your general knowledge of this domain."}

Generate one practice question in the exact JSON format specified. No markdown, no extra text."""

        raw = call_ollama(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=800,
        )

        # Strip markdown fences if model added them anyway
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            q = json.loads(raw)
            q["domain"] = domain
            q["sources"] = sources
            return q
        except json.JSONDecodeError:
            # Fallback question if parsing fails
            return {
                "question": "What does the CIA triad stand for in cybersecurity?",
                "type": "multiple_choice",
                "options": [
                    "A) Confidentiality, Integrity, Availability",
                    "B) Control, Inspection, Authentication",
                    "C) Cryptography, Identification, Authorization",
                    "D) Classification, Integrity, Access",
                ],
                "correct_answer": "A",
                "explanation": "The CIA triad is the core model: Confidentiality (only authorized access), Integrity (data is accurate and unaltered), Availability (systems accessible when needed).",
                "difficulty": difficulty,
                "domain": domain,
                "sources": sources,
            }

    def grade_answer(self, question: dict, user_answer: str) -> dict:
        """Grade the user's answer and provide detailed feedback."""
        system = """You are a strict but fair technical examiner. Grade the answer and return ONLY valid JSON with no extra text or markdown:
{
  "score": 0,
  "verdict": "correct",
  "feedback": "Detailed explanation of what was right or wrong",
  "correct_answer": "The full correct answer",
  "gaps": ["specific knowledge gap 1", "specific knowledge gap 2"]
}
score is 0 to 100. verdict is correct, partial, or incorrect.
gaps should be specific topics the user needs to study. Use an empty list if fully correct.
Be strict — partial credit only if the core concept is understood but details are missing."""

        options_str = "\n".join(question.get("options", [])) if question.get("options") else ""

        user = f"""Question: {question['question']}
{f"Options:{chr(10)}{options_str}" if options_str else ""}
Correct answer: {question['correct_answer']}
Explanation: {question.get('explanation', '')}

User's answer: {user_answer}

Grade this answer. Return only JSON, no markdown."""

        raw = call_ollama(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            result = json.loads(raw)
        except Exception:
            # Fallback: simple exact match for multiple choice
            correct = question.get("correct_answer", "").strip().upper()
            given = user_answer.strip().upper()
            score = 100 if (given == correct or given.startswith(correct)) else 0
            result = {
                "score": score,
                "verdict": "correct" if score == 100 else "incorrect",
                "feedback": question.get("explanation", "Check the correct answer above."),
                "correct_answer": question.get("correct_answer", ""),
                "gaps": [] if score == 100 else [f"Review: {question.get('domain', 'this topic')}"],
            }

        # Save session to database
        gaps = result.get("gaps", [])
        con = sqlite3.connect(DB_PATH)
        con.execute("""
            INSERT INTO sessions (ts, domain, difficulty, question, correct_answer,
                                  user_answer, score, feedback, knowledge_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            question.get("domain", "general"),
            question.get("difficulty", "intermediate"),
            question["question"],
            question.get("correct_answer", ""),
            user_answer,
            result.get("score", 0),
            result.get("feedback", ""),
            question.get("sources", ""),
        ))
        for gap in gaps:
            con.execute("""
                INSERT INTO gaps (domain, topic, detected_at)
                VALUES (?, ?, ?)
            """, (question.get("domain", "general"), gap, datetime.now().isoformat()))
        con.commit()
        con.close()

        return result

    def get_skill_scores(self) -> dict:
        """Get current skill scores per domain."""
        con = sqlite3.connect(DB_PATH)
        rows = con.execute("""
            SELECT domain,
                   AVG(score) as avg_score,
                   COUNT(*) as attempts,
                   SUM(CASE WHEN score >= 80 THEN 1 ELSE 0 END) as correct
            FROM sessions
            GROUP BY domain
        """).fetchall()
        con.close()
        scores = {}
        for row in rows:
            scores[row[0]] = {
                "avg": round(row[1], 1),
                "attempts": row[2],
                "correct": row[3],
                "level": _score_to_level(row[1]),
            }
        return scores

    def get_top_gaps(self, limit: int = 5) -> list[dict]:
        """Get the most frequently identified knowledge gaps."""
        con = sqlite3.connect(DB_PATH)
        rows = con.execute("""
            SELECT domain, topic, COUNT(*) as freq
            FROM gaps
            WHERE resolved = 0
            GROUP BY domain, topic
            ORDER BY freq DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return [{"domain": r[0], "topic": r[1], "frequency": r[2]} for r in rows]

    def get_recent_sessions(self, limit: int = 10) -> list[dict]:
        """Get recent practice session history."""
        con = sqlite3.connect(DB_PATH)
        rows = con.execute("""
            SELECT ts, domain, difficulty, score, question
            FROM sessions ORDER BY ts DESC LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return [
            {
                "ts": r[0],
                "domain": r[1],
                "difficulty": r[2],
                "score": r[3],
                "question": r[4][:80] + "...",
            }
            for r in rows
        ]


def _score_to_level(avg: float) -> str:
    if avg >= 90:
        return "Expert"
    elif avg >= 75:
        return "Professional"
    elif avg >= 55:
        return "Intermediate"
    elif avg >= 35:
        return "Beginner"
    else:
        return "Novice"