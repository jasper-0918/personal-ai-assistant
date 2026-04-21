"""
Knowledge Crawler — Engine 1: Knowledge Scale
Auto-ingests professional-grade content from the web into your ChromaDB.

Usage:
    python crawler.py                     # crawl all configured sources
    python crawler.py --topic security    # crawl only security sources
    python crawler.py --url https://...   # crawl a specific URL

Run on a schedule (add to cron or Windows Task Scheduler):
    0 6 * * * cd /path/to/jasper_ai && python crawler.py
"""

import os
import re
import sys
import time
import hashlib
import argparse
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

import chromadb
from chromadb.utils import embedding_functions

# ── Optional imports (install only what you need) ─────────────────────────────
try:
    from bs4 import BeautifulSoup
    BS4 = True
except ImportError:
    BS4 = False
    print("⚠️  Install beautifulsoup4 for web scraping: pip install beautifulsoup4 requests")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YT = True
except ImportError:
    YT = False

try:
    import arxiv
    ARXIV = True
except ImportError:
    ARXIV = False

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "jasper_knowledge"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# ══ YOUR PROFESSIONAL KNOWLEDGE SOURCES ══════════════════════════════════════
# Add/remove URLs freely. Organized by your skill domains.
SOURCES = {
    "cybersecurity": [
        # PortSwigger Web Security Academy
        "https://portswigger.net/web-security/sql-injection",
        "https://portswigger.net/web-security/cross-site-scripting",
        "https://portswigger.net/web-security/authentication",
        "https://portswigger.net/web-security/access-control",
        # OWASP
        "https://owasp.org/www-project-top-ten/",
        # Cloudflare Learning Center
        "https://www.cloudflare.com/learning/security/what-is-a-cyberattack/",
        "https://www.cloudflare.com/learning/ddos/what-is-a-ddos-attack/",
    ],
    "reverse_engineering": [
        "https://malwareunicorn.org/workshops/re101.html",
        "https://ctf101.org/reverse-engineering/overview/",
        "https://ctf101.org/binary-exploitation/overview/",
    ],
    "machine_learning": [
        "https://developers.google.com/machine-learning/crash-course/ml-intro",
        "https://huggingface.co/learn/nlp-course/chapter1/1",
        "https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html",
    ],
    "embedded_systems": [
        "https://interrupt.memfault.com/blog/cortex-m-fault-debug",
        "https://www.freertos.org/Documentation/00-Overview",
    ],
    "python_advanced": [
        "https://docs.python.org/3/howto/descriptor.html",
        "https://realpython.com/python-concurrency/",
        "https://realpython.com/python-async-await/",
    ],
}

# YouTube video IDs to ingest (transcripts only, free)
YOUTUBE_IDS = {
    "cybersecurity": [
        "qiQR5rTSshw",   # John Hammond - CTF walkthroughs
        "3Kq1MIfTWCE",   # NetworkChuck - Ethical Hacking
    ],
    "machine_learning": [
        "aircAruvnKk",   # 3Blue1Brown - Neural Networks
        "IHZwWFHWa-w",   # 3Blue1Brown - Gradient Descent
    ],
}

# ArXiv paper IDs to ingest (free, open access)
ARXIV_PAPERS = [
    "1706.03762",    # Attention Is All You Need (Transformers)
    "2005.14165",    # Language Models are Few-Shot Learners (GPT-3)
    "2310.06825",    # Self-RAG (relevant to how this system works)
]


# ── Chunking ──────────────────────────────────────────────────────────────────
def chunk_text(text: str, source: str = "") -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    text = re.sub(r'\s+', ' ', text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if len(chunk) > 80:  # skip tiny fragments
            chunks.append({
                "text": chunk,
                "source": source,
                "crawled_at": datetime.now().isoformat(),
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def url_to_id(url: str, idx: int) -> str:
    """Create a stable, unique ID for a URL chunk."""
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"web_{h}_{idx}"


# ── Web scraping ──────────────────────────────────────────────────────────────
def scrape_url(url: str, timeout: int = 15) -> str:
    """Scrape clean text content from a URL."""
    if not BS4:
        print("  ⚠️  beautifulsoup4 not installed — skipping web scraping")
        return ""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JasperAI-Crawler/1.0; personal use)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  Failed to fetch {url}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "form", "button", "iframe", "noscript"]):
        tag.decompose()

    # Try to find main content
    main = (
        soup.find("main") or
        soup.find("article") or
        soup.find(class_=re.compile(r"(content|article|post|body)", re.I)) or
        soup.find("body")
    )
    if not main:
        return ""

    text = main.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── YouTube transcripts ───────────────────────────────────────────────────────
def get_youtube_transcript(video_id: str) -> str:
    """Get transcript from a YouTube video (free, no API key needed)."""
    if not YT:
        print("  ⚠️  Install youtube-transcript-api: pip install youtube-transcript-api")
        return ""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(seg["text"] for seg in transcript)
    except Exception as e:
        print(f"  ⚠️  Could not get transcript for {video_id}: {e}")
        return ""


# ── ArXiv papers ──────────────────────────────────────────────────────────────
def get_arxiv_paper(paper_id: str) -> tuple[str, str]:
    """Fetch title + abstract from an ArXiv paper (free API)."""
    if not ARXIV:
        print("  ⚠️  Install arxiv: pip install arxiv")
        return "", ""
    try:
        search = arxiv.Search(id_list=[paper_id])
        paper = next(search.results())
        text = f"Title: {paper.title}\n\nAuthors: {', '.join(str(a) for a in paper.authors)}\n\nAbstract: {paper.summary}"
        return text, paper.title
    except Exception as e:
        print(f"  ⚠️  Could not fetch ArXiv {paper_id}: {e}")
        return "", ""


# ── ChromaDB connection ───────────────────────────────────────────────────────
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(collection, chunks: list[dict], id_prefix: str):
    """Upsert a list of chunks into ChromaDB."""
    if not chunks:
        return 0
    ids = [f"{id_prefix}_{i}" for i in range(len(chunks))]
    docs = [c["text"] for c in chunks]
    metas = [{k: v for k, v in c.items() if k != "text"} for c in chunks]
    collection.upsert(documents=docs, ids=ids, metadatas=metas)
    return len(chunks)


# ── Main crawler ──────────────────────────────────────────────────────────────
def crawl(topic_filter: str | None = None, single_url: str | None = None):
    print("🕷️  Jasper AI — Knowledge Crawler")
    print("=" * 45)
    collection = get_collection()
    total = 0

    # Single URL mode
    if single_url:
        print(f"\n📄 Crawling: {single_url}")
        text = scrape_url(single_url)
        if text:
            chunks = chunk_text(text, source=single_url)
            h = hashlib.md5(single_url.encode()).hexdigest()[:8]
            n = upsert_chunks(collection, chunks, f"custom_{h}")
            print(f"   ✅ {n} chunks stored")
            total += n
        print(f"\n✅ Done. {total} chunks stored. Total in DB: {collection.count()}")
        return

    # Web sources
    sources_to_crawl = SOURCES
    if topic_filter:
        sources_to_crawl = {k: v for k, v in SOURCES.items() if k == topic_filter}
        if not sources_to_crawl:
            print(f"⚠️  No topic '{topic_filter}'. Available: {list(SOURCES.keys())}")
            return

    for topic, urls in sources_to_crawl.items():
        print(f"\n📚 Topic: {topic}")
        for url in urls:
            print(f"  → {url[:70]}...")
            text = scrape_url(url)
            if text:
                chunks = chunk_text(text, source=f"{topic}:{url}")
                h = hashlib.md5(url.encode()).hexdigest()[:8]
                n = upsert_chunks(collection, chunks, f"web_{topic}_{h}")
                print(f"     ✅ {n} chunks")
                total += n
            time.sleep(1.5)  # be polite to servers

    # YouTube transcripts
    if not topic_filter or topic_filter in YOUTUBE_IDS:
        yt_sources = YOUTUBE_IDS if not topic_filter else {topic_filter: YOUTUBE_IDS.get(topic_filter, [])}
        for topic, vids in yt_sources.items():
            for vid_id in vids:
                print(f"\n  🎬 YouTube [{topic}]: {vid_id}")
                text = get_youtube_transcript(vid_id)
                if text:
                    chunks = chunk_text(text, source=f"youtube:{vid_id}")
                    n = upsert_chunks(collection, chunks, f"yt_{vid_id}")
                    print(f"     ✅ {n} chunks")
                    total += n

    # ArXiv papers
    if not topic_filter:
        print(f"\n📄 ArXiv papers")
        for paper_id in ARXIV_PAPERS:
            print(f"  → {paper_id}")
            text, title = get_arxiv_paper(paper_id)
            if text:
                chunks = chunk_text(text, source=f"arxiv:{paper_id} — {title}")
                n = upsert_chunks(collection, chunks, f"arxiv_{paper_id.replace('.','_')}")
                print(f"     ✅ {n} chunks — {title[:50]}")
                total += n

    print("\n" + "=" * 45)
    print(f"✅ Crawl complete. {total} new chunks stored.")
    print(f"📦 Total in DB: {collection.count()} chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jasper AI Knowledge Crawler")
    parser.add_argument("--topic", type=str, help="Crawl only a specific topic")
    parser.add_argument("--url", type=str, help="Crawl a specific URL")
    args = parser.parse_args()
    crawl(topic_filter=args.topic, single_url=args.url)
