"""Render the Thai stock summary JSON into email files for the Gmail-connector path.

No secrets, no SMTP, no network. Given a summary JSON it writes, next to it:
    <stem>.html         -> use as create_draft htmlBody
    <stem>.txt          -> use as create_draft body (plain-text alternative)
    <stem>.subject.txt  -> use as create_draft subject

Then prints an ASCII-safe JSON line with those paths and the recipient hint, so
it never crashes on a Windows cp1252 console. The /daily-stocks command reads the
three files back (UTF-8) and creates the Gmail draft via the connector.

Usage:
    python render_email.py summaries/2026-06-16.json
"""

import json
import os
import sys

from email_render import build_html, build_plain_text, subject_for


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_email.py <path-to-summary.json>", file=sys.stderr)
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
        sys.exit(1)

    stem = os.path.splitext(summary_path)[0]
    html_path = stem + ".html"
    text_path = stem + ".txt"
    subject_path = stem + ".subject.txt"

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(data))
    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write(build_plain_text(data))
    with open(subject_path, "w", encoding="utf-8") as fh:
        fh.write(subject_for(data))

    # ASCII-safe so a Windows console can always print it. The actual Thai text
    # lives in the UTF-8 files above; read those back to build the draft.
    out = {
        # EMAIL_TO is the natural recipient; fall back to None so the caller decides.
        "to": os.environ.get("EMAIL_TO"),
        "subject_path": subject_path,
        "html_path": html_path,
        "text_path": text_path,
    }
    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()
