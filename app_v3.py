"""
Jasper AI Pro — v3 Virtual Assistant
Tabs: Chat | Email | Jobs | GitHub | Projects | Practice | Dashboard | Knowledge
100% local, 100% free, no credit card.
"""

import sys
import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Jasper AI", page_icon="🧠", layout="wide")

# ── Imports ───────────────────────────────────────────────────────────────────
from rag import RAGAssistant
from practice import PracticeEngine, DOMAINS, DIFFICULTY_PROMPTS
from feedback import (record_thumbs_up, record_correction,
                      get_feedback_stats, get_corrections, init_feedback_db)

init_feedback_db()

@st.cache_resource
def load_rag():
    return RAGAssistant()

@st.cache_resource
def load_practice():
    return PracticeEngine()

rag      = load_rag()
practice = load_practice()

# ── Navigation ────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "💬 Chat",
    "📧 Email",
    "💼 Jobs",
    "🐙 GitHub",
    "🛠️ Projects",
    "🎯 Practice",
    "📊 Dashboard",
    "📚 Knowledge",
])
(tab_chat, tab_email, tab_jobs, tab_github,
 tab_projects, tab_practice, tab_dashboard, tab_knowledge) = tabs


# ════════════════════════════════════════════════════════════════════════
# TAB 1: CHAT
# ════════════════════════════════════════════════════════════════════════
with tab_chat:
    col_main, col_side = st.columns([3, 1])
    with col_side:
        st.markdown("**Settings**")
        model = st.selectbox("Model", [
            "qwen2.5:14b", "llama3.2:3b", "llama3.1:8b", "mistral:7b", "phi3:mini"
        ], key="chat_model")
        top_k = st.slider("Knowledge chunks", 1, 8, 3, key="chat_topk")
        temp  = st.slider("Creativity", 0.0, 1.0, 0.3, 0.1, key="chat_temp")
        st.markdown("---")
        fb = get_feedback_stats()
        st.metric("AI accuracy", f"{fb['accuracy_pct']}%")
        st.metric("Corrections stored", fb["corrections_stored"])
        if st.button("Clear chat"):
            st.session_state.chat_messages = []
            st.rerun()
        import requests as req
        try:
            req.get("http://localhost:11434", timeout=2)
            st.success("Ollama running")
        except Exception:
            st.error("Ollama offline")

    with col_main:
        st.title("Jasper AI Chat")
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        if "last_qa" not in st.session_state:
            st.session_state.last_qa = None

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask anything..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    corrections = get_corrections(prompt, top_k=2)
                    response, sources = rag.query(
                        question=prompt,
                        chat_history=st.session_state.chat_messages[:-1],
                        top_k=top_k, temperature=temp, model=model,
                        extra_context=corrections,
                    )
                st.markdown(response)
                if corrections + sources:
                    with st.expander("Sources", expanded=False):
                        for s in corrections + sources:
                            badge = "CORRECTION" if s.get("is_correction") else "doc"
                            st.markdown(f"`{badge}` {s['source']} — *{s['preview']}*")
                st.markdown("---")
                c1, c2, _ = st.columns([1, 1, 5])
                if c1.button("👍", key=f"up_{len(st.session_state.chat_messages)}"):
                    record_thumbs_up(prompt, response)
                    st.success("Noted!")
                if c2.button("👎", key=f"dn_{len(st.session_state.chat_messages)}"):
                    st.session_state.last_qa = (prompt, response)
            st.session_state.chat_messages.append({"role": "assistant", "content": response})

        if st.session_state.last_qa:
            corr = st.text_area("What's the correct answer?")
            if st.button("Submit correction", type="primary"):
                q, a = st.session_state.last_qa
                record_correction(q, a, corr)
                st.session_state.last_qa = None
                st.success("Correction stored!")
                st.rerun()


# ════════════════════════════════════════════════════════════════════════
# TAB 2: EMAIL
# ════════════════════════════════════════════════════════════════════════
with tab_email:
    st.title("Email Assistant")
    st.caption("Read, draft, and send emails with AI help — powered by Gmail.")

    import config
    if config.GMAIL_ADDRESS == "your.email@gmail.com":
        st.warning("Set your GMAIL_ADDRESS and GMAIL_APP_PASS in config.py first.")
    else:
        from agents.email_agent import (fetch_inbox, summarize_email,
                                        draft_reply, draft_new_email,
                                        send_email, check_for_job_replies)

        email_tab1, email_tab2, email_tab3 = st.tabs(["Inbox", "Compose", "Job replies"])

        with email_tab1:
            col1, col2 = st.columns([1, 2])
            with col1:
                limit = st.number_input("Emails to fetch", 5, 50, 10)
                if st.button("Fetch inbox", type="primary"):
                    with st.spinner("Connecting to Gmail..."):
                        st.session_state.emails = fetch_inbox(limit=limit)

            if "emails" in st.session_state:
                emails = st.session_state.emails
                if emails and "error" in emails[0]:
                    st.error(emails[0]["error"])
                else:
                    with col1:
                        st.markdown(f"**{len(emails)} emails**")
                        for i, em in enumerate(emails):
                            if st.button(
                                f"{em['subject'][:35]}...\n{em['sender'][:25]}",
                                key=f"em_{i}", use_container_width=True
                            ):
                                st.session_state.selected_email = em

                    with col2:
                        if "selected_email" in st.session_state:
                            em = st.session_state.selected_email
                            st.markdown(f"**From:** {em['sender']}")
                            st.markdown(f"**Subject:** {em['subject']}")
                            st.markdown(f"**Date:** {em['date']}")
                            st.markdown("---")
                            st.text_area("Body", em["body"][:2000], height=200)

                            if st.button("Summarize with AI"):
                                with st.spinner("Summarizing..."):
                                    summary = summarize_email(em)
                                st.info(summary)

                            st.markdown("---")
                            instructions = st.text_input(
                                "Reply instructions (optional)",
                                placeholder="e.g. decline politely, ask for more details"
                            )
                            if st.button("Draft AI reply"):
                                with st.spinner("Drafting..."):
                                    draft = draft_reply(em, instructions)
                                st.session_state.draft_reply = draft

                            if "draft_reply" in st.session_state:
                                reply_text = st.text_area(
                                    "Edit before sending:",
                                    st.session_state.draft_reply, height=200
                                )
                                send_to = st.text_input("Send to:", em["sender"].split("<")[-1].strip(">"))
                                if st.button("Send reply", type="primary"):
                                    with st.spinner("Sending..."):
                                        result = send_email(send_to, f"Re: {em['subject']}", reply_text)
                                    if result["success"]:
                                        st.success("Email sent!")
                                        del st.session_state.draft_reply
                                    else:
                                        st.error(result["error"])

        with email_tab2:
            st.markdown("### Compose new email")
            to_addr = st.text_input("To:")
            about   = st.text_area("What's this email about?",
                                   placeholder="e.g. Follow up on my job application at CompanyX")
            if st.button("Generate email with AI", type="primary"):
                with st.spinner("Writing email..."):
                    from agents.email_agent import draft_new_email
                    draft = draft_new_email(to_addr, about)
                    st.session_state.new_subject = draft.get("subject", "")
                    st.session_state.new_body    = draft.get("body", "")

            if "new_subject" in st.session_state:
                subject  = st.text_input("Subject:", st.session_state.new_subject)
                body     = st.text_area("Body:", st.session_state.new_body, height=300)
                if st.button("Send email", type="primary"):
                    with st.spinner("Sending..."):
                        result = send_email(to_addr, subject, body)
                    if result["success"]:
                        st.success(f"Sent to {to_addr}!")
                        del st.session_state.new_subject, st.session_state.new_body
                    else:
                        st.error(result["error"])

        with email_tab3:
            if st.button("Scan for job replies", type="primary"):
                with st.spinner("Scanning inbox for job-related emails..."):
                    replies = check_for_job_replies()
                if replies:
                    st.success(f"Found {len(replies)} job-related emails!")
                    for em in replies:
                        with st.expander(f"{em['subject']} — {em['sender'][:30]}"):
                            st.write(em["preview"])
                else:
                    st.info("No job-related emails found in recent inbox.")


# ════════════════════════════════════════════════════════════════════════
# TAB 3: JOBS
# ════════════════════════════════════════════════════════════════════════
with tab_jobs:
    st.title("Job Search & Apply")
    st.caption("Searches free job boards, scores matches, generates cover letters, and applies for you.")

    from agents.job_agent import (search_all_boards, score_and_save_jobs,
                                  get_jobs, generate_cover_letter,
                                  apply_to_job, init_job_db)
    init_job_db()

    job_tab1, job_tab2, job_tab3 = st.tabs(["Search", "Matches", "Applied"])

    with job_tab1:
        st.markdown("### Search job boards")
        st.info("Searches: RemoteOK, We Work Remotely, Jobicy — all free, no API key")

        keywords_input = st.text_area(
            "Keywords (one per line)",
            "\n".join(config.JOB_KEYWORDS[:5]),
            height=120
        )
        if st.button("Search & score jobs", type="primary"):
            keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
            with st.spinner("Searching job boards and scoring matches... (takes 2-3 min)"):
                jobs = search_all_boards(keywords)
                if jobs:
                    scored = score_and_save_jobs(jobs)
                    st.success(f"Found {len(scored)} jobs. Top matches saved to database.")
                    st.session_state.scored_jobs = scored[:20]
                else:
                    st.warning("No jobs found. Check your internet connection.")

        if "scored_jobs" in st.session_state:
            st.markdown("### Top matches just found:")
            for job in st.session_state.scored_jobs[:10]:
                score = job.get("match_score", 0)
                color = "green" if score >= 70 else ("orange" if score >= 50 else "gray")
                st.markdown(
                    f":{color}[**{score}%**] **{job['title']}** at {job['company']} "
                    f"({job['location']}) — [{job['source']}]({job.get('url', '#')})"
                )

    with job_tab2:
        st.markdown("### Your job matches")
        min_score = st.slider("Minimum match score", 0, 100, 50)
        jobs = get_jobs(applied=False, min_score=min_score, limit=30)

        if not jobs:
            st.info("No matches yet — run a search first.")
        else:
            st.markdown(f"**{len(jobs)} jobs found** with score >= {min_score}%")
            for job in jobs:
                with st.expander(
                    f"[{job['match_score']}%] {job['title']} — {job['company']} ({job['location']})"
                ):
                    st.markdown(f"**Source:** {job['source']}")
                    st.markdown(f"**URL:** {job.get('url', 'N/A')}")
                    st.markdown(f"**Description:** {job.get('description', '')[:500]}")
                    st.markdown("---")

                    if st.button("Generate cover letter", key=f"cl_{job['id']}"):
                        with st.spinner("Writing cover letter..."):
                            cl = generate_cover_letter(job)
                            st.session_state[f"cl_{job['id']}"] = cl

                    if f"cl_{job['id']}" in st.session_state:
                        cl_text = st.text_area(
                            "Cover letter (edit before sending):",
                            st.session_state[f"cl_{job['id']}"],
                            height=300,
                            key=f"clt_{job['id']}"
                        )
                        contact = st.text_input(
                            "Company contact email:",
                            key=f"ce_{job['id']}",
                            placeholder="hr@company.com"
                        )
                        if contact and st.button("Apply now", type="primary", key=f"apply_{job['id']}"):
                            with st.spinner("Sending application..."):
                                result = apply_to_job(job["id"], contact)
                            if result.get("success"):
                                st.success("Application sent!")
                            else:
                                st.error(result.get("error", "Failed"))

    with job_tab3:
        applied = get_jobs(applied=True, limit=50)
        if not applied:
            st.info("No applications sent yet.")
        else:
            st.markdown(f"**{len(applied)} applications sent**")
            for job in applied:
                st.markdown(
                    f"- **{job['title']}** at {job['company']} — applied {job.get('applied_at', '')[:10]}"
                )


# ════════════════════════════════════════════════════════════════════════
# TAB 4: GITHUB
# ════════════════════════════════════════════════════════════════════════
with tab_github:
    st.title("GitHub Portfolio")
    st.caption("Manage your repos, push code, and grow your portfolio.")

    if config.GITHUB_TOKEN == "ghp_yourtoken":
        st.warning("Set your GITHUB_TOKEN and GITHUB_USERNAME in config.py first.")
    else:
        from agents.github_agent import (get_profile, list_repos, create_repo,
                                          push_file, generate_readme,
                                          generate_project_code, create_and_push_project,
                                          get_portfolio_summary)

        gh_tab1, gh_tab2, gh_tab3 = st.tabs(["Portfolio", "Create repo", "Generate project"])

        with gh_tab1:
            if st.button("Load my GitHub profile", type="primary"):
                with st.spinner("Fetching from GitHub..."):
                    summary = get_portfolio_summary()
                    st.session_state.gh_summary = summary

            if "gh_summary" in st.session_state:
                s = st.session_state.gh_summary
                c1, c2, c3 = st.columns(3)
                c1.metric("Public repos", s.get("public_repos", 0))
                c2.metric("Followers", s.get("followers", 0))
                c3.metric("Profile", f"@{s.get('username', '')}")

                st.markdown("---")
                st.markdown("**Top languages:**")
                for lang, count in s.get("top_languages", []):
                    st.markdown(f"- {lang}: {count} repos")

                st.markdown("**Recent repositories:**")
                for repo in s.get("recent_repos", []):
                    st.markdown(
                        f"- [{repo['name']}]({repo['url']}) — "
                        f"{repo.get('language', '')} — {repo.get('stars', 0)} stars"
                    )

        with gh_tab2:
            st.markdown("### Create a new repository")
            repo_name = st.text_input("Repo name (no spaces):", placeholder="my-cool-project")
            repo_desc = st.text_input("Description:")
            private   = st.checkbox("Private repo")

            if st.button("Create repo", type="primary") and repo_name:
                with st.spinner(f"Creating {repo_name}..."):
                    result = create_repo(repo_name, repo_desc, private)
                if result.get("success"):
                    st.success(f"Created! View at: {result['url']}")
                else:
                    st.error(result.get("error", "Failed"))

            st.markdown("---")
            st.markdown("### Push a file to a repo")
            push_repo = st.text_input("Repo name:")
            push_path = st.text_input("File path:", placeholder="src/main.py")
            push_content = st.text_area("File content:", height=200)
            push_msg = st.text_input("Commit message:", "Add file via Jasper AI")

            if st.button("Push file", type="primary") and push_repo and push_path:
                with st.spinner("Pushing..."):
                    result = push_file(push_repo, push_path, push_content, push_msg)
                if result.get("success"):
                    st.success(f"Pushed! View at: {result['url']}")
                else:
                    st.error(result.get("error", "Failed"))

        with gh_tab3:
            st.markdown("### Generate a project and push to GitHub")
            idea = st.text_area("Describe your project idea:",
                                placeholder="A Python CLI tool that monitors CPU temperature and alerts when too hot")
            private_proj = st.checkbox("Make repo private", key="proj_private")

            if st.button("Generate & push to GitHub", type="primary") and idea:
                with st.spinner("Generating project and pushing to GitHub... (2-5 min)"):
                    result = create_and_push_project(idea, private=private_proj)
                if result.get("success"):
                    st.success(f"Project live at: {result['repo_url']}")
                    st.markdown(f"**Run with:** `{result.get('run_command', '')}`")
                    st.markdown("**Files pushed:**")
                    for f in result.get("files_pushed", []):
                        emoji = "ok" if f["success"] else "fail"
                        st.markdown(f"- `{f['file']}` — {emoji}")
                else:
                    st.error(result.get("error", "Failed"))


# ════════════════════════════════════════════════════════════════════════
# TAB 5: PROJECTS
# ════════════════════════════════════════════════════════════════════════
with tab_projects:
    st.title("Project Builder")
    st.caption("AI generates a working project, runs it, and creates a demo video.")

    from agents.project_agent import full_pipeline, PROJECTS_DIR, VIDEOS_DIR

    proj_idea = st.text_area(
        "What project should the AI build?",
        placeholder="A port scanner in Python that checks if common ports are open on a given host",
        height=100
    )
    push_gh = st.checkbox("Also push to GitHub after building")

    if st.button("Build project + demo video", type="primary") and proj_idea:
        with st.spinner("Building... this takes 3-5 minutes. AI is coding for you."):
            result = full_pipeline(proj_idea, push_to_github=push_gh)

        if "error" in result:
            st.error(result["error"])
        else:
            st.success("Project built!")

            st.markdown("**Steps completed:**")
            for step in result.get("steps", []):
                st.markdown(f"- {step}")

            proj = result.get("project", {})
            if proj:
                st.markdown(f"**Name:** `{proj.get('project_name', '')}`")
                st.markdown(f"**Run:** `{proj.get('run_command', '')}`")

            run = result.get("run", {})
            if run:
                status = "Ran successfully" if run["success"] else "Run failed"
                st.markdown(f"**Status:** {status}")
                if run.get("stdout"):
                    with st.expander("Output"):
                        st.code(run["stdout"][:1000])

            video = result.get("video", {})
            if video.get("success"):
                st.success(f"Demo video created: `{video['path']}`")
                try:
                    st.video(video["path"])
                except Exception:
                    st.info(f"Video saved to: {video['path']}")
            elif video.get("error"):
                st.warning(f"Video not created: {video['error']}")
                st.info("Install moviepy: pip install moviepy Pillow")

    # Show existing projects
    st.markdown("---")
    st.markdown("### Existing projects")
    if PROJECTS_DIR.exists():
        projects = [p for p in PROJECTS_DIR.iterdir() if p.is_dir()]
        if projects:
            for proj_path in sorted(projects, reverse=True)[:10]:
                files = list(proj_path.glob("**/*.py"))
                st.markdown(f"- **{proj_path.name}** — {len(files)} Python file(s)")
        else:
            st.info("No projects built yet.")

    st.markdown("### Demo videos")
    if VIDEOS_DIR.exists():
        videos = list(VIDEOS_DIR.glob("*.mp4"))
        if videos:
            selected = st.selectbox("Play a video:", [v.name for v in videos])
            if selected:
                st.video(str(VIDEOS_DIR / selected))
        else:
            st.info("No videos yet — build a project to generate one.")


# ════════════════════════════════════════════════════════════════════════
# TAB 6: PRACTICE
# ════════════════════════════════════════════════════════════════════════
with tab_practice:
    st.title("Practice Mode")
    if "current_question" not in st.session_state:
        st.session_state.current_question = None
    if "grading_result" not in st.session_state:
        st.session_state.grading_result = None

    p1, p2, p3 = st.columns(3)
    domain     = p1.selectbox("Domain", list(DOMAINS.keys()), key="pd",
                               format_func=lambda x: x.replace("_", " ").title())
    difficulty = p2.selectbox("Difficulty", list(DIFFICULTY_PROMPTS.keys()), index=1, key="pdiff")

    if p3.button("Generate question", type="primary", use_container_width=True):
        with st.spinner("Generating..."):
            st.session_state.current_question = practice.generate_question(domain, difficulty)
            st.session_state.grading_result = None

    if st.session_state.current_question:
        q = st.session_state.current_question
        st.markdown("---")
        st.markdown(f"**Domain:** `{q.get('domain','').replace('_',' ').title()}` · **Difficulty:** `{q.get('difficulty', difficulty).title()}`")
        st.markdown(f"### {q['question']}")
        if q.get("type") == "multiple_choice" and q.get("options"):
            answer = st.radio("Choose:", q["options"], key="mc")
            user_answer = answer[0] if answer else ""
        else:
            user_answer = st.text_area("Your answer:", height=150, key="oe")

        if st.button("Submit", type="primary"):
            if user_answer.strip():
                with st.spinner("Grading..."):
                    st.session_state.grading_result = practice.grade_answer(q, user_answer)

        if st.session_state.grading_result:
            r = st.session_state.grading_result
            score = r.get("score", 0)
            fn = st.success if score >= 80 else (st.warning if score >= 50 else st.error)
            fn(f"{r.get('verdict','').title()} — {score}/100")
            st.markdown(f"**Feedback:** {r.get('feedback','')}")
            st.markdown(f"**Correct answer:** {r.get('correct_answer','')}")
            for g in r.get("gaps", []):
                st.markdown(f"- Study: {g}")


# ════════════════════════════════════════════════════════════════════════
# TAB 7: DASHBOARD
# ════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.title("Skill Dashboard")
    scores = practice.get_skill_scores()
    gaps   = practice.get_top_gaps(limit=8)
    recent = practice.get_recent_sessions(limit=10)

    if not scores:
        st.info("Complete practice sessions to see scores.")
    else:
        cols = st.columns(3)
        for i, (dom, data) in enumerate(scores.items()):
            with cols[i % 3]:
                lvl = data["level"]
                clr = {"Expert":"purple","Professional":"blue","Intermediate":"orange",
                       "Beginner":"orange","Novice":"red"}.get(lvl, "gray")
                st.metric(dom.replace("_"," ").title(), f"{data['avg']}% · {lvl}",
                          f"{data['correct']}/{data['attempts']} correct")
        st.markdown("---")
        st.markdown("### Progress to professional (75%+)")
        for dom, data in scores.items():
            st.progress(min(data["avg"]/75.0, 1.0),
                        text=f"{dom.replace('_',' ').title()}: {data['avg']}%")

    if gaps:
        st.markdown("---")
        st.markdown("### Top knowledge gaps")
        for g in gaps:
            st.markdown(f"- **{g['domain'].replace('_',' ').title()}**: {g['topic']} (×{g['frequency']})")

    if recent:
        st.markdown("---")
        st.markdown("### Recent sessions")
        for s in recent:
            e = "pass" if s["score"] >= 80 else ("warn" if s["score"] >= 50 else "fail")
            st.markdown(f"`{s['ts'][:16]}` {s['domain']} ({s['difficulty']}) — **{s['score']}/100** — *{s['question']}*")


# ════════════════════════════════════════════════════════════════════════
# TAB 8: KNOWLEDGE
# ════════════════════════════════════════════════════════════════════════
with tab_knowledge:
    st.title("Knowledge Manager")
    import chromadb as _chromadb
    _client = _chromadb.PersistentClient(path="./chroma_db")
    try:
        main_count = _client.get_collection("jasper_knowledge").count()
    except Exception:
        main_count = 0
    try:
        corr_count = _client.get_collection("jasper_corrections").count()
    except Exception:
        corr_count = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Knowledge chunks", main_count)
    k2.metric("Corrections", corr_count)
    k3.metric("Total", main_count + corr_count)

    st.markdown("---")
    url_input = st.text_input("Crawl a URL:")
    if st.button("Crawl URL") and url_input:
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        import subprocess
        result = subprocess.run(["python", "crawler.py", "--url", url_input.strip()],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace", env=env)
        st.code(result.stdout or result.stderr)

    st.markdown("---")
    uploaded = st.file_uploader("Upload a file (.txt, .md, .pdf, .docx, .json)",
                                type=["txt","md","pdf","docx","json"])
    if uploaded and st.button("Ingest file"):
        import tempfile, subprocess
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded.name}",
                                         dir="./knowledge") as tmp:
            tmp.write(uploaded.read())
        env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(["python", "ingest.py"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", env=env)
        st.success(f"{uploaded.name} ingested!") if result.returncode == 0 else st.error(result.stderr)

    st.markdown("---")
    if st.button("Rebuild database"):
        import shutil, subprocess
        shutil.rmtree("./chroma_db", ignore_errors=True)
        result = subprocess.run(["python", "ingest.py"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0:
            st.success("Rebuilt!")
            st.cache_resource.clear()
            st.rerun()
