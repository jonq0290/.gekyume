"""
config.py — Configuration loader for [.tikzon] arbitrage agent.
Reads from .env and config/scan_config.json.
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Central configuration object. All scripts import `cfg` from this module."""

    # ── Paths ──────────────────────────────────────────────────────────────
    BASE_DIR: Path = BASE_DIR
    SKILLS_DIR: Path = BASE_DIR / "skills"
    MEMORY_DIR: Path = BASE_DIR / "memory"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # ── Email (Gmail SMTP) ─────────────────────────────────────────────────
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    OPERATOR_EMAIL: str = os.getenv("OPERATOR_EMAIL", "")

    # ── Google Sheets ──────────────────────────────────────────────────────
    GOOGLE_SHEETS_CREDENTIALS_JSON: str = os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_JSON", str(BASE_DIR / "config" / "service_account.json")
    )
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

    # ── TikTok Scraping ────────────────────────────────────────────────────
    FASTMOSS_SESSION_COOKIE: str = os.getenv("FASTMOSS_SESSION_COOKIE", "")
    KALODATA_SESSION_COOKIE: str = os.getenv("KALODATA_SESSION_COOKIE", "")

    # ── Scheduling ─────────────────────────────────────────────────────────
    OPERATOR_TIMEZONE: str = os.getenv("OPERATOR_TIMEZONE", "America/New_York")
    SCAN_HOUR: int = int(os.getenv("SCAN_HOUR", "5"))
    SCAN_MINUTE: int = int(os.getenv("SCAN_MINUTE", "0"))

    # ── Scan parameters (loaded from JSON, overridable via env) ────────────
    _scan_config: dict = {}

    @classmethod
    def load_scan_config(cls) -> dict:
        path = cls.BASE_DIR / "config" / "scan_config.json"
        try:
            with open(path) as f:
                cls._scan_config = json.load(f)
                return cls._scan_config
        except FileNotFoundError:
            logger.error(f"scan_config.json not found at {path}. Using defaults.")
            return {}

    @classmethod
    def categories(cls) -> list[str]:
        return cls._scan_config.get("categories", ["beauty", "gadgets", "home"])

    @classmethod
    def margin_threshold(cls) -> float:
        env_val = os.getenv("MARGIN_THRESHOLD")
        if env_val:
            return float(env_val)
        return cls._scan_config.get("economics", {}).get("margin_threshold", 0.30)

    @classmethod
    def max_test_budget(cls) -> float:
        env_val = os.getenv("MAX_TEST_BUDGET")
        if env_val:
            return float(env_val)
        return cls._scan_config.get("economics", {}).get("max_test_budget_usd", 100.0)

    @classmethod
    def competition_ceiling(cls) -> int:
        env_val = os.getenv("COMPETITION_CEILING")
        if env_val:
            return int(env_val)
        return cls._scan_config.get("competition", {}).get("competition_ceiling", 10)

    @classmethod
    def gated_categories(cls) -> list[str]:
        return cls._scan_config.get("amazon", {}).get("gated_categories", [])

    @classmethod
    def tiktok_config(cls) -> dict:
        return cls._scan_config.get("tiktok", {
            "min_video_views": 100000,
            "min_engagement_rate": 0.05,
            "scrape_retries": 3,
            "retry_interval_minutes": 10
        })

    @classmethod
    def economics_config(cls) -> dict:
        return cls._scan_config.get("economics", {
            "import_duty_rate_default": 0.06,
            "amazon_referral_fee_rate": 0.15,
            "fba_fulfillment_fee_small": 3.22,
            "fba_fulfillment_fee_standard": 5.32,
            "fba_storage_monthly_per_cubic_ft": 0.78
        })

    @classmethod
    def validate(cls) -> bool:
        """Check that all required env vars are present. Exit if not."""
        required = {
            "SMTP_USER": cls.SMTP_USER,
            "SMTP_PASSWORD": cls.SMTP_PASSWORD,
            "OPERATOR_EMAIL": cls.OPERATOR_EMAIL,
            "GOOGLE_SHEET_ID": cls.GOOGLE_SHEET_ID,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.error(
                f"[.tikzon] Missing required environment variables: {', '.join(missing)}\n"
                f"Copy .env.example to .env and fill in the values."
            )
            return False

        creds_path = Path(cls.GOOGLE_SHEETS_CREDENTIALS_JSON)
        if not creds_path.exists():
            logger.error(
                f"Google Sheets credentials file not found: {creds_path}\n"
                f"See README.md → 'Google Sheets Setup' for instructions."
            )
            return False

        return True

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required directories if they don't exist."""
        for d in [cls.LOGS_DIR, cls.MEMORY_DIR]:
            d.mkdir(parents=True, exist_ok=True)


# Singleton — import this everywhere
cfg = Config()
cfg.load_scan_config()
