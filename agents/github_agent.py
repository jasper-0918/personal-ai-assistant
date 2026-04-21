"""
agents/github_agent.py — GitHub Portfolio Agent
Creates repos, pushes AI-generated code, writes READMEs,
and maintains your GitHub portfolio automatically.
Uses PyGithub — free with a personal access token.
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import base64
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

GITHUB_API = "https://api.github.com"


def _gh_headers() -> dict:
    return {
        "Authorization": f"token {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": config.GITHUB_USERNAME,
    }


def _call_ollama(prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": messages,
                  "stream": False, "options": {"temperature": 0.4, "num_predict": 1500}},
            timeout=180,
        )
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[Ollama error: {e}]"


# ── GitHub API wrappers ───────────────────────────────────────────────────────

def get_profile() -> dict:
    """Fetch your GitHub profile info."""
    resp = requests.get(f"{GITHUB_API}/user", headers=_gh_headers(), timeout=10)
    if resp.status_code == 200:
        return resp.json()
    return {"error": f"GitHub API error {resp.status_code}: {resp.text}"}


def list_repos(limit: int = 20) -> list[dict]:
    """List your GitHub repositories."""
    resp = requests.get(
        f"{GITHUB_API}/user/repos",
        headers=_gh_headers(),
        params={"per_page": limit, "sort": "updated"},
        timeout=10
    )
    if resp.status_code == 200:
        return [{"name": r["name"], "description": r.get("description", ""),
                 "url": r["html_url"], "stars": r["stargazers_count"],
                 "language": r.get("language", ""), "updated": r["updated_at"]}
                for r in resp.json()]
    return [{"error": f"GitHub API error: {resp.status_code}"}]


def create_repo(name: str, description: str = "", private: bool = False) -> dict:
    """Create a new GitHub repository."""
    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": True,
        "gitignore_template": "Python",
    }
    resp = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=_gh_headers(),
        json=payload,
        timeout=15
    )
    if resp.status_code == 201:
        data = resp.json()
        return {"success": True, "url": data["html_url"], "clone_url": data["clone_url"], "name": name}
    return {"success": False, "error": resp.json().get("message", resp.text)}


def push_file(repo_name: str, file_path: str, content: str, commit_msg: str = "Add file") -> dict:
    """Push a file to a GitHub repository (creates or updates)."""
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Check if file already exists (to get its SHA for update)
    url = f"{GITHUB_API}/repos/{config.GITHUB_USERNAME}/{repo_name}/contents/{file_path}"
    check = requests.get(url, headers=_gh_headers(), timeout=10)
    sha = check.json().get("sha") if check.status_code == 200 else None

    payload = {"message": commit_msg, "content": encoded}
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
    if resp.status_code in (200, 201):
        return {"success": True, "url": f"https://github.com/{config.GITHUB_USERNAME}/{repo_name}/blob/main/{file_path}"}
    return {"success": False, "error": resp.json().get("message", resp.text)}


def update_repo_description(repo_name: str, description: str, topics: list[str] = None) -> dict:
    """Update a repo's description and topics."""
    resp = requests.patch(
        f"{GITHUB_API}/repos/{config.GITHUB_USERNAME}/{repo_name}",
        headers=_gh_headers(),
        json={"description": description},
        timeout=10
    )
    if topics:
        requests.put(
            f"{GITHUB_API}/repos/{config.GITHUB_USERNAME}/{repo_name}/topics",
            headers={**_gh_headers(), "Accept": "application/vnd.github.mercy-preview+json"},
            json={"names": topics[:20]},
            timeout=10
        )
    return {"success": resp.status_code == 200}


# ── AI-powered content generation ────────────────────────────────────────────

def generate_readme(project_name: str, description: str, tech_stack: list[str],
                    features: list[str] = None) -> str:
    """Generate a professional README.md using AI."""
    system = """You are a technical writer. Generate professional GitHub README files.
Use proper Markdown formatting with badges, sections, and code examples where appropriate."""

    prompt = f"""Generate a professional README.md for this project:

Project: {project_name}
Description: {description}
Tech stack: {', '.join(tech_stack)}
Key features: {', '.join(features or ['See description'])}
Author: {config.YOUR_NAME} ({config.YOUR_GITHUB})

Include these sections:
- Project title with a brief tagline
- Badges (Python version, license)
- Overview (2-3 sentences)
- Features (bullet list)
- Tech stack
- Installation steps
- Usage example
- Author section with links

Make it professional and engaging."""

    return _call_ollama(prompt, system)


def generate_project_code(project_idea: str, language: str = "Python") -> dict:
    """Ask AI to generate a complete small project."""
    system = f"""You are {config.YOUR_NAME}, a Computer Engineering student skilled in Python, C, ML, and cybersecurity.
Generate complete, working, well-commented code projects.
Return ONLY valid JSON:
{{
  "project_name": "snake_case_name",
  "description": "one sentence description",
  "files": [
    {{"path": "main.py", "content": "# full file content here"}},
    {{"path": "requirements.txt", "content": "package1\\npackage2"}}
  ],
  "tech_stack": ["Python", "requests"],
  "features": ["feature 1", "feature 2"],
  "run_command": "python main.py"
}}"""

    prompt = f"""Create a complete, working {language} project for:
{project_idea}

The project should be:
- Actually runnable (not just skeleton code)
- Well-commented
- Under 300 lines total
- Demonstrate real technical skill
- Appropriate for a Computer Engineering student's GitHub portfolio

Return valid JSON only, no markdown fences."""

    raw = _call_ollama(prompt, system)
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception as e:
        return {"error": f"JSON parse failed: {e}", "raw": raw[:500]}


def create_and_push_project(project_idea: str, private: bool = False) -> dict:
    """
    Full pipeline: generate project → create repo → push all files → generate README.
    Returns summary dict with repo URL.
    """
    print(f"  Generating project code for: {project_idea}")
    project = generate_project_code(project_idea)
    if "error" in project:
        return project

    repo_name = project.get("project_name", "new-project").replace("_", "-").lower()
    description = project.get("description", project_idea[:100])

    print(f"  Creating repo: {repo_name}")
    repo_result = create_repo(repo_name, description, private=private)
    if not repo_result.get("success"):
        return repo_result

    import time
    time.sleep(2)  # wait for GitHub to initialize repo

    # Push each generated file
    pushed = []
    for file_info in project.get("files", []):
        result = push_file(
            repo_name,
            file_info["path"],
            file_info["content"],
            f"Add {file_info['path']}"
        )
        pushed.append({"file": file_info["path"], "success": result.get("success", False)})
        time.sleep(0.5)

    # Generate and push README
    print("  Generating README...")
    readme = generate_readme(
        repo_name, description,
        project.get("tech_stack", ["Python"]),
        project.get("features", [])
    )
    push_file(repo_name, "README.md", readme, "Add README")

    # Update topics
    update_repo_description(
        repo_name, description,
        topics=[t.lower() for t in project.get("tech_stack", [])]
    )

    return {
        "success": True,
        "repo_name": repo_name,
        "repo_url": repo_result["url"],
        "files_pushed": pushed,
        "run_command": project.get("run_command", ""),
        "description": description,
    }


def get_portfolio_summary() -> dict:
    """Get a summary of your GitHub portfolio for job applications."""
    repos = list_repos(limit=30)
    profile = get_profile()

    languages = {}
    for repo in repos:
        lang = repo.get("language", "")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    return {
        "username":    config.GITHUB_USERNAME,
        "profile_url": f"https://github.com/{config.GITHUB_USERNAME}",
        "public_repos": profile.get("public_repos", len(repos)),
        "followers":   profile.get("followers", 0),
        "top_languages": sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5],
        "recent_repos": repos[:5],
    }
