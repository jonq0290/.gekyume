"""
sheets_manager.py — Google Sheets integration for [.tikzon] arbitrage agent.

Manages two tabs:
  - "Opportunities": full product tracker with status lifecycle
  - "Scan Log": daily run summary

Requires: Google Sheets API credentials (service account JSON).
See README.md → "Google Sheets Setup" for full setup instructions.
"""

from datetime import datetime
from typing import List

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from scripts.config import cfg
from scripts.models import ProductOpportunity, ProductStatus, ScanResult

# ─────────────────────────────────────────────
# Google Sheets column headers
# ─────────────────────────────────────────────

OPPORTUNITY_HEADERS = [
    "Date Discovered", "Product Name", "Category",
    "TikTok Rank", "Video Views", "Engagement Rate",
    "Trend Velocity", "Risk Class", "Priority",
    "Best Supplier", "Landed Cost", "Amazon Price",
    "FBA Fees", "Net Profit", "Margin %",
    "# Amazon Sellers", "Avg Reviews",
    "Status", "Operator Notes", "Rejection Reason",
]

SCAN_LOG_HEADERS = [
    "Scan Date", "Products Discovered", "Products Qualified",
    "Products Recommended", "Scan Status", "Error Notes",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ─────────────────────────────────────────────
# Client factory
# ─────────────────────────────────────────────

def get_client() -> gspread.Client:
    """Authenticate with Google Sheets API using service account credentials."""
    creds = Credentials.from_service_account_file(
        cfg.GOOGLE_SHEETS_CREDENTIALS_JSON,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_or_create_sheet(client: gspread.Client, title: str) -> gspread.Worksheet:
    """Return a worksheet by title, creating it if it doesn't exist."""
    spreadsheet = client.open_by_key(cfg.GOOGLE_SHEET_ID)
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(OPPORTUNITY_HEADERS) + 5)
        logger.info(f"[Sheets] Created new worksheet: {title}")
        return ws


def ensure_headers(ws: gspread.Worksheet, headers: list) -> None:
    """Write headers to row 1 if the sheet is empty."""
    existing = ws.row_values(1)
    if not existing or existing[0] != headers[0]:
        ws.update("A1", [headers])
        logger.info(f"[Sheets] Headers written to {ws.title}")


# ─────────────────────────────────────────────
# Opportunities tab
# ─────────────────────────────────────────────

def get_existing_product_names(ws: gspread.Worksheet) -> dict[str, int]:
    """
    Return a dict of {product_name_lower: row_number} for deduplication.
    """
    records = ws.get_all_values()
    result = {}
    for i, row in enumerate(records[1:], start=2):  # skip header row
        if row and row[1]:
            result[row[1].lower()] = i
    return result


def append_or_update_product(
    ws: gspread.Worksheet,
    product: ProductOpportunity,
    existing: dict[str, int],
) -> None:
    """Append new products or update rows where metrics have changed."""
    row_data = product.to_sheet_row()
    name_key = product.product_name.lower()

    if name_key in existing:
        # Update existing row
        row_num = existing[name_key]
        # Only update status and economics columns — preserve operator notes
        ws.update(f"A{row_num}:T{row_num}", [row_data])
        logger.info(f"[Sheets] Updated row {row_num}: {product.product_name}")
    else:
        # Append new row
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        logger.info(f"[Sheets] Appended: {product.product_name}")


def update_opportunities_tab(
    client: gspread.Client,
    scan_result: ScanResult,
) -> None:
    """Write all recommended and rejected products to the Opportunities tab."""
    ws = get_or_create_sheet(client, "Opportunities")
    ensure_headers(ws, OPPORTUNITY_HEADERS)
    existing = get_existing_product_names(ws)

    all_products = scan_result.opportunities + scan_result.rejected
    for product in all_products:
        try:
            append_or_update_product(ws, product, existing)
        except Exception as exc:
            logger.error(f"[Sheets] Failed to write {product.product_name}: {exc}")

    logger.info(f"[Sheets] Opportunities tab updated: {len(all_products)} products")


# ─────────────────────────────────────────────
# Scan Log tab
# ─────────────────────────────────────────────

def append_scan_log(client: gspread.Client, scan_result: ScanResult) -> None:
    """Append one row to the Scan Log tab summarising today's run."""
    ws = get_or_create_sheet(client, "Scan Log")
    ensure_headers(ws, SCAN_LOG_HEADERS)

    error_summary = "; ".join(scan_result.errors[:3]) if scan_result.errors else ""

    row = [
        scan_result.scan_date,
        scan_result.total_discovered,
        scan_result.total_qualified,
        scan_result.total_recommended,
        scan_result.scan_status,
        error_summary,
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info(f"[Sheets] Scan log appended: status={scan_result.scan_status}")


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def update_google_sheets(scan_result: ScanResult) -> bool:
    """
    Update both Google Sheet tabs with the scan results.
    Returns True on success, False on failure.
    """
    try:
        client = get_client()
        update_opportunities_tab(client, scan_result)
        append_scan_log(client, scan_result)
        logger.info("[Sheets] Google Sheets update complete.")
        return True
    except Exception as exc:
        logger.error(f"[Sheets] Google Sheets update failed: {exc}")
        return False


def get_sheet_url() -> str:
    """Return the public URL of the Google Sheet for use in email digests."""
    return f"https://docs.google.com/spreadsheets/d/{cfg.GOOGLE_SHEET_ID}/edit"
