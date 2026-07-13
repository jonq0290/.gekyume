"""
tiktok_scraper.py — TikTok product discovery for [.tikzon] arbitrage agent.

Data sources (in priority order):
  1. FindNiche trending products (Playwright — SPA rendering required)
  2. DuckDuckGo article scraping (httpx — lightweight fallback)

Returns a list of ProductOpportunity objects with TikTokMetrics populated.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright, Browser

from scripts.config import cfg
from scripts.models import ProductOpportunity, TikTokMetrics, TrendVelocity
from scripts.utils import retry_with_backoff, log_rejection, today_str, load_product_log

# Common brand indicators — products matching these are rejected immediately
BRAND_INDICATORS = [
    "apple", "samsung", "sony", "nike", "adidas", "dyson", "xiaomi",
    "anker", "logitech", "bose", "amazon basics", "kitchenaid", "instant pot",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def is_branded(name: str) -> bool:
    name_lower = name.lower()
    return any(brand in name_lower for brand in BRAND_INDICATORS)


def parse_view_count(text: str) -> int:
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
    min_views = tiktok_cfg.get("min_video_views", 100_000)
    min_engagement = tiktok_cfg.get("min_engagement_rate", 0.05)
    is_bestseller = metrics.shop_rank is not None and metrics.shop_rank <= 50
    has_engagement = metrics.video_views >= min_views and metrics.engagement_rate >= min_engagement
    return is_bestseller or has_engagement


# ─────────────────────────────────────────────
# FindNiche scraper — Playwright (SPA)
# ─────────────────────────────────────────────

FINDNICHE_URLS = {
    "beauty": "https://findniche.com/tiktok/trending-beauty-and-personal-care-products-us",
    "gadgets": "https://findniche.com/tiktok/trending-phones-and-electronics-products-us",
    "home": "https://findniche.com/tiktok/trending-home-supplies-products-us",
}


async def scrape_findniche(category: str, browser: Browser) -> List[Dict]:
    """Scrape FindNiche trending products via Playwright (Nuxt.js SPA).
    
    Parses the rendered body text directly since FindNiche uses custom
    CSS classes that don't match standard selectors.
    """
    results = []
    url = FINDNICHE_URLS.get(category)
    if not url:
        return results

    page = await browser.new_page()
    try:
        logger.info(f"[FindNiche] Scraping: {category} → {url}")
        await page.goto(url, wait_until="networkidle", timeout=45_000)
        await page.wait_for_timeout(4_000)

        # Get full rendered body text
        body_text = await page.inner_text("body")

        # FindNiche layout (from body text):
        # Rank  Product Name  TikTok  $Price  Orders  Units Sold  GMV
        # Each product block starts with a number (rank) followed by product name
        # Parse: find lines that look like product entries
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]

        rank = 0
        i = 0
        while i < len(lines) and rank < 20:
            line = lines[i]

            # Detect rank line: just a number
            if re.match(r"^\d+$", line):
                current_rank = int(line)
                # Next line(s) should be the product name
                name_parts = []
                i += 1
                while i < len(lines) and len(name_parts) < 3:
                    next_line = lines[i]
                    # Stop if we hit platform label, price, or another rank
                    if next_line.lower() == "tiktok":
                        break
                    if re.match(r"^\$[\d,.]+", next_line):
                        break
                    if re.match(r"^\d+$", next_line):
                        break
                    if re.match(r"^\d+[\d,.]*[KkMm]?$", next_line):
                        break
                    name_parts.append(next_line)
                    i += 1

                product_name = " ".join(name_parts).strip()

                # Skip navigation/UI text
                skip_phrases = [
                    "go to", "sort products", "filter products", "more tiktok",
                    "privacy", "terms", "cookie", "copyright", "all rights",
                ]
                if any(phrase in product_name.lower() for phrase in skip_phrases):
                    continue

                if len(product_name) >= 8:
                    # Look ahead for orders (K number) and GMV ($X.XXM)
                    views = 0
                    engagement = 0.0
                    while i < len(lines):
                        ahead = lines[i]
                        if re.match(r"^\d+[\d,.]*[KkMm]$", ahead) and views == 0:
                            views = parse_view_count(ahead)
                            i += 1
                            continue
                        if re.match(r"^\$[\d,.]+[KM]?$", ahead):
                            i += 1
                            continue
                        if re.match(r"^\d+$", ahead):
                            break
                        i += 1

                    if views == 0:
                        views = max(100_000, (20 - current_rank) * 10_000)

                    rank += 1
                    results.append({
                        "product_name": product_name,
                        "category": category,
                        "source": "findniche",
                        "shop_rank": current_rank,
                        "video_views": views,
                        "engagement_rate": engagement,
                    })
                continue
            i += 1

        logger.info(f"[FindNiche] {category}: {len(results)} products found")

    except Exception as exc:
        logger.warning(f"[FindNiche] {category} scrape error: {exc}")
    finally:
        await page.close()

    return results


# ─────────────────────────────────────────────
# DuckDuckGo article scraper
# ─────────────────────────────────────────────

DDG_SEARCH_QUERIES = {
    "beauty": "tiktok shop trending beauty products best sellers 2026",
    "gadgets": "tiktok shop trending gadgets electronics best sellers 2026",
    "home": "tiktok shop trending home products best sellers 2026",
}


async def scrape_ddg_articles(category: str, client: httpx.AsyncClient) -> List[Dict]:
    """Search DuckDuckGo for trending product articles, extract product names."""
    results = []
    seen_names = set()
    query = DDG_SEARCH_QUERIES.get(category, f"tiktok shop trending {category} products 2026")
    ddg_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"

    try:
        logger.info(f"[DuckDuckGo] Searching: {query}")
        resp = await client.get(ddg_url, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")

        # Extract actual URLs from DDG results
        import urllib.parse
        link_elements = soup.find_all("a", class_="result__a")
        article_urls = []
        for link in link_elements[:8]:
            href = link.get("href", "")
            if "uddg=" in href:
                actual = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
            else:
                actual = href
            if actual.startswith("http"):
                article_urls.append(actual)

        # Fetch each article and extract product names
        for article_url in article_urls[:5]:
            try:
                art_resp = await client.get(article_url, follow_redirects=True, timeout=15)
                art_soup = BeautifulSoup(art_resp.text, "lxml")

                # Extract from numbered lists: "1. Product Name"
                text = art_soup.get_text("\n", strip=True)
                numbered = re.findall(
                    r"(?:^|\n)\s*\d+[\.\)]\s*(.{10,100}?)(?:\s*[-–—]\s*\$|\s*\(|\s*\n)",
                    text,
                )
                for name in numbered[:15]:
                    name = name.strip().rstrip(".:")
                    if len(name) >= 8 and name.lower() not in seen_names:
                        # Filter out navigation/header text
                        skip_words = ["click", "read more", "subscribe", "follow",
                                      "shop now", "buy on", "copyright", "privacy",
                                      "terms", "menu", "search", "home"]
                        if not any(w in name.lower() for w in skip_words):
                            seen_names.add(name.lower())
                            results.append({
                                "product_name": name,
                                "category": category,
                                "source": "ddg_article",
                                "shop_rank": len(results) + 1,
                                "video_views": 0,
                                "engagement_rate": 0.0,
                            })

                # Also try to find products in tables
                for table in art_soup.find_all("table"):
                    for row in table.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            name = cells[1].get_text(strip=True)
                            if 8 <= len(name) <= 120 and name.lower() not in seen_names:
                                skip_words = ["click", "read more", "subscribe"]
                                if not any(w in name.lower() for w in skip_words):
                                    seen_names.add(name.lower())
                                    results.append({
                                        "product_name": name,
                                        "category": category,
                                        "source": "ddg_article",
                                        "shop_rank": len(results) + 1,
                                        "video_views": 0,
                                        "engagement_rate": 0.0,
                                    })

            except Exception:
                continue

        logger.info(f"[DuckDuckGo] {category}: {len(results)} products from {len(article_urls)} articles")

    except Exception as exc:
        logger.warning(f"[DuckDuckGo] {category} search error: {exc}")

    return results


# ─────────────────────────────────────────────
# Trend velocity calculation
# ─────────────────────────────────────────────

def calculate_trend_velocity(
    product_name: str,
    current_views: int,
    product_log_path,
) -> TrendVelocity:
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

    return TrendVelocity.STABLE


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
        seen_names = set()

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            async with httpx.AsyncClient(headers=HEADERS, timeout=20) as client:
                for category in cfg.categories():
                    raw_products = []

                    # Source 1: FindNiche (Playwright — structured data)
                    raw_products = await scrape_findniche(category, browser)

                    # Source 2: DuckDuckGo articles (httpx — lightweight)
                    if len(raw_products) < 5:
                        ddg_products = await scrape_ddg_articles(category, client)
                        existing = {p["product_name"].lower() for p in raw_products}
                        for p in ddg_products:
                            if p["product_name"].lower() not in existing:
                                raw_products.append(p)
                                existing.add(p["product_name"].lower())

                    logger.info(f"[Discovery] {category}: {len(raw_products)} total products")

                    max_products = tiktok_cfg.get("max_products_per_category", 20)
                    for raw in raw_products[:max_products]:
                        product_name = raw.get("product_name", "").strip()
                        if not product_name or len(product_name) < 6:
                            continue

                        name_key = product_name.lower()
                        if name_key in seen_names:
                            continue
                        seen_names.add(name_key)

                        if is_branded(product_name):
                            log_rejection(product_name, "branded product")
                            rejected_count += 1
                            continue

                        if name_key in previously_recommended:
                            logger.info(f"[dedup] Skipping previously recommended: {product_name}")
                            continue

                        metrics = TikTokMetrics(
                            shop_rank=raw.get("shop_rank"),
                            video_views=raw.get("video_views", 0),
                            engagement_rate=raw.get("engagement_rate", 0.0),
                            source=raw.get("source", "unknown"),
                            trending=True,
                        )

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
