"""
config.py — Your personal settings. Fill this in once.
Everything runs locally on your machine — nothing is sent to any cloud service.

SETUP CHECKLIST:
  [ ] 1. Fill in your Gmail address and app password
  [ ] 2. Fill in your GitHub token and username
  [ ] 3. Fill in your personal profile details
  [ ] 4. Put your CV file in the my_cv/ folder and update CV_FILE_PATH
  [ ] 5. Update JOB_KEYWORDS to match your target roles
"""

# ── AI Model (Ollama — runs locally, no API key needed) ───────────────────────
# Install Ollama from https://ollama.com then run: ollama pull qwen2.5:14b
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:14b"   # or: llama3.1:8b, mistral:7b, phi3:mini


# ── Gmail ─────────────────────────────────────────────────────────────────────
# DO NOT use your regular Gmail password here.
# You need a Gmail App Password (free, takes 2 minutes):
#   1. Go to myaccount.google.com → Security
#   2. Enable 2-Step Verification (if not already on)
#   3. Go to myaccount.google.com/apppasswords
#   4. Select "Mail" and your device → click Generate
#   5. Copy the 16-character code and paste it below
GMAIL_ADDRESS  = "you@gmail.com"           # ← your Gmail address
GMAIL_APP_PASS = "xxxx xxxx xxxx xxxx"     # ← your 16-char app password


# ── GitHub ────────────────────────────────────────────────────────────────────
# Get a free Personal Access Token:
#   1. github.com → Settings (top right avatar)
#   2. Developer settings → Personal access tokens → Tokens (classic)
#   3. Generate new token → check: repo, read:user, workflow
#   4. Copy and paste the token below (starts with ghp_)
GITHUB_TOKEN    = "ghp_your_token_here"    # ← paste your token
GITHUB_USERNAME = "your-github-username"   # ← your GitHub username


# ── Your Personal Profile ─────────────────────────────────────────────────────
# Used by the job agent (cover letters) and email agent (signatures).
YOUR_NAME     = "Your Full Name"
YOUR_EMAIL    = "you@gmail.com"
YOUR_PHONE    = "+1 234 567 8900"
YOUR_LOCATION = "Your City, Country"
YOUR_GITHUB   = f"github.com/{GITHUB_USERNAME}"
YOUR_LINKEDIN = "linkedin.com/in/your-profile"

# Path to your CV file (drop it in the my_cv/ folder)
# Supported formats: .docx, .pdf, .txt
CV_FILE_PATH  = "./my_cv/my_cv.docx"


# ── Job Search Preferences ────────────────────────────────────────────────────
# The job agent will search for these keywords across free job boards.
# Edit to match your target roles.
JOB_KEYWORDS = [
    "Software Engineer",
    "Python Developer",
    "Backend Developer",
    "Data Engineer",
    "Machine Learning Engineer",
]

# Preferred job locations (used to filter/rank results)
JOB_LOCATIONS = ["Remote", "Work from home", "Your City"]

# Minimum AI match score (0–100) to show a job in recommendations.
# Jobs below this score are still saved but ranked lower.
JOB_MIN_SCORE = 60


# ── Your Skills & Background ──────────────────────────────────────────────────
# The AI uses this to write cover letters and match jobs.
# Be specific — the more detail you add, the better the cover letters.
YOUR_SKILLS = """
Programming: Python, JavaScript, SQL
Frameworks: FastAPI, React, TensorFlow
Tools: Git, Docker, Linux
Interests: [your interests here]
Experience: [brief summary of your background]
"""


# ── Database Paths (no need to change these) ─────────────────────────────────
CHROMA_DB_PATH   = "./chroma_db"
COLLECTION_NAME  = "va_knowledge"
CORRECTIONS_NAME = "va_corrections"
SKILL_DB_PATH    = "./skill_data.db"
