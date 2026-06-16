"""Send a structured Thai stock summary by email via Gmail SMTP.

The summary is a JSON file (see /daily-stocks) so the HTML can be rendered as
clean, scannable cards. All secrets come from environment / .env only.

Usage:
    python send_email.py summaries/2026-06-16.json
"""

import json
import os
import sys
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = ["EMAIL_FROM", "EMAIL_PASSWORD", "EMAIL_TO", "SMTP_HOST", "SMTP_PORT"]

THAI_DISCLAIMER = (
    "ข้อมูลนี้จัดทำเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำในการลงทุน "
    "การลงทุนมีความเสี่ยง ผู้ลงทุนควรศึกษาข้อมูลก่อนตัดสินใจลงทุน"
)

# sentiment key -> (Thai label, text color, background color)
SENTIMENT_STYLES = {
    "positive": ("ข่าวเชิงบวก", "#15803d", "#dcfce7"),
    "negative": ("ข่าวเชิงลบ", "#b91c1c", "#fee2e2"),
    "neutral": ("ข่าวเป็นกลาง", "#475569", "#e2e8f0"),
}

# Card accent + % pill colors for gainers vs losers.
GAINER_COLORS = {"accent": "#16a34a", "pill_bg": "#dcfce7", "pill_text": "#15803d", "arrow": "↑"}
LOSER_COLORS = {"accent": "#dc2626", "pill_bg": "#fee2e2", "pill_text": "#b91c1c", "arrow": "↓"}


def esc(text):
    """Minimal HTML escaping for text inserted into the template."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def fmt_price(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return esc(value)


def fmt_pct(value):
    try:
        v = float(value)
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"
    except (TypeError, ValueError):
        return esc(value)


def render_card(stock, colors):
    """Render one stock as an email-client-safe table card."""
    ticker = esc(stock.get("ticker", "?"))
    price = fmt_price(stock.get("price"))
    pct = fmt_pct(stock.get("pct_change"))
    summary = esc(stock.get("summary", ""))

    sentiment = stock.get("sentiment", "neutral")
    sent_label, sent_text, sent_bg = SENTIMENT_STYLES.get(
        sentiment, SENTIMENT_STYLES["neutral"]
    )

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:separate;border:1px solid #e5e7eb;border-left:4px solid {colors['accent']};border-radius:6px;background-color:#ffffff;margin-bottom:12px;">
  <tr>
    <td style="padding:14px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td align="left" style="font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:16px;font-weight:bold;color:#111827;">
            {ticker} <span style="font-weight:normal;color:#6b7280;font-size:14px;">{price}</span>
          </td>
          <td align="right">
            <table cellpadding="0" cellspacing="0" border="0"><tr>
              <td style="background-color:{colors['pill_bg']};color:{colors['pill_text']};font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:13px;font-weight:bold;padding:4px 10px;border-radius:12px;white-space:nowrap;">
                {colors['arrow']} {pct}
              </td>
            </tr></table>
          </td>
        </tr>
      </table>
      <p style="margin:10px 0 10px 0;font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:14px;line-height:1.6;color:#374151;">{summary}</p>
      <span style="font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:12px;color:{sent_text};background-color:{sent_bg};padding:3px 9px;border-radius:4px;">{sent_label}</span>
    </td>
  </tr>
</table>"""


def render_section_heading(text):
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
  <td style="padding:6px 0 10px 0;font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:15px;font-weight:bold;color:#0f172a;">{esc(text)}</td>
</tr></table>"""


def build_html(data):
    date_str = esc(data.get("date", datetime.now().strftime("%Y-%m-%d")))
    title = esc(data.get("title", "สรุปหุ้นเทค/ชิป/AI ประจำวัน"))
    tldr = esc(data.get("tldr", ""))
    gainers = data.get("gainers", []) or []
    losers = data.get("losers", []) or []
    overview = data.get("sector_overview", []) or []

    parts = []

    # Header
    parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0f172a;border-radius:8px 8px 0 0;">
  <tr><td style="padding:20px 22px;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
    <div style="font-size:19px;font-weight:bold;color:#ffffff;">📈 {title}</div>
    <div style="font-size:13px;color:#94a3b8;margin-top:4px;">{date_str}</div>
  </td></tr>
</table>""")

    # TL;DR bar
    if tldr:
        parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#fff7e6;border-left:4px solid #f59e0b;margin:16px 0;">
  <tr><td style="padding:12px 16px;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
    <div style="font-size:12px;font-weight:bold;color:#b45309;letter-spacing:0.5px;">วันนี้ที่ต้องรู้</div>
    <div style="font-size:14px;color:#92400e;line-height:1.55;margin-top:4px;">{tldr}</div>
  </td></tr>
</table>""")

    # Gainers
    if gainers:
        parts.append(render_section_heading("📈 หุ้นขึ้นเด่น"))
        for stock in gainers:
            parts.append(render_card(stock, GAINER_COLORS))

    # Losers
    if losers:
        parts.append(render_section_heading("📉 หุ้นลงเด่น"))
        for stock in losers:
            parts.append(render_card(stock, LOSER_COLORS))

    if not gainers and not losers:
        parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border:1px solid #e5e7eb;border-radius:6px;margin-bottom:12px;">
  <tr><td style="padding:14px 16px;font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:14px;color:#374151;line-height:1.6;">
    วันนี้ไม่มีหุ้นเข้าเกณฑ์เฝ้าระวัง (ราคาขยับ ≥ 3% หรือวอลุ่ม ≥ 1.5 เท่า)
  </td></tr>
</table>""")

    # Sector takeaways
    if overview:
        items = "".join(
            f'<li style="margin-bottom:8px;">{esc(point)}</li>' for point in overview
        )
        parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;border-radius:6px;margin:18px 0 8px 0;">
  <tr><td style="padding:16px 18px;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
    <div style="font-size:15px;font-weight:bold;color:#0f172a;margin-bottom:10px;">ภาพรวมกลุ่มเทค/ชิป/AI</div>
    <ul style="margin:0;padding-left:20px;font-size:14px;color:#334155;line-height:1.6;">{items}</ul>
  </td></tr>
</table>""")

    # Disclaimer footer
    parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
  <td style="padding:14px 4px 6px 4px;font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:11px;color:#94a3b8;line-height:1.5;border-top:1px solid #e5e7eb;">
    {esc(THAI_DISCLAIMER)}
  </td>
</tr></table>""")

    inner = "\n".join(parts)

    # Outer wrapper: gray page bg, centered 600px single column.
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f4f5f7;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f5f7;">
    <tr><td align="center" style="padding:20px 12px;">
      <table width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;">
        <tr><td>
{inner}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_plain_text(data):
    """Plain-text alternative built from the same structured data."""
    lines = []
    lines.append(f"{data.get('title', 'สรุปหุ้นเทค/ชิป/AI ประจำวัน')} {data.get('date', '')}".strip())
    if data.get("tldr"):
        lines.append("")
        lines.append(f"[วันนี้ที่ต้องรู้] {data['tldr']}")

    def dump(stocks, header):
        if not stocks:
            return
        lines.append("")
        lines.append(header)
        for s in stocks:
            label = SENTIMENT_STYLES.get(s.get("sentiment", "neutral"), SENTIMENT_STYLES["neutral"])[0]
            lines.append(f"- {s.get('ticker')} {fmt_price(s.get('price'))} ({fmt_pct(s.get('pct_change'))}) [{label}]")
            lines.append(f"  {s.get('summary', '')}")

    dump(data.get("gainers"), "== หุ้นขึ้นเด่น ==")
    dump(data.get("losers"), "== หุ้นลงเด่น ==")

    overview = data.get("sector_overview") or []
    if overview:
        lines.append("")
        lines.append("== ภาพรวมกลุ่มเทค/ชิป/AI ==")
        for point in overview:
            lines.append(f"- {point}")

    lines.append("")
    lines.append(THAI_DISCLAIMER)
    return "\n".join(lines)


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

    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    subject = f"📈 สรุปหุ้นเทค/ชิป/AI ประจำวัน {date_str}"

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
