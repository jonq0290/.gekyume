"""
tiktok_scraper.py — TikTok product discovery for [.tikzon] arbitrage agent.

Data sources (in priority order):
  1. TikTok Shop US direct scrape (Playwright)
  2. FastMoss (if session cookie provided)
  3. Kalodata (if session cookie provided)
  4. Google Search fallback (no auth required)

Returns a list of ProductOpportunity objects with TikTokMetrics populated.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext

from scripts.config import cfg
from scripts.models import ProductOpportunity, TikTokMetrics, TrendVelocity
from scripts.utils import retry_with_backoff, log_rejection, today_str, load_product_log

# ─────────────────────────────────────────────
# TikTok Shop category URL map
# ─────────────────────────────────────────────
CATEGORY_URLS = {
    "beauty": "https://www.tiktok.com/shop/category/beauty-personal-care",
    "gadgets": "https://www.tiktok.com/shop/category/electronics-accessories",
    "home": "https://www.tiktok.com/shop/category/home-improvement",
}

FASTMOSS_CATEGORY_MAP = {
    "beauty": "beauty",
    "gadgets": "electronics",
    "home": "home-kitchen",
}

# Common brand indicators — products matching these are rejected immediately
BRAND_INDICATORS = [
    "apple", "samsung", "sony", "nike", "adidas", "dyson", "xiaomi",
    "anker", "logitech", "bose", "amazon basics", "kitchenaid", "instant pot",
]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def is_branded(name: str) -> bool:
    """Return True if the product name contains a known brand indicator."""
    name_lower = name.lower()
    return any(brand in name_lower for brand in BRAND_INDICATORS)


def parse_view_count(text: str) -> int:
    """Parse '1.2M', '450K', '23000' style strings to int."""
    text = text.strip().replace(",", "")
    try:
        if "M" in text.upper():
            return int(float(text.upper().replace("M", "")) * 1_000_000)
        elif "K" in text.upper():
            return int(float(text.upper().replace("K", "")) * 1_000)
        return int(float(text))
    except (ValueError, AttributeError):
        return 0


def qualifies(metrics: TikTokMetrics, tiktok_cfg: dict) -> bool:
    """Apply the TikTok qualification gate."""
    min_views = tiktok_cfg.get("min_video_views", 100_000)
    min_engagement = tiktok_cfg.get("min_engagement_rate", 0.05)
    is_bestseller = metrics.shop_rank is not None and metrics.shop_rank <= 50
    has_engagement = metrics.video_views >= min_views and metrics.engagement_rate >= min_engagement
    return is_bestseller or has_engagement


# ─────────────────────────────────────────────
# TikTok Shop direct scraper
# ─────────────────────────────────────────────

async def scrape_tiktok_shop(category: str, context: BrowserContext) -> List[Dict]:
    """Scrape TikTok Shop US bestsellers for a given category."""
    results = []
    url = CATEGORY_URLS.get(category, f"https://www.tiktok.com/shop/category/{category}")
    page = await context.new_page()

    try:
        logger.info(f"[TikTok Shop] Scraping: {category} → {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(4_000)

        # Scroll to load more products
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1_000)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        # Try multiple selectors as TikTok's frontend evolves
        cards = (
            soup.find_all("div", attrs={"data-e2e": "product-card"})
            or soup.find_all("div", class_=re.compile(r"product.?card", re.I))
            or soup.find_all("div", class_=re.compile(r"item.?card", re.I))
        )

        for rank, card in enumerate(cards[:30], start=1):
            name_el = (
                card.find("span", class_=re.compile(r"title|name", re.I))
                or card.find("p", class_=re.compile(r"title|name", re.I))
                or card.find(["h3", "h4"])
            )
            if not name_el:
                continue
            product_name = name_el.get_text(strip=True)
            if not product_name or len(product_name) < 4:
                continue

            results.append({
                "product_name": product_name,
                "category": category,
                "source": "tiktok_shop",
                "shop_rank": rank,
                "video_views": 0,
                "engagement_rate": 0.0,
            })

        logger.info(f"[TikTok Shop] {category}: {len(results)} products found")

    except Exception as exc:
        logger.warning(f"[TikTok Shop] {category} scrape error: {exc}")
    finally:
        await page.close()

    return results


# ─────────────────────────────────────────────
# FastMoss scraper
# ─────────────────────────────────────────────

async def scrape_fastmoss(category: str, context: BrowserContext) -> List[Dict]:
    """Scrape FastMoss trending products. Requires FASTMOSS_SESSION_COOKIE."""
    if not cfg.FASTMOSS_SESSION_COOKIE:
        logger.info("[FastMoss] No session cookie — skipping")
        return []

    results = []
    fm_cat = FASTMOSS_CATEGORY_MAP.get(category, category)
    url = f"https://www.fastmoss.com/products?category={fm_cat}&sort=trending&region=US"
    page = await context.new_page()

    try:
        # Inject session cookie
        await context.add_cookies([{
            "name": "session",
            "value": cfg.FASTMOSS_SESSION_COOKIE,
            "domain": ".fastmoss.com",
            "path": "/",
        }])

        logger.info(f"[FastMoss] Scraping: {category}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        rows = soup.find_all("tr", class_=re.compile(r"product|item", re.I))
        for rank, row in enumerate(rows[:20], start=1):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            product_name = cells[0].get_text(strip=True)
            views = parse_view_count(cells[1].get_text(strip=True)) if len(cells) > 1 else 0
            engagement = float(cells[2].get_text(strip=True).replace("%", "")) / 100 if len(cells) > 2 else 0.0

            results.append({
                "product_name": product_name,
                "category": category,
                "source": "fastmoss",
                "shop_rank": rank,
                "video_views": views,
                "engagement_rate": engagement,
            })

        logger.info(f"[FastMoss] {category}: {len(results)} products found")

    except Exception as exc:
        logger.warning(f"[FastMoss] {category} scrape error: {exc}")
    finally:
        await page.close()

    return results


# ─────────────────────────────────────────────
# Google Search fallback
# ─────────────────────────────────────────────

async def google_fallback(category: str) -> List[Dict]:
    """
    Fallback: search Google for trending TikTok products in this category.
    Low quality but requires no auth.
    """
    results = []
    query = f'site:tiktok.com "{category}" product trending views'
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num=20"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            resp = await client.get(url)
            soup = BeautifulSoup(resp.text, "lxml")

            titles = soup.find_all("h3")
            for rank, t in enumerate(titles[:10], start=1):
                text = t.get_text(strip=True)
                if len(text) > 10 and "tiktok" not in text.lower():
                    results.append({
                        "product_name": text,
                        "category": category,
                        "source": "google_fallback",
                        "shop_rank": None,
                        "video_views": 0,
                        "engagement_rate": 0.0,
                    })

        logger.info(f"[Google fallback] {category}: {len(results)} products found")

    except Exception as exc:
        logger.warning(f"[Google fallback] {category}: {exc}")

    return results


# ─────────────────────────────────────────────
# Trend velocity calculation
# ─────────────────────────────────────────────

def calculate_trend_velocity(
    product_name: str,
    current_views: int,
    product_log_path
) -> TrendVelocity:
    """Compare today's views to yesterday's stored metrics."""
    log = load_product_log(product_log_path)
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

    for p in log.get("products", []):
        if p.get("product_name", "").lower() == product_name.lower():
            prev_views = p.get("tiktok_views", 0)
            prev_date = p.get("scan_date", "")
            if prev_date == yesterday and prev_views > 0:
                change = (current_views - prev_views) / prev_views
                if change > 0.20:
                    return TrendVelocity.RISING
                elif change < -0.20:
                    return TrendVelocity.COOLING
                return TrendVelocity.STABLE

    return TrendVelocity.STABLE  # Default for new products


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

@retry_with_backoff(attempts=3, wait_seconds=600)
def get_tiktok_trending(previously_recommended: set[str]) -> List[ProductOpportunity]:
    """
    Run the full TikTok discovery pipeline.
    Returns a list of qualifying ProductOpportunity objects.
    """
    tiktok_cfg = cfg.tiktok_config()
    product_log_path = cfg.MEMORY_DIR / "product_log.json"
    opportunities: List[ProductOpportunity] = []
    rejected_count = 0

    async def _run() -> List[ProductOpportunity]:
        nonlocal rejected_count
        results: List[ProductOpportunity] = []

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context: BrowserContext = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )

            for category in cfg.categories():
                raw_products = await scrape_tiktok_shop(category, context)

                # Fallback to FastMoss if direct scrape returns nothing
                if not raw_products:
                    logger.warning(f"[TikTok Shop] Zero results for {category} — trying FastMoss")
                    raw_products = await scrape_fastmoss(category, context)

                # Final fallback: Google Search
                if not raw_products:
                    logger.warning(f"[FastMoss] Zero results for {category} — trying Google fallback")
                    raw_products = await google_fallback(category)

                max_products = tiktok_cfg.get("max_products_per_category", 20)
                for raw in raw_products[:max_products]:
                    product_name = raw.get("product_name", "").strip()
                    if not product_name:
                        continue

                    # Branded check
                    if is_branded(product_name):
                        log_rejection(product_name, "branded product")
                        rejected_count += 1
                        continue

                    # Deduplication
                    if product_name.lower() in previously_recommended:
                        logger.info(f"[dedup] Skipping previously recommended: {product_name}")
                        continue

                    metrics = TikTokMetrics(
                        shop_rank=raw.get("shop_rank"),
                        video_views=raw.get("video_views", 0),
                        engagement_rate=raw.get("engagement_rate", 0.0),
                        source=raw.get("source", "unknown"),
                        trending=True,
                    )

                    # Engagement gate
                    if not qualifies(metrics, tiktok_cfg):
                        log_rejection(product_name, "low engagement / not trending")
                        rejected_count += 1
                        continue

                    velocity = calculate_trend_velocity(
                        product_name, metrics.video_views, product_log_path
                    )

                    product = ProductOpportunity(
                        product_name=product_name,
                        category=category,
                        tiktok_metrics=metrics,
                        trend_velocity=velocity,
                    )
                    results.append(product)
                    logger.info(f"[QUALIFIED] {product_name} | {category} | {velocity.value}")

            await browser.close()
        return results

    try:
        opportunities = asyncio.run(_run())
    except Exception as exc:
        logger.error(f"TikTok discovery pipeline error: {exc}")
        raise

    logger.info(
        f"TikTok discovery complete: {len(opportunities)} qualifying, "
        f"{rejected_count} rejected"
    )
    return opportunities
