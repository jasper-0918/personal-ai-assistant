"""
agents/email_agent.py — Email Virtual Assistant
Read, summarize, draft, and send emails via Gmail.
Uses IMAP/SMTP — free, no third-party API needed.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import imaplib
import smtplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587


def _call_ollama(prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "messages": messages,
                  "stream": False, "options": {"temperature": 0.4, "num_predict": 800}},
            timeout=120,
        )
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[AI error: {e}]"


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="replace")
    return ""


def fetch_inbox(limit: int = 10, folder: str = "INBOX") -> list[dict]:
    """Fetch recent emails from Gmail inbox."""
    emails = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASS)
        mail.select(folder)
        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        recent_ids = list(reversed(ids[-limit:] if len(ids) > limit else ids))
        for eid in recent_ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            body = _get_body(msg)
            emails.append({
                "id":      eid.decode(),
                "subject": _decode_header_value(msg.get("Subject", "(no subject)")),
                "sender":  _decode_header_value(msg.get("From", "")),
                "date":    msg.get("Date", ""),
                "body":    body,
                "preview": body[:300].replace("\n", " ").strip(),
            })
        mail.logout()
    except imaplib.IMAP4.error as e:
        return [{"error": f"Gmail login failed: {e}. Check config.py"}]
    except Exception as e:
        return [{"error": str(e)}]
    return emails


def summarize_email(email_dict: dict) -> str:
    """Summarize an email and suggest a reply using AI."""
    system = f"You are {config.YOUR_NAME}'s email assistant. Summarize emails concisely."
    prompt = f"""Email from: {email_dict['sender']}
Subject: {email_dict['subject']}
Body:
{email_dict['body'][:1500]}

1. Summarize in 2-3 sentences.
2. Does it need a reply? If yes, suggest what to say briefly."""
    return _call_ollama(prompt, system)


def draft_reply(email_dict: dict, instructions: str = "") -> str:
    """Draft a professional reply to an email."""
    system = f"""You are {config.YOUR_NAME}. Write professional email replies.
Sign off as {config.YOUR_NAME} ({config.YOUR_EMAIL} | {config.YOUR_PHONE})"""
    prompt = f"""Original email:
From: {email_dict['sender']}
Subject: {email_dict['subject']}
Body: {email_dict['body'][:1500]}

Write a professional reply.
{f'Instruction: {instructions}' if instructions else ''}
Reply body only — no Subject line."""
    return _call_ollama(prompt, system)


def draft_new_email(to: str, about: str) -> dict:
    """Draft a new email from scratch using AI."""
    system = f"""You are {config.YOUR_NAME}. Write professional emails.
Return ONLY valid JSON: {{"subject": "...", "body": "..."}} — no markdown."""
    prompt = f"Write a professional email to: {to}\nAbout: {about}\nSign as {config.YOUR_NAME}"
    raw = _call_ollama(prompt, system).replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except Exception:
        lines = raw.split("\n")
        return {"subject": lines[0].replace("Subject:", "").strip() if lines else about,
                "body": "\n".join(lines[1:]).strip() if len(lines) > 1 else raw}


def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email via Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.GMAIL_ADDRESS
        msg["To"]      = to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASS)
            server.sendmail(config.GMAIL_ADDRESS, to, msg.as_string())
        return {"success": True}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "Authentication failed. Check GMAIL_APP_PASS in config.py"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_for_job_replies(keywords: list[str] = None) -> list[dict]:
    """Scan inbox for job application replies."""
    if keywords is None:
        keywords = ["interview", "application", "position", "opportunity",
                    "offer", "shortlisted", "assessment", "hiring"]
    emails = fetch_inbox(limit=50)
    return [em for em in emails if "error" not in em and
            any(kw.lower() in (em["subject"] + em["preview"]).lower() for kw in keywords)]
