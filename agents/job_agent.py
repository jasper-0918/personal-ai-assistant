"""
agents/job_agent.py — Job Search & Application Agent
Scrapes free job boards, scores matches against your profile,
generates tailored cover letters with AI, and applies via email.
All free — no paid job APIs.
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import sqlite3
import requests
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

JOB_DB_PATH = "./jobs.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── Database ──────────────────────────────────────────────────────────────────

def init_job_db():
    con = sqlite3.connect(JOB_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, title TEXT, company TEXT, location TEXT,
            url TEXT UNIQUE, description TEXT, date_found TEXT,
            match_score INTEGER DEFAULT 0,
            cover_letter TEXT,
            applied INTEGER DEFAULT 0,
            applied_at TEXT,
            notes TEXT
        )
    """)
    con.commit()
    con.close()


def save_jobs(jobs: list[dict]):
    con = sqlite3.connect(JOB_DB_PATH)
    for job in jobs:
        try:
            con.execute("""
                INSERT OR IGNORE INTO jobs
                (source, title, company, location, url, description, date_found)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("source", ""), job.get("title", ""),
                job.get("company", ""), job.get("location", ""),
                job.get("url", ""), job.get("description", ""),
                datetime.now().isoformat()
            ))
        except Exception:
            pass
    con.commit()
    con.close()


def get_jobs(applied: bool = None, min_score: int = 0, limit: int = 50) -> list[dict]:
    con = sqlite3.connect(JOB_DB_PATH)
    q = "SELECT * FROM jobs WHERE match_score >= ?"
    params = [min_score]
    if applied is not None:
        q += " AND applied = ?"
        params.append(1 if applied else 0)
    q += " ORDER BY match_score DESC, date_found DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(q, params).fetchall()
    cols = [d[0] for d in con.execute(q, params).description] if False else [
        "id", "source", "title", "company", "location", "url",
        "description", "date_found", "match_score", "cover_letter",
        "applied", "applied_at", "notes"
    ]
    con.close()
    return [dict(zip(cols, r)) for r in rows]


def mark_applied(job_id: int, cover_letter: str = ""):
    con = sqlite3.connect(JOB_DB_PATH)
    con.execute("""
        UPDATE jobs SET applied=1, applied_at=?, cover_letter=? WHERE id=?
    """, (datetime.now().isoformat(), cover_letter, job_id))
    con.commit()
    con.close()


# ── Job board scrapers (all free, no API key) ─────────────────────────────────

def scrape_remoteok(keyword: str = "python") -> list[dict]:
    """RemoteOK has a free JSON API — no key needed."""
    jobs = []
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15
        )
        data = resp.json()
        for item in data[1:]:  # first item is legal notice
            if not isinstance(item, dict):
                continue
            title = item.get("position", "")
            if keyword.lower() not in title.lower() and keyword.lower() not in " ".join(item.get("tags", [])).lower():
                continue
            jobs.append({
                "source":      "RemoteOK",
                "title":       title,
                "company":     item.get("company", ""),
                "location":    "Remote",
                "url":         item.get("url", ""),
                "description": item.get("description", "")[:1000],
            })
        time.sleep(1)
    except Exception as e:
        print(f"RemoteOK scrape error: {e}")
    return jobs


def scrape_weworkremotely(keyword: str = "python") -> list[dict]:
    """We Work Remotely — free RSS feed."""
    jobs = []
    try:
        import xml.etree.ElementTree as ET
        categories = ["programming", "devops-sysadmin", "design", "all-other-remote"]
        for cat in categories[:2]:  # limit to avoid hammering
            resp = requests.get(
                f"https://weworkremotely.com/categories/remote-{cat}-jobs.rss",
                headers=HEADERS, timeout=15
            )
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                if keyword.lower() not in title.lower():
                    continue
                jobs.append({
                    "source":      "We Work Remotely",
                    "title":       title,
                    "company":     item.findtext("{https://weworkremotely.com}company", ""),
                    "location":    "Remote",
                    "url":         item.findtext("link", ""),
                    "description": item.findtext("description", "")[:1000],
                })
            time.sleep(1.5)
    except Exception as e:
        print(f"WeWorkRemotely scrape error: {e}")
    return jobs


def scrape_github_jobs_alternative(keyword: str = "python") -> list[dict]:
    """Scrape Jobicy — free remote job board with public JSON."""
    jobs = []
    try:
        resp = requests.get(
            f"https://jobicy.com/api/v2/remote-jobs?count=20&tag={keyword}",
            headers=HEADERS, timeout=15
        )
        data = resp.json()
        for item in data.get("jobs", []):
            jobs.append({
                "source":      "Jobicy",
                "title":       item.get("jobTitle", ""),
                "company":     item.get("companyName", ""),
                "location":    item.get("jobGeo", "Remote"),
                "url":         item.get("url", ""),
                "description": item.get("jobExcerpt", "")[:1000],
            })
        time.sleep(1)
    except Exception as e:
        print(f"Jobicy scrape error: {e}")
    return jobs


def search_all_boards(keywords: list[str] = None) -> list[dict]:
    """Search all job boards for all your keywords."""
    if keywords is None:
        keywords = config.JOB_KEYWORDS

    all_jobs = []
    for kw in keywords[:4]:  # limit to avoid being too slow
        print(f"  Searching: {kw}")
        all_jobs.extend(scrape_remoteok(kw))
        all_jobs.extend(scrape_weworkremotely(kw))
        all_jobs.extend(scrape_github_jobs_alternative(kw))
        time.sleep(1)

    # Deduplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        if job["url"] and job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)
    return unique


# ── AI-powered matching and cover letter generation ───────────────────────────

USER_PROFILE = f"""
Name: {config.YOUR_NAME}
Role: Computer Engineering student (graduating 2026), Software Dev Intern at Benpos Systems
Skills: Python, C, C++, TensorFlow, Edge Impulse, HuggingFace, OpenCV, SQLite, Git, GitHub
Interests: Cybersecurity, Reverse Engineering, Embedded Systems, AI/ML
Certifications: Google Cloud Cybersecurity, Cisco Junior Cybersecurity Analyst, Machining NC II
Projects: Plastic bottle segregation system (TensorFlow/Edge Impulse), AI Document Organizer (HuggingFace/OpenCV)
Location: Ozamiz City, Philippines — open to remote work
"""


def score_job(job: dict) -> int:
    """Ask Ollama to score how well this job matches Jasper's profile (0-100)."""
    system = """You are a job matcher. Score how well the job matches the candidate.
Return ONLY a JSON object: {"score": 75, "reason": "short reason"}
Score: 0=no match, 50=partial match, 80+=strong match, 100=perfect match."""

    prompt = f"""Candidate profile:
{USER_PROFILE}

Job listing:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job.get('description', '')[:800]}

Score this match."""

    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ], "stream": False, "options": {"temperature": 0.1, "num_predict": 100}},
            timeout=60,
        )
        raw = resp.json()["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return int(data.get("score", 0))
    except Exception:
        return 0


def generate_cover_letter(job: dict) -> str:
    """Generate a tailored cover letter for a specific job using AI."""
    system = f"""You are a professional cover letter writer.
Write compelling, specific cover letters that match the job requirements.
The candidate is {config.YOUR_NAME}."""

    # Try to load CV content
    cv_text = ""
    cv_path = Path(config.CV_FILE_PATH)
    if cv_path.exists():
        try:
            if cv_path.suffix == ".docx":
                import docx
                doc = docx.Document(cv_path)
                cv_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            elif cv_path.suffix in (".txt", ".md"):
                cv_text = cv_path.read_text(encoding="utf-8")
        except Exception:
            pass

    prompt = f"""Write a professional cover letter for this job application.

CANDIDATE:
{USER_PROFILE}
{f'Additional CV details:{chr(10)}{cv_text[:1000]}' if cv_text else ''}

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Description: {job.get('description', '')[:800]}

Write a 3-paragraph cover letter:
1. Opening: express enthusiasm, mention the specific role
2. Middle: highlight 2-3 most relevant skills/projects from the candidate's background
3. Closing: call to action, thank them

Address it to "Hiring Manager" if no name is available.
Sign as {config.YOUR_NAME} ({config.YOUR_EMAIL} | {config.YOUR_PHONE})"""

    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ], "stream": False, "options": {"temperature": 0.5, "num_predict": 700}},
            timeout=120,
        )
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[Cover letter generation failed: {e}]"


def score_and_save_jobs(jobs: list[dict]) -> list[dict]:
    """Score all found jobs and save to database."""
    init_job_db()
    scored = []
    for job in jobs:
        score = score_job(job)
        job["match_score"] = score
        scored.append(job)
        time.sleep(0.5)
    save_jobs(scored)
    return sorted(scored, key=lambda x: x["match_score"], reverse=True)


def apply_to_job(job_id: int, contact_email: str) -> dict:
    """
    Apply to a job by emailing the cover letter + CV.
    Returns result dict.
    """
    from agents.email_agent import send_email

    con = sqlite3.connect(JOB_DB_PATH)
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    if not row:
        return {"success": False, "error": "Job not found"}

    cols = ["id", "source", "title", "company", "location", "url",
            "description", "date_found", "match_score", "cover_letter",
            "applied", "applied_at", "notes"]
    job = dict(zip(cols, row))

    cover = job.get("cover_letter") or generate_cover_letter(job)
    subject = f"Application for {job['title']} — {config.YOUR_NAME}"
    body = f"""{cover}

---
Attached: CV / Resume
LinkedIn: {config.YOUR_LINKEDIN}
GitHub: {config.YOUR_GITHUB}
"""
    result = send_email(contact_email, subject, body)
    if result["success"]:
        mark_applied(job_id, cover)
    return result
