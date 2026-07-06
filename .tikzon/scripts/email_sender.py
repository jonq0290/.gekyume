"""
email_sender.py — Daily digest email for [.tikzon] arbitrage agent.

Sends an HTML email via Gmail SMTP using Jinja2 templating.
Falls back to plain text if template rendering fails.
Saves digest to disk if email delivery fails.
"""

import smtplib
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from loguru import logger

from scripts.config import cfg
from scripts.models import ScanResult, ProductOpportunity, ProductStatus
from scripts.sheets_manager import get_sheet_url

TEMPLATE_NAME = "email_digest.html"


# ─────────────────────────────────────────────
# Template rendering
# ─────────────────────────────────────────────

def render_html_digest(scan_result: ScanResult) -> str:
    """Render the HTML email digest using the Jinja2 template."""
    try:
        env = Environment(
            loader=FileSystemLoader(str(cfg.TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template(TEMPLATE_NAME)
        return template.render(
            scan_result=scan_result,
            recommendations=scan_result.recommendations,
            rejected=scan_result.rejected,
            sheet_url=get_sheet_url(),
            scan_date=datetime.now().strftime("%b %d, %Y"),
            scan_time=datetime.now().strftime("%I:%M %p"),
            operator_email=cfg.OPERATOR_EMAIL,
        )
    except TemplateNotFound:
        logger.warning(f"[Email] Template not found: {TEMPLATE_NAME}. Using plain text fallback.")
        return build_plain_text_digest(scan_result)
    except Exception as exc:
        logger.error(f"[Email] Template rendering error: {exc}")
        return build_plain_text_digest(scan_result)


def build_plain_text_digest(scan_result: ScanResult) -> str:
    """Plain text fallback if HTML template fails."""
    lines = [
        f"[.tikzon] Morning Digest — {datetime.now().strftime('%b %d, %Y')}",
        f"Scan completed: {scan_result.scan_date}",
        f"Total discovered: {scan_result.total_discovered} | "
        f"Recommended: {scan_result.total_recommended}",
        "",
    ]

    recs = scan_result.recommendations
    if not recs:
        lines.append("No qualifying products found today.")
    else:
        lines.append(f"TOP {min(5, len(recs))} OPPORTUNITIES")
        lines.append("=" * 60)
        for i, p in enumerate(recs[:5], 1):
            e = p.economics
            s = p.best_supplier
            lines += [
                f"\n{i}. {p.product_name} [{p.category.upper()}]",
                f"   TikTok: rank #{p.tiktok_metrics.shop_rank} | "
                f"{p.tiktok_metrics.video_views:,} views | "
                f"trend: {p.trend_velocity.value if p.trend_velocity else 'N/A'}",
                f"   Supplier: {s.supplier_name} ({s.platform}) | "
                f"Landed: ${s.landed_cost:.2f}" if s else "   No supplier",
                f"   Amazon: {p.amazon_status.num_sellers} sellers | "
                f"avg {p.amazon_status.avg_reviews} reviews",
                f"   Price: ${e.amazon_price:.2f} | FBA fees: ${e.fba_fees:.2f} | "
                f"Net profit: ${e.net_profit:.2f} | Margin: {e.margin_pct:.1f}%" if e else "",
                f"   Risk: {p.risk_class.value if p.risk_class else 'N/A'} | "
                f"Priority: {p.priority.value if p.priority else 'N/A'}",
            ]

    lines += [
        "",
        "─" * 60,
        f"Full data: {get_sheet_url()}",
        f"To approve: reply with 'APPROVE: [product name]'",
        f"Next scan: tomorrow at {cfg.SCAN_HOUR:02d}:{cfg.SCAN_MINUTE:02d} "
        f"{cfg.OPERATOR_TIMEZONE}",
    ]

    if scan_result.errors:
        lines += ["", "⚠️ ERRORS THIS SCAN:", *[f"  • {e}" for e in scan_result.errors]]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Subject line builder
# ─────────────────────────────────────────────

def build_subject(scan_result: ScanResult) -> str:
    date_str = datetime.now().strftime("%b %d, %Y")
    n = scan_result.total_recommended

    if scan_result.scan_status == "failed":
        return f"[.tikzon] ⚠️ ALERT — Scan failed ({date_str})"
    elif n == 0:
        return f"[.tikzon] No qualifying products today — {date_str}"
    else:
        return f"[.tikzon] Morning Digest — {date_str} | {n} {'opportunity' if n == 1 else 'opportunities'}"


# ─────────────────────────────────────────────
# Save digest to disk (fallback)
# ─────────────────────────────────────────────

def save_digest_to_disk(html_content: str, date_str: str) -> Path:
    """Save the digest HTML to memory/ in case email delivery fails."""
    path = cfg.MEMORY_DIR / f"digest_{date_str}.html"
    path.write_text(html_content, encoding="utf-8")
    logger.info(f"[Email] Digest saved to disk: {path}")
    return path


# ─────────────────────────────────────────────
# SMTP delivery
# ─────────────────────────────────────────────

def send_digest(scan_result: ScanResult) -> bool:
    """
    Build and send the morning digest email.
    Returns True on success, False on failure.
    On failure, saves digest to disk.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = build_subject(scan_result)
    html_body = render_html_digest(scan_result)
    plain_body = build_plain_text_digest(scan_result)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.SMTP_USER
    msg["To"] = cfg.OPERATOR_EMAIL
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"[Email] Connecting to {cfg.SMTP_HOST}:{cfg.SMTP_PORT}")
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.sendmail(cfg.SMTP_USER, cfg.OPERATOR_EMAIL, msg.as_string())

        logger.info(f"[Email] Digest sent to {cfg.OPERATOR_EMAIL}: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "[Email] SMTP authentication failed. "
            "Make sure you are using a Gmail App Password, not your regular password. "
            "Generate one at: https://myaccount.google.com/apppasswords"
        )
        save_digest_to_disk(html_body, date_str)
        return False

    except Exception as exc:
        logger.error(f"[Email] Delivery failed: {exc}")
        save_digest_to_disk(html_body, date_str)
        return False
