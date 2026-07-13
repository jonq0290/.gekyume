"""
supplier_search.py — Supplier sourcing for [.tikzon] arbitrage agent.

Searches AliExpress, Alibaba, and 1688 for each qualifying product.
Returns up to 3 ranked suppliers per product by total landed cost.
"""

import re
import asyncio
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import async_playwright, BrowserContext
from deep_translator import GoogleTranslator

from scripts.config import cfg
from scripts.models import ProductOpportunity, Supplier, SourcingStatus
from scripts.utils import retry_with_backoff, log_rejection

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

ALIEXPRESS_SEARCH = "https://www.aliexpress.com/wholesale?SearchText={query}&shipCountry=US"
ALIBABA_SEARCH = "https://www.alibaba.com/trade/search?SearchText={query}&IndexArea=product_en"
SS_1688_SEARCH = "https://s.1688.com/selloffer/offer_search.htm?keywords={query}"

MIN_RATING = cfg.tiktok_config().get("min_supplier_rating", 4.5) if hasattr(cfg, "tiktok_config") else 4.5
ECONOMICS = cfg.economics_config() if hasattr(cfg, "economics_config") else {}
DEFAULT_DUTY_RATE = ECONOMICS.get("import_duty_rate_default", 0.06)
DEFAULT_SHIP_SMALL = 2.50
DEFAULT_SHIP_LARGE = 5.00


# ─────────────────────────────────────────────
# Translation helper
# ─────────────────────────────────────────────

def translate_to_chinese(text: str) -> str:
    """Translate product name to Simplified Chinese for 1688 search."""
    try:
        return GoogleTranslator(source="en", target="zh-CN").translate(text)
    except Exception as exc:
        logger.warning(f"Translation failed for '{text}': {exc}")
        return text


# ─────────────────────────────────────────────
# Price / rating parsers
# ─────────────────────────────────────────────

def parse_price(text: str) -> float:
    """Extract a float price from strings like '$3.20', 'US $3.20', '3.20 - 5.00'."""
    text = text.strip()
    # Take the lower bound if a range is given
    parts = re.split(r"[-–]", text)
    cleaned = re.sub(r"[^\d.]", "", parts[0])
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_rating(text: str) -> float:
    """Extract a float rating from strings like '4.8', '98% positive'."""
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        val = float(match.group(1))
        # Handle percentage-style ratings (e.g. 98% → 4.9 scale)
        if val > 5:
            return round(val / 20, 1)
        return val
    return 0.0


def parse_orders(text: str) -> int:
    """Extract order count from '3,420 sold', '1.2k orders', etc."""
    text = text.lower().replace(",", "")
    match = re.search(r"(\d+\.?\d*)\s*(k|m)?", text)
    if match:
        num = float(match.group(1))
        suffix = match.group(2) or ""
        if suffix == "k":
            return int(num * 1_000)
        elif suffix == "m":
            return int(num * 1_000_000)
        return int(num)
    return 0


def calculate_landed_cost(
    unit_cost: float,
    shipping_cost: float,
    duty_rate: float = DEFAULT_DUTY_RATE,
) -> float:
    duties = unit_cost * duty_rate
    return round(unit_cost + shipping_cost + duties, 2)


# ─────────────────────────────────────────────
# AliExpress scraper
# ─────────────────────────────────────────────

async def scrape_aliexpress(query: str, context: BrowserContext) -> List[Supplier]:
    suppliers = []
    url = ALIEXPRESS_SEARCH.format(query=query.replace(" ", "+"))
    page = await context.new_page()

    try:
        logger.info(f"[AliExpress] Searching: {query}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_500)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        # Product listing cards — selectors subject to change
        cards = (
            soup.find_all("div", attrs={"data-widget-cid": re.compile(r"SearchProductCard", re.I)})
            or soup.find_all("div", class_=re.compile(r"search-item|product-snippet", re.I))
            or soup.find_all("a", class_=re.compile(r"manhattan--container", re.I))
        )

        for card in cards[:10]:
            try:
                title_el = card.find(["h1", "h3", "span"], class_=re.compile(r"title|name", re.I))
                price_el = card.find(["span", "div"], class_=re.compile(r"price", re.I))
                rating_el = card.find(["span", "div"], class_=re.compile(r"rating|star|feedback", re.I))
                orders_el = card.find(["span", "div"], class_=re.compile(r"order|sold|trade", re.I))

                title = title_el.get_text(strip=True) if title_el else query
                unit_cost = parse_price(price_el.get_text(strip=True)) if price_el else 0.0
                rating = parse_rating(rating_el.get_text(strip=True)) if rating_el else 0.0
                orders = parse_orders(orders_el.get_text(strip=True)) if orders_el else 0

                if unit_cost == 0 or rating < MIN_RATING or orders < 100:
                    continue

                landed = calculate_landed_cost(unit_cost, DEFAULT_SHIP_SMALL)
                suppliers.append(Supplier(
                    supplier_name=title[:60],
                    platform="aliexpress",
                    unit_cost=unit_cost,
                    rating=rating,
                    order_volume=orders,
                    shipping_time_days=14,  # AliExpress standard estimate
                    shipping_cost=DEFAULT_SHIP_SMALL,
                    estimated_duties=round(unit_cost * DEFAULT_DUTY_RATE, 2),
                    landed_cost=landed,
                ))
            except Exception:
                continue

    except Exception as exc:
        logger.warning(f"[AliExpress] Scrape error for '{query}': {exc}")
    finally:
        await page.close()

    logger.info(f"[AliExpress] {query}: {len(suppliers)} qualifying suppliers")
    return suppliers


# ─────────────────────────────────────────────
# Alibaba scraper
# ─────────────────────────────────────────────

async def scrape_alibaba(query: str, context: BrowserContext) -> List[Supplier]:
    suppliers = []
    url = ALIBABA_SEARCH.format(query=query.replace(" ", "+"))
    page = await context.new_page()

    try:
        logger.info(f"[Alibaba] Searching: {query}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        items = soup.find_all("div", class_=re.compile(r"organic-offer-wrapper|J-offer-wrapper", re.I))

        for item in items[:10]:
            try:
                title_el = item.find("h2") or item.find("span", class_=re.compile(r"title", re.I))
                price_el = item.find("span", class_=re.compile(r"price", re.I))
                rating_el = item.find("span", class_=re.compile(r"rating|score|star", re.I))
                orders_el = item.find("span", class_=re.compile(r"order|transaction", re.I))

                title = title_el.get_text(strip=True) if title_el else query
                unit_cost = parse_price(price_el.get_text(strip=True)) if price_el else 0.0
                rating = parse_rating(rating_el.get_text(strip=True)) if rating_el else 4.6
                orders = parse_orders(orders_el.get_text(strip=True)) if orders_el else 50

                if unit_cost == 0 or rating < MIN_RATING:
                    continue

                landed = calculate_landed_cost(unit_cost, DEFAULT_SHIP_LARGE)
                suppliers.append(Supplier(
                    supplier_name=title[:60],
                    platform="alibaba",
                    unit_cost=unit_cost,
                    rating=rating,
                    order_volume=orders,
                    shipping_time_days=20,
                    shipping_cost=DEFAULT_SHIP_LARGE,
                    estimated_duties=round(unit_cost * DEFAULT_DUTY_RATE, 2),
                    landed_cost=landed,
                    moq=50,
                    notes="Alibaba listings may have MOQ. Confirm before ordering.",
                ))
            except Exception:
                continue

    except Exception as exc:
        logger.warning(f"[Alibaba] Scrape error for '{query}': {exc}")
    finally:
        await page.close()

    logger.info(f"[Alibaba] {query}: {len(suppliers)} qualifying suppliers")
    return suppliers


# ─────────────────────────────────────────────
# 1688 scraper
# ─────────────────────────────────────────────

async def scrape_1688(query: str, context: BrowserContext) -> List[Supplier]:
    suppliers = []
    cn_query = translate_to_chinese(query)
    url = SS_1688_SEARCH.format(query=cn_query.replace(" ", "+"))
    page = await context.new_page()

    try:
        logger.info(f"[1688] Searching: {query} → {cn_query}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)

        content = await page.content()
        soup = BeautifulSoup(content, "lxml")

        items = soup.find_all("div", class_=re.compile(r"offer-item|item-offer", re.I))

        for item in items[:10]:
            try:
                title_el = item.find(["h2", "span"], class_=re.compile(r"title|name", re.I))
                price_el = item.find(["span", "em"], class_=re.compile(r"price", re.I))
                rating_el = item.find("span", class_=re.compile(r"score|rate", re.I))
                orders_el = item.find("span", class_=re.compile(r"trade|sold", re.I))

                title = title_el.get_text(strip=True) if title_el else cn_query
                unit_cost = parse_price(price_el.get_text(strip=True)) if price_el else 0.0
                rating = parse_rating(rating_el.get_text(strip=True)) if rating_el else 4.7
                orders = parse_orders(orders_el.get_text(strip=True)) if orders_el else 100

                # 1688 prices are in CNY — rough conversion to USD (~0.14)
                unit_cost_usd = round(unit_cost * 0.14, 2) if unit_cost > 0 else 0.0

                if unit_cost_usd == 0 or rating < MIN_RATING:
                    continue

                # 1688 requires freight forwarder — higher shipping cost
                shipping = DEFAULT_SHIP_LARGE + 2.00
                landed = calculate_landed_cost(unit_cost_usd, shipping)

                suppliers.append(Supplier(
                    supplier_name=title[:60],
                    platform="1688",
                    unit_cost=unit_cost_usd,
                    rating=rating,
                    order_volume=orders,
                    shipping_time_days=25,
                    shipping_cost=shipping,
                    estimated_duties=round(unit_cost_usd * DEFAULT_DUTY_RATE, 2),
                    landed_cost=landed,
                    notes="1688 purchases require a sourcing agent or freight forwarder.",
                ))
            except Exception:
                continue

    except Exception as exc:
        logger.warning(f"[1688] Scrape error for '{query}': {exc}")
    finally:
        await page.close()

    logger.info(f"[1688] {query}: {len(suppliers)} qualifying suppliers")
    return suppliers


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def search_suppliers(products: List[ProductOpportunity]) -> List[ProductOpportunity]:
    """
    For each product, search all 3 platforms and attach ranked suppliers.
    Returns the products list with sourcing data populated.
    """

    async def _run() -> None:
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
                )
            )

            for product in products:
                query = product.product_name
                logger.info(f"[Sourcing] {query}")

                all_suppliers: List[Supplier] = []
                all_suppliers += await scrape_aliexpress(query, context)
                all_suppliers += await scrape_alibaba(query, context)
                all_suppliers += await scrape_1688(query, context)

                # Sort by landed cost, keep top 3
                all_suppliers.sort(key=lambda s: s.landed_cost)
                top_3 = all_suppliers[:3]

                product.sourcing = top_3
                if top_3:
                    product.sourcing_status = SourcingStatus.FOUND
                    logger.info(
                        f"[Sourcing] {query}: best landed cost ${top_3[0].landed_cost:.2f} "
                        f"({top_3[0].platform})"
                    )
                else:
                    product.sourcing_status = SourcingStatus.NOT_FOUND
                    logger.warning(f"[Sourcing] No qualifying suppliers found for: {query}")

            await browser.close()

    asyncio.run(_run())
    return products
