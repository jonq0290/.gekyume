"""
amazon_checker.py — Amazon validation for [.tikzon] arbitrage agent.

For each product:
  1. Checks if the category is gated
  2. Detects trademark/brand risk
  3. Counts competing sellers
  4. Estimates FBA fees
  5. Sets priority (high/medium) and flags first-to-market opportunities
"""

import re
import asyncio
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright, BrowserContext

from scripts.config import cfg
from scripts.models import ProductOpportunity, AmazonStatus, Priority, ProductStatus
from scripts.utils import log_rejection

AMAZON_SEARCH_URL = "https://www.amazon.com/s?k={query}&ref=nb_sb_noss"

# Trademark markers often found in listing titles
TRADEMARK_PATTERNS = [re.compile(p, re.I) for p in [
    r"\bregistered\b", r"®", r"™", r"\btrademark\b",
    r"\bpatented\b", r"\blicensed\b",
]]

# FBA fee tiers (approximate, based on Amazon's public schedule)
FBA_TIERS = {
    "small_standard": {"fulfillment": 3.22, "max_weight_oz": 16},
    "standard":       {"fulfillment": 5.32, "max_weight_oz": 48},
    "large_standard": {"fulfillment": 8.26, "max_weight_oz": 320},
}

REFERRAL_FEE_RATE = 0.15        # 15% across most categories
STORAGE_EST_2MO = 0.45          # ~2 months of monthly storage per unit


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def is_gated_category(category: str) -> bool:
    """Check if the product's general category is on the gated list."""
    gated = cfg.gated_categories()
    return any(g.lower() in category.lower() for g in gated)


def detect_trademark(title: str) -> bool:
    """Return True if the listing title contains trademark signals."""
    return any(p.search(title) for p in TRADEMARK_PATTERNS)


def estimate_fba_fees(amazon_price: float, size_tier: str = "small_standard") -> Tuple[float, float, float]:
    """
    Returns (referral_fee, fulfillment_fee, storage_est) for a given selling price.
    """
    referral = round(amazon_price * REFERRAL_FEE_RATE, 2)
    fulfillment = FBA_TIERS.get(size_tier, FBA_TIERS["small_standard"])["fulfillment"]
    storage = STORAGE_EST_2MO
    return referral, fulfillment, storage


def count_sellers_from_soup(soup: BeautifulSoup) -> int:
    """Attempt to count distinct seller counts from Amazon search results."""
    seller_elements = soup.find_all(
        "span",
        string=re.compile(r"\d+\s*(new|used|seller|offer)", re.I),
    )
    counts = []
    for el in seller_elements:
        match = re.search(r"(\d+)", el.get_text())
        if match:
            counts.append(int(match.group(1)))
    return max(counts) if counts else 0


# ─────────────────────────────────────────────
# Amazon page scraper
# ─────────────────────────────────────────────

async def check_amazon_product(
    product: ProductOpportunity,
    context: BrowserContext,
) -> ProductOpportunity:
    """Scrape Amazon search results for a product and populate its AmazonStatus."""
    query = product.product_name
    url = AMAZON_SEARCH_URL.format(query=query.replace(" ", "+"))
    page = await context.new_page()
    status = AmazonStatus()

    try:
        # Category gating check (local — no scraping needed)
        if is_gated_category(product.category):
            product.amazon_status = AmazonStatus(
                category_gated=True,
                category_verified=True,
            )
            product.reject("gated Amazon category")
            log_rejection(query, "gated Amazon category")
            return product

        logger.info(f"[Amazon] Checking: {query}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        # ── Listing existence ───────────────────────────────────────────────
        result_divs = soup.find_all("div", {"data-component-type": "s-search-result"})
        status.existing_listing = len(result_divs) > 0

        if not status.existing_listing:
            logger.info(f"[Amazon] No listing found — HIGH PRIORITY first-to-market: {query}")
            product.amazon_status = status
            product.priority = Priority.HIGH
            product.notes = "No Amazon listing exists — first-to-market opportunity."
            return product

        # ── Trademark check ─────────────────────────────────────────────────
        first_title_el = soup.find("span", class_="a-size-medium a-color-base a-text-normal") \
                      or soup.find("h2", class_=re.compile(r"a-size", re.I))
        first_title = first_title_el.get_text(strip=True) if first_title_el else ""

        if detect_trademark(first_title):
            product.reject("branded product — trademark risk")
            log_rejection(query, "trademark detected in first listing")
            product.amazon_status = AmazonStatus(trademark_risk=True)
            return product

        # ── Seller count ────────────────────────────────────────────────────
        num_sellers = len(result_divs)  # rough proxy; each result = distinct offer
        status.num_sellers = num_sellers

        # ── Review aggregation ──────────────────────────────────────────────
        review_counts = []
        ratings = []
        for div in result_divs[:5]:
            review_el = div.find("span", class_=re.compile(r"a-size-base.*review", re.I)) \
                     or div.find("span", attrs={"aria-label": re.compile(r"\d+ rating", re.I)})
            rating_el = div.find("span", class_="a-icon-alt")
            if review_el:
                rc = parse_review_count(review_el.get_text(strip=True))
                if rc:
                    review_counts.append(rc)
            if rating_el:
                rm = re.search(r"(\d+\.?\d*)\s*out", rating_el.get_text())
                if rm:
                    ratings.append(float(rm.group(1)))

        status.avg_reviews = int(sum(review_counts) / len(review_counts)) if review_counts else 0
        status.avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        # ── Amazon's Choice badge ───────────────────────────────────────────
        status.amazon_choice_badge = bool(
            soup.find("span", class_=re.compile(r"ac-badge|amazons-choice", re.I))
        )

        # ── Competition gate ────────────────────────────────────────────────
        ceiling = cfg.competition_ceiling()
        if num_sellers >= ceiling:
            product.reject(f"too many sellers ({num_sellers} found, ceiling: {ceiling})")
            log_rejection(query, f"too many sellers: {num_sellers}")
            product.amazon_status = status
            return product

        # ── Priority assignment ─────────────────────────────────────────────
        if num_sellers <= 4 and status.avg_reviews < 100:
            product.priority = Priority.HIGH
        else:
            product.priority = Priority.MEDIUM

        status.category_gated = False
        status.trademark_risk = False
        product.amazon_status = status

        logger.info(
            f"[Amazon] {query}: {num_sellers} sellers, "
            f"avg {status.avg_reviews} reviews, priority={product.priority.value}"
        )

    except Exception as exc:
        logger.warning(f"[Amazon] Error checking '{query}': {exc}")
        product.amazon_status = AmazonStatus(
            category_verified=False,
            notes="category status unverified — check manually before listing",
        )
    finally:
        await page.close()

    return product


def parse_review_count(text: str) -> int:
    """Parse '1,234 ratings' → 1234."""
    cleaned = re.sub(r"[^\d]", "", text.split()[0]) if text else ""
    try:
        return int(cleaned)
    except ValueError:
        return 0


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def check_amazon_for_products(products: List[ProductOpportunity]) -> List[ProductOpportunity]:
    """
    Run Amazon checks for all products. Returns the updated list.
    Products that fail the competition or gating gate are marked REJECTED.
    """

    async def _run() -> List[ProductOpportunity]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )

            checked = []
            for product in products:
                result = await check_amazon_product(product, context)
                checked.append(result)

            await browser.close()
        return checked

    return asyncio.run(_run())
