"""Send a structured Thai stock summary by email via Gmail SMTP.

LEGACY / FALLBACK PATH. The daily cloud routine now creates a Gmail *draft* via
the Gmail connector (see /daily-stocks) because the sandbox blocks SMTP egress.
This script still works for local use or if smtp.gmail.com is allowlisted: it
reads the same JSON summary and renders the shared card template.

All secrets come from environment / .env only.

Usage:
    python send_email.py summaries/2026-06-16.json
"""

import json
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from email_render import build_html, build_plain_text, subject_for

load_dotenv()

REQUIRED_VARS = ["EMAIL_FROM", "EMAIL_PASSWORD", "EMAIL_TO", "SMTP_HOST", "SMTP_PORT"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_email.py <path-to-summary.json>", file=sys.stderr)
        sys.exit(1)

    summary_path = sys.argv[1]
    if not os.path.isfile(summary_path):
        print(f"Error: file not found: {summary_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(summary_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"Error: summary file is not valid JSON: {exc}", file=sys.stderr)
        print("The /daily-stocks command should write a JSON summary.", file=sys.stderr)
        sys.exit(1)

    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(
            "Error: missing required environment variables: " + ", ".join(missing),
            file=sys.stderr,
        )
        print("Set them in a .env file (see .env.example).", file=sys.stderr)
        sys.exit(1)

    email_from = os.environ["EMAIL_FROM"]
    email_password = os.environ["EMAIL_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])

    html_body = build_html(data)
    text_body = build_plain_text(data)

    subject = subject_for(data)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = [addr.strip() for addr in email_to.split(",") if addr.strip()]
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(email_from, email_password)
            server.sendmail(email_from, recipients, msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(email_from, email_password)
            server.sendmail(email_from, recipients, msg.as_string())

    # Guard against Windows consoles (cp1252) that can't encode emoji/Thai.
    try:
        print(f"Sent '{subject}' to {email_to}")
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(f"Sent '{subject}' to {email_to}".encode(enc, "replace").decode(enc))


if __name__ == "__main__":
    main()
