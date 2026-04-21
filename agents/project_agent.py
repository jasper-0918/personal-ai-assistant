"""
agents/project_agent.py — Project Builder & Demo Video Agent
Generates working code projects, runs them, takes screenshots,
and creates demo videos — all locally, all free.
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
import shutil
import subprocess
import tempfile
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PROJECTS_DIR = Path("./projects")
VIDEOS_DIR   = Path("./demo_videos")


def _call_ollama(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": messages,
                  "stream": False,
                  "options": {"temperature": 0.3, "num_predict": max_tokens}},
            timeout=300,
        )
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[Ollama error: {e}]"


def setup_dirs():
    PROJECTS_DIR.mkdir(exist_ok=True)
    VIDEOS_DIR.mkdir(exist_ok=True)


def generate_project(idea: str, language: str = "Python") -> dict:
    """
    Use Ollama to generate a complete runnable project.
    Returns a dict with all file contents.
    """
    system = f"""You are {config.YOUR_NAME}, a skilled Computer Engineering student.
Generate complete, runnable {language} projects.
Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "project_name": "snake_case_name",
  "description": "what this project does",
  "files": [
    {{"path": "main.py", "content": "# complete file content"}},
    {{"path": "requirements.txt", "content": "requests\\n"}}
  ],
  "run_command": "python main.py",
  "expected_output": "what you expect to see when it runs",
  "tech_stack": ["Python", "requests"],
  "features": ["feature 1", "feature 2"]
}}"""

    prompt = f"""Create a complete, working {language} project:
Idea: {idea}

Requirements:
- Must actually run without errors
- Well-commented code showing engineering skill
- Total code under 250 lines
- Suitable for a GitHub portfolio
- Include a requirements.txt if external packages are needed

Return ONLY valid JSON."""

    raw = _call_ollama(prompt, system, max_tokens=3000)
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Try to extract JSON if there's extra text
    if "{" in raw:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        raw = raw[start:end]

    try:
        return json.loads(raw)
    except Exception as e:
        return {"error": f"Could not parse project JSON: {e}", "raw": raw[:300]}


def write_project_to_disk(project: dict) -> Path:
    """Write all project files to a folder under projects/."""
    setup_dirs()
    name = project.get("project_name", f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    proj_dir = PROJECTS_DIR / name
    proj_dir.mkdir(parents=True, exist_ok=True)

    for file_info in project.get("files", []):
        file_path = proj_dir / file_info["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_info["content"], encoding="utf-8")

    return proj_dir


def install_requirements(proj_dir: Path) -> dict:
    """Install pip requirements if requirements.txt exists."""
    req_file = proj_dir / "requirements.txt"
    if not req_file.exists():
        return {"success": True, "message": "No requirements.txt"}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120
        )
        if result.returncode == 0:
            return {"success": True}
        return {"success": False, "error": result.stderr[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_project(proj_dir: Path, run_command: str = "python main.py", timeout: int = 30) -> dict:
    """
    Run the project and capture its output.
    Returns stdout, stderr, and return code.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            run_command.split(),
            cwd=str(proj_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timed out", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def create_demo_video(
    project: dict,
    proj_dir: Path,
    run_result: dict,
    output_path: Path = None,
) -> dict:
    """
    Create a demo video for the project.
    Uses moviepy + PIL to generate a professional slide-based video.
    No screen recording needed — creates a clean animated presentation.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
    except ImportError:
        return {
            "success": False,
            "error": "Install moviepy and Pillow: pip install moviepy Pillow",
        }

    setup_dirs()
    if output_path is None:
        output_path = VIDEOS_DIR / f"{project.get('project_name', 'demo')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    W, H = 1280, 720
    FPS  = 24
    BG   = (18, 18, 28)       # dark background
    ACC  = (120, 100, 220)     # accent purple
    WHITE= (240, 240, 245)
    GRAY = (140, 140, 160)
    GREEN= (80, 200, 120)

    def make_frame(title: str, lines: list[tuple], duration: float = 3.0) -> ImageClip:
        """Create a single slide as an ImageClip."""
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # Top accent bar
        draw.rectangle([0, 0, W, 6], fill=ACC)

        # Title
        try:
            font_title = ImageFont.truetype("arial.ttf", 52)
            font_body  = ImageFont.truetype("arial.ttf", 30)
            font_code  = ImageFont.truetype("consola.ttf", 26)
            font_small = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font_title = font_body = font_code = font_small = ImageFont.load_default()

        draw.text((80, 60), title, font=font_title, fill=WHITE)
        draw.rectangle([80, 130, 80 + len(title) * 26, 134], fill=ACC)

        y = 180
        for text, style in lines:
            if style == "code":
                draw.rectangle([70, y - 6, W - 70, y + 44], fill=(30, 30, 45))
                draw.text((90, y), text, font=font_code, fill=GREEN)
                y += 58
            elif style == "bullet":
                draw.ellipse([74, y + 10, 84, y + 20], fill=ACC)
                draw.text((100, y), text, font=font_body, fill=WHITE)
                y += 50
            elif style == "gray":
                draw.text((80, y), text, font=font_small, fill=GRAY)
                y += 36
            else:
                draw.text((80, y), text, font=font_body, fill=WHITE)
                y += 50

        # Bottom watermark
        draw.text((W - 340, H - 40), f"github.com/{config.GITHUB_USERNAME}", font=font_small, fill=GRAY)

        return ImageClip(img).set_duration(duration)

    # ── Build slides ──────────────────────────────────────────────────────────
    clips = []

    # Slide 1: Title
    clips.append(make_frame(
        project.get("project_name", "Project").replace("_", " ").title(),
        [
            (project.get("description", ""), "normal"),
            ("", "normal"),
            (f"by {config.YOUR_NAME}", "gray"),
            (f"Stack: {', '.join(project.get('tech_stack', ['Python']))}", "gray"),
        ],
        duration=4.0
    ))

    # Slide 2: Features
    features = project.get("features", [])
    if features:
        feature_lines = [(f[:70], "bullet") for f in features[:6]]
        clips.append(make_frame("Features", feature_lines, duration=4.0))

    # Slide 3: Code preview (first file)
    files = project.get("files", [])
    if files:
        code_lines = files[0]["content"].split("\n")[:12]
        code_slide_lines = []
        for line in code_lines:
            code_slide_lines.append((line[:75] if line else "", "code"))
        clips.append(make_frame(
            f"Code — {files[0]['path']}",
            code_slide_lines[:10],
            duration=5.0
        ))

    # Slide 4: Output
    stdout = run_result.get("stdout", "").strip()
    output_lines = stdout.split("\n")[:10] if stdout else ["(no output)"]
    out_slide = [(line[:75], "code") for line in output_lines[:8]]
    status = "Run successful" if run_result.get("success") else "Output:"
    clips.append(make_frame(status, out_slide, duration=5.0))

    # Slide 5: Call to action
    clips.append(make_frame(
        "View on GitHub",
        [
            (f"github.com/{config.GITHUB_USERNAME}", "bullet"),
            (config.YOUR_EMAIL, "bullet"),
            (config.YOUR_LINKEDIN, "bullet"),
            ("", "normal"),
            ("Open to opportunities — remote & Philippines", "gray"),
        ],
        duration=4.0
    ))

    # ── Concatenate and export ────────────────────────────────────────────────
    try:
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio=False,
            verbose=False,
            logger=None,
        )
        return {"success": True, "path": str(output_path), "duration": final.duration}
    except Exception as e:
        return {"success": False, "error": str(e)}


def full_pipeline(idea: str, push_to_github: bool = False) -> dict:
    """
    Complete pipeline: generate → write → install → run → make video → optionally push to GitHub.
    """
    results = {"idea": idea, "steps": []}

    # 1. Generate
    print("  Generating project...")
    project = generate_project(idea)
    if "error" in project:
        return {"error": project["error"]}
    results["project"] = project
    results["steps"].append("Generated project code")

    # 2. Write to disk
    proj_dir = write_project_to_disk(project)
    results["proj_dir"] = str(proj_dir)
    results["steps"].append(f"Written to {proj_dir}")

    # 3. Install requirements
    print("  Installing requirements...")
    install_result = install_requirements(proj_dir)
    results["install"] = install_result
    results["steps"].append(f"Install: {'OK' if install_result['success'] else install_result.get('error', '')}")

    # 4. Run
    print("  Running project...")
    run_cmd = project.get("run_command", "python main.py")
    run_result = run_project(proj_dir, run_cmd)
    results["run"] = run_result
    results["steps"].append(f"Run: {'success' if run_result['success'] else 'failed'}")

    # 5. Create demo video
    print("  Creating demo video...")
    video_result = create_demo_video(project, proj_dir, run_result)
    results["video"] = video_result
    if video_result.get("success"):
        results["steps"].append(f"Video created: {video_result['path']}")
    else:
        results["steps"].append(f"Video failed: {video_result.get('error', '')}")

    # 6. Push to GitHub (optional)
    if push_to_github:
        print("  Pushing to GitHub...")
        from agents.github_agent import create_and_push_project
        gh_result = create_and_push_project(idea)
        results["github"] = gh_result
        results["steps"].append(f"GitHub: {gh_result.get('repo_url', gh_result.get('error', ''))}")

    return results
