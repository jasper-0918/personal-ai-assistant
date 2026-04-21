# Personal AI Virtual Assistant

A fully local, privacy-first AI virtual assistant that runs entirely on your own computer. No subscriptions, no cloud APIs, no credit card — just your machine and open-source tools.

Built to act as a second version of you: it knows your background, speaks in your voice, manages your email, searches and applies to jobs, maintains your GitHub portfolio, builds and demos projects, and continuously grows smarter the more you use it.

---

## What It Does

### Chat — Your AI Self
Talk to an AI that knows who you are. Feed it your CV, notes, project docs, and Q&A pairs. It answers as you, in your voice, using your actual knowledge as context. Correct wrong answers and it permanently remembers the correction for next time.

### Email Assistant
Connects to your Gmail inbox. Reads and summarizes emails with AI, drafts replies in your tone, sends emails, and automatically scans for job interview replies.

### Job Search & Auto-Apply
Scrapes free job boards (RemoteOK, We Work Remotely, Jobicy) for your target roles. Scores every listing against your profile using AI (0–100 match score). Generates a tailored cover letter per job and sends the application by email — one click.

### GitHub Portfolio Manager
Lists and creates repositories, pushes AI-generated code, writes professional READMEs, and builds complete projects from a one-line description. Keeps your GitHub active and growing automatically.

### Project Builder + Demo Video
Describe a project idea in plain English. The AI writes the full working code, installs dependencies, runs it, and produces an MP4 demo video with slides showing the code, output, and your contact info — ready to attach to job applications or post to LinkedIn.

### Practice Engine
Generates quiz questions from your own knowledge base and grades your answers. Tracks your score per skill domain, identifies knowledge gaps, and shows your progress toward professional and expert level. The harder you practice, the smarter the AI becomes at answering questions in those areas.

### Knowledge Manager
Drop any file into the `knowledge/` folder and it ingests automatically within 30 seconds. Paste a URL and it scrapes and stores the content. A background daemon watches for new files 24/7 and auto-crawls professional sources on a schedule you control.

---

## Why This Is Different

Most AI assistants send your data to a cloud server. This one runs everything on your own CPU:

- **Private** — your emails, CV, and personal data never leave your machine
- **Free forever** — no monthly subscription, no API usage fees, no credit card
- **No rate limits** — run it all day, every day, without hitting quotas
- **Improves over time** — corrections, practice results, and new knowledge permanently improve it
- **Offline capable** — works without internet once set up (crawler and job search need internet)

---

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| AI brain | [Ollama](https://ollama.com) + qwen2.5:14b | Local LLM, no API key |
| Knowledge memory | [ChromaDB](https://www.trychroma.com) | Local vector database |
| Embeddings | [sentence-transformers](https://www.sbert.net) | Local semantic search |
| UI | [Streamlit](https://streamlit.io) | Browser-based chat interface |
| Email | Gmail IMAP/SMTP | Free with app password |
| GitHub | GitHub REST API | Free with personal token |
| Job boards | RemoteOK, We Work Remotely, Jobicy | Free public APIs/RSS |
| Demo videos | MoviePy + Pillow | Free, fully local |
| Background daemon | Python + watchdog | File watcher, auto-ingest |

---

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.11 (recommended — best compatibility with chromadb)
- 8 GB RAM minimum, 16 GB+ recommended
- 10 GB free disk space (for AI model + packages)
- Internet for initial setup and job searching

---

## Installation

### Step 1 — Install Python 3.11

Download from [python.org/downloads](https://www.python.org/downloads/).

> **Windows:** On the installer's first screen, check **"Add Python to PATH"** before clicking Install Now.

Verify:
```bash
python --version
# Should show: Python 3.11.x
```

### Step 2 — Install Ollama

Download from [ollama.com](https://ollama.com). Install with all defaults.

**Windows:** Ollama runs silently in your taskbar after install and starts automatically on boot.

**Mac/Linux:** Start it manually when needed:
```bash
ollama serve
```

### Step 3 — Download an AI model

```bash
ollama pull qwen2.5:14b
```

This downloads ~9 GB. It runs once and never needs to be downloaded again.

**Smaller/faster alternatives if you have less RAM:**

```bash
ollama pull llama3.1:8b   # ~5 GB, very good quality
ollama pull phi3:mini      # ~2.2 GB, fast on any machine
```

### Step 4 — Clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/personal-ai-assistant.git
cd personal-ai-assistant
```

### Step 5 — Set up the environment

**Windows:**
```bat
SETUP.bat
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python ingest.py
```

---

## Configuration

Open `config.py` in any text editor and fill in your details. This is the only file you need to edit.

```python
# Your name and contact info
YOUR_NAME     = "Your Full Name"
YOUR_EMAIL    = "you@gmail.com"
YOUR_PHONE    = "+1 234 567 8900"
YOUR_LOCATION = "Your City, Country"

# Gmail (for email agent)
GMAIL_ADDRESS  = "you@gmail.com"
GMAIL_APP_PASS = "xxxx xxxx xxxx xxxx"

# GitHub (for portfolio agent)
GITHUB_TOKEN    = "ghp_your_token_here"
GITHUB_USERNAME = "your-github-username"

# Job search
JOB_KEYWORDS = ["Software Engineer", "Python Developer", ...]
```

### Getting a Gmail App Password (free, 2 minutes)

1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
2. Enable **2-Step Verification** if not already on
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. App: **Mail** → Device: **Windows Computer** → Generate
5. Copy the 16-character code into `GMAIL_APP_PASS` in config.py

### Getting a GitHub Personal Access Token (free, 2 minutes)

1. Go to [github.com](https://github.com) → click your avatar → **Settings**
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token** → check: `repo`, `read:user`, `workflow`
4. Copy the token (starts with `ghp_`) into `GITHUB_TOKEN` in config.py

---

## Adding Your Knowledge

The AI only knows what you tell it. Put your files in the `knowledge/` folder:

| File type | What to put there |
|---|---|
| `.txt` or `.md` | Notes, study summaries, anything you've written |
| `.pdf` | Your CV, research papers, textbooks |
| `.docx` | Reports, assignments, documentation |
| `.json` | Q&A pairs — best for teaching how you think |

**JSON Q&A format** (the most powerful way to train it):

```json
[
  {
    "question": "How do you approach debugging a production issue?",
    "answer": "I start by reproducing the issue locally, then check logs for the first occurrence. I isolate the component, add instrumentation, and work outward from the failure point."
  }
]
```

Drop files in `knowledge/` and the daemon ingests them automatically within 30 seconds. Or run manually:

```bash
python ingest.py
```

**Edit `personality.txt`** to define your voice, background, and how the AI should present itself when asked personal questions.

---

## Running the App

**Windows:**
```bat
START.bat
```

**Mac/Linux:**
```bash
./start.sh
```

The app opens in your browser at **http://localhost:8501**

The first response after starting takes 10–30 seconds while the model loads into memory. Subsequent responses are faster.

---

## Auto-Start on Boot

### Windows — Task Scheduler

1. Press `Win + R` → type `taskschd.msc` → Enter
2. **Create Basic Task** → name it `Personal AI Assistant`
3. Trigger: **When the computer starts**
4. Action: **Start a program** → browse to `START.bat`
5. Check **Run whether user is logged on or not** → Finish

### Linux — systemd service

Create `/etc/systemd/system/personal-ai.service`:

```ini
[Unit]
Description=Personal AI Assistant
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/personal-ai-assistant
ExecStart=/path/to/personal-ai-assistant/venv/bin/python daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable personal-ai
sudo systemctl start personal-ai
```

---

## Project Structure

```
personal-ai-assistant/
│
├── config.py              # Your settings — fill this in
├── personality.txt        # Your AI's voice and identity
├── app_v3.py              # Main Streamlit app (8 tabs)
├── rag.py                 # RAG pipeline (retrieve → LLM → answer)
├── practice.py            # Practice engine + skill tracking
├── feedback.py            # Correction storage and retrieval
├── ingest.py              # Knowledge file ingestion
├── crawler.py             # Web crawler for auto-learning
├── daemon.py              # Background file watcher + scheduler
├── requirements.txt       # Python dependencies
│
├── agents/
│   ├── email_agent.py     # Gmail read/draft/send
│   ├── job_agent.py       # Job search + cover letters + apply
│   ├── github_agent.py    # Repo management + portfolio
│   └── project_agent.py   # Code generation + demo videos
│
├── knowledge/             # Drop your files here
├── my_cv/                 # Put your CV here
├── projects/              # Generated projects saved here
├── demo_videos/           # Generated demo videos saved here
└── chroma_db/             # Vector database (auto-created)
```

---

## Model Selection Guide

Change `OLLAMA_MODEL` in `config.py` to switch models. First pull it with `ollama pull MODEL_NAME`.

| Model | RAM needed | Speed | Best for |
|---|---|---|---|
| `qwen2.5:14b` | 9 GB | Medium | Best quality — recommended |
| `llama3.1:8b` | 5 GB | Fast | Great balance of speed/quality |
| `mistral:7b` | 4.5 GB | Fast | Strong reasoning |
| `phi3:mini` | 3 GB | Very fast | Low-RAM machines |
| `codellama:7b` | 4.5 GB | Medium | Best for code generation |

---

## Troubleshooting

**"Ollama is not running" in chat**
- Windows: look for the llama icon in your taskbar. Click it if not there.
- Mac/Linux: open a terminal and run `ollama serve`

**First response is very slow**
- Normal — the model loads into RAM on first use. Responses speed up after.
- Switch to a smaller model in `config.py` if consistently slow.

**Gmail login failed**
- Make sure you used an **App Password**, not your regular Gmail password.
- 2-Step Verification must be enabled on your account.
- Re-generate the app password if it's not working.

**"No module named X" error**
- Your virtual environment is not activated.
- Windows: run `venv\Scripts\activate` in the project folder.
- Mac/Linux: run `source venv/bin/activate`

**ChromaDB errors on startup**
- Delete the `chroma_db/` folder and run `python ingest.py` to rebuild.

**UnicodeEncodeError on Windows**
- Add `set PYTHONIOENCODING=utf-8` to your terminal before running, or set it as a system environment variable permanently.

---

## Privacy

All processing happens on your machine. The following never leaves your computer:
- Your emails and email credentials
- Your CV and personal documents
- Your chat history and corrections
- Your GitHub token
- Your knowledge base content

The only outbound connections are:
- Job board scraping (when you click "Search jobs")
- GitHub API calls (when you use the GitHub tab)
- Web crawler (when you crawl URLs for knowledge)
- Initial model download via Ollama (one time)

---

## License

MIT License — free to use, modify, and distribute.

---

## Contributing

Pull requests welcome. If you add a new agent or improve an existing one, please keep the same pattern: all credentials read from `config.py`, all AI calls go through Ollama, no external paid APIs.

---

*Built to be a true digital twin — one that grows smarter every day alongside you.*
