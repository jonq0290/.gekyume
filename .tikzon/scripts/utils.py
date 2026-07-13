"""
utils.py — Shared utilities for [.tikzon] arbitrage agent.
Provides: logging setup, retry decorator, error notification, product log I/O.
"""

import json
import time
import smtplib
import functools
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from typing import Callable, Any, Optional

from loguru import logger


# ─────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────

def setup_logging(log_dir: Path) -> None:
    """Configure loguru to write to rotating daily log files."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_dir / "tikzon_{time:YYYY-MM-DD}.log"),
        rotation="00:00",       # rotate at midnight
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} — {message}",
        enqueue=True,           # thread-safe
    )
    logger.info("[.tikzon] Logging initialized.")


# ─────────────────────────────────────────────
# Retry decorator
# ─────────────────────────────────────────────

def retry_with_backoff(attempts: int = 3, wait_seconds: int = 600) -> Callable:
    """
    Decorator: retries the wrapped function up to `attempts` times,
    waiting `wait_seconds` between each attempt.
    On final failure, raises the last exception.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    if attempt < attempts:
                        logger.warning(
                            f"[retry] {func.__name__} failed "
                            f"(attempt {attempt}/{attempts}): {exc}. "
                            f"Retrying in {wait_seconds}s..."
                        )
                        time.sleep(wait_seconds)
                    else:
                        logger.error(
                            f"[retry] {func.__name__} failed after "
                            f"{attempts} attempts: {exc}"
                        )
            raise last_exception  # type: ignore
        return wrapper
    return decorator


# ─────────────────────────────────────────────
# Error notification (plain-text email alert)
# ─────────────────────────────────────────────

def send_alert_email(subject: str, body: str, cfg: Any) -> None:
    """Send a plain-text alert email to the operator via Gmail SMTP."""
    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = cfg.SMTP_USER
        msg["To"] = cfg.OPERATOR_EMAIL

        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.sendmail(cfg.SMTP_USER, cfg.OPERATOR_EMAIL, msg.as_string())

        logger.info(f"Alert email sent: {subject}")
    except Exception as exc:
        logger.error(f"Failed to send alert email: {exc}")


# ─────────────────────────────────────────────
# Product log I/O
# ─────────────────────────────────────────────

def load_product_log(log_path: Path) -> dict:
    """Load the local product log from memory/product_log.json."""
    if not log_path.exists():
        return {"products": [], "last_scan": None, "scan_count": 0}
    with open(log_path) as f:
        return json.load(f)


def save_product_log(log_path: Path, data: dict) -> None:
    """Persist the product log back to disk."""
    with open(log_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Product log saved: {log_path}")


def get_previously_recommended(log_path: Path) -> set[str]:
    """Return a set of product names already recommended in past scans."""
    log = load_product_log(log_path)
    return {
        p["product_name"].lower()
        for p in log.get("products", [])
        if p.get("status") in {"recommended", "approved", "purchased", "listed", "sold"}
    }


def update_context(context_path: Path, scan_result: Any) -> None:
    """Update memory/context.json with latest scan metadata."""
    try:
        with open(context_path) as f:
            ctx = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ctx = {}

    ctx["last_scan_date"] = scan_result.scan_date
    ctx["last_scan_status"] = scan_result.scan_status
    ctx["total_products_discovered"] = ctx.get("total_products_discovered", 0) + scan_result.total_discovered
    ctx["total_products_recommended"] = ctx.get("total_products_recommended", 0) + scan_result.total_recommended
    ctx["session_count"] = ctx.get("session_count", 0) + 1
    ctx["last_updated"] = datetime.now().isoformat()

    with open(context_path, "w") as f:
        json.dump(ctx, f, indent=2)
    logger.info("Context memory updated.")


# ─────────────────────────────────────────────
# Misc helpers
# ─────────────────────────────────────────────

def log_rejection(product_name: str, reason: str) -> None:
    """Convenience wrapper for rejection logging."""
    logger.info(f"REJECTED | {product_name} | {reason}")


def today_str() -> str:
    return datetime.now().date().isoformat()


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division with zero-denominator guard."""
    if denominator == 0:
        return default
    return numerator / denominator
