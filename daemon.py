"""
daemon.py — Always-Running Background Guardian
Keeps your AI alive, learning, and growing 24/7 on your own computer.

Runs in the background and does three things:
  1. Watches your knowledge/ folder for new files → auto-ingests them
  2. Crawls professional sources on a schedule (configurable)
  3. Logs all activity to daemon.log

Start it:
    python daemon.py

Stop it:
    Press Ctrl+C, or close the terminal window.

To run it on startup → see GUIDE.md for Windows/Linux instructions.
"""

import os
import sys
import time
import logging
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DAEMON] %(message)s",
    handlers=[
        logging.FileHandler("daemon.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ── Settings ──────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR = Path("./knowledge")
CHECK_INTERVAL_SECONDS = 30          # how often to check for new files
CRAWL_INTERVAL_HOURS   = 24          # how often to auto-crawl (set 0 to disable)
CRAWL_ON_STARTUP       = False       # set True to crawl when daemon first starts

WATCHED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".json"}

# Track files already ingested by their hash
_seen_hashes: set[str] = set()
_last_crawl: float = 0.0


def file_hash(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def run(cmd: list[str]) -> bool:
    """Run a subprocess and log its output."""
    try:
        result = subprocess.run(
            [sys.executable] + cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent),
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                log.info(f"  {line}")
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                log.warning(f"  STDERR: {line}")
        return result.returncode == 0
    except Exception as e:
        log.error(f"Failed to run {cmd}: {e}")
        return False


def scan_knowledge_folder() -> list[Path]:
    """Return all knowledge files not yet seen."""
    new_files = []
    if not KNOWLEDGE_DIR.exists():
        KNOWLEDGE_DIR.mkdir(exist_ok=True)
        return []
    for path in KNOWLEDGE_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in WATCHED_EXTENSIONS:
            h = file_hash(path)
            if h and h not in _seen_hashes:
                new_files.append(path)
                _seen_hashes.add(h)
    return new_files


def ingest_new_files(new_files: list[Path]):
    """Run the ingest script to process new knowledge files."""
    if not new_files:
        return
    log.info(f"📥 {len(new_files)} new file(s) detected:")
    for f in new_files:
        log.info(f"   → {f.name}")
    log.info("Running ingest.py...")
    ok = run(["ingest.py"])
    if ok:
        log.info("✅ Ingest complete.")
    else:
        log.warning("⚠️  Ingest had errors — check above.")


def maybe_crawl():
    """Crawl professional sources if enough time has passed."""
    global _last_crawl
    if CRAWL_INTERVAL_HOURS <= 0:
        return
    hours_since = (time.time() - _last_crawl) / 3600
    if hours_since >= CRAWL_INTERVAL_HOURS:
        log.info(f"🕷️  Auto-crawl triggered (last crawl {hours_since:.1f}h ago)...")
        ok = run(["crawler.py"])
        if ok:
            log.info("✅ Crawl complete.")
        else:
            log.warning("⚠️  Crawl had errors — check above.")
        _last_crawl = time.time()


def seed_initial_hashes():
    """On startup, mark all existing files as already seen (don't re-ingest)."""
    if not KNOWLEDGE_DIR.exists():
        return
    for path in KNOWLEDGE_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in WATCHED_EXTENSIONS:
            h = file_hash(path)
            if h:
                _seen_hashes.add(h)
    log.info(f"📚 Found {len(_seen_hashes)} existing knowledge file(s) — watching for new ones.")


def main():
    global _last_crawl
    log.info("=" * 50)
    log.info("🧠 Jasper AI Daemon — starting up")
    log.info(f"   Watching: {KNOWLEDGE_DIR.resolve()}")
    log.info(f"   Crawl interval: {CRAWL_INTERVAL_HOURS}h")
    log.info(f"   Check interval: {CHECK_INTERVAL_SECONDS}s")
    log.info("=" * 50)

    seed_initial_hashes()

    if CRAWL_ON_STARTUP:
        log.info("🕷️  Running startup crawl...")
        run(["crawler.py"])
        _last_crawl = time.time()
    else:
        # Set last crawl to now so it won't crawl until CRAWL_INTERVAL_HOURS later
        _last_crawl = time.time()

    log.info("✅ Daemon is running. Drop files into knowledge/ to auto-ingest them.")
    log.info("   Press Ctrl+C to stop.\n")

    try:
        while True:
            # 1. Check for new knowledge files
            new_files = scan_knowledge_folder()
            if new_files:
                ingest_new_files(new_files)

            # 2. Auto-crawl on schedule
            maybe_crawl()

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log.info("\n🛑 Daemon stopped by user.")


if __name__ == "__main__":
    main()
