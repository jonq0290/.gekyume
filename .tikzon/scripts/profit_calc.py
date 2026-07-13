"""
profit_calc.py — Profit calculation and go/no-go gate for [.tikzon] arbitrage agent.

For each product with at least one supplier:
  - Calculates full economics (landed cost → net margin)
  - Applies the 30% margin gate
  - Assigns risk classification (short-lived / sustained)
  - Checks test order fits within $100 budget
"""

import math
from datetime import datetime, timedelta
from typing import List, Optional

from loguru import logger

from scripts.config import cfg
from scripts.models import (
    ProductOpportunity,
    Supplier,
    Economics,
    RiskClass,
    ProductStatus,
    TrendVelocity,
)
from scripts.utils import log_rejection, safe_divide

ECONOMICS = cfg.economics_config()
REFERRAL_FEE_RATE = ECONOMICS.get("amazon_referral_fee_rate", 0.15)
FULFILLMENT_FEE_SMALL = ECONOMICS.get("fba_fulfillment_fee_small", 3.22)
FULFILLMENT_FEE_STANDARD = ECONOMICS.get("fba_fulfillment_fee_standard", 5.32)
STORAGE_EST_2MO = 0.45  # $0.78/cu ft × ~0.58 cu ft × 2 months ≈ $0.45

# Price multipliers for "no listing" estimation
ALIEXPRESS_RETAIL_MULTIPLIER = 3.5  # Estimate Amazon price from AliExpress unit cost
TIKTOK_PRICE_MULTIPLIER = 2.2       # Estimate from TikTok Shop price


# ─────────────────────────────────────────────
# Amazon price estimation
# ─────────────────────────────────────────────

def estimate_amazon_price(product: ProductOpportunity) -> tuple[float, str]:
    """
    Estimate the Amazon selling price when no listing exists.
    Returns (price_estimate, source_description).
    """
    best = product.best_supplier
    if not best:
        return 0.0, "unknown"

    # Use AliExpress cost × multiplier as primary estimate
    estimated = round(best.unit_cost * ALIEXPRESS_RETAIL_MULTIPLIER, 2)
    return estimated, "estimated (landed_cost × 3.5x multiplier)"


def get_amazon_price(product: ProductOpportunity) -> tuple[float, str]:
    """
    Return the Amazon selling price and its source.
    For products with no listing, estimate it.
    """
    # Try to get from scraped data stored in amazon_status notes
    # (In a future version, this could pull from a price scrape step)
    # For now: use notes field if price was scraped, else estimate
    notes = product.amazon_status.notes or ""
    price_match = None

    import re
    m = re.search(r"price[:\s]+\$?([\d.]+)", notes, re.I)
    if m:
        return float(m.group(1)), "scraped"

    if not product.amazon_status.existing_listing:
        return estimate_amazon_price(product)

    # Listing exists but no price captured — estimate from supplier
    return estimate_amazon_price(product)


# ─────────────────────────────────────────────
# FBA fee calculation
# ─────────────────────────────────────────────

def calculate_fba_fees(amazon_price: float, size_tier: str = "small") -> float:
    """Return total estimated FBA fees for one unit."""
    referral = round(amazon_price * REFERRAL_FEE_RATE, 2)
    fulfillment = FULFILLMENT_FEE_SMALL if size_tier == "small" else FULFILLMENT_FEE_STANDARD
    total = referral + fulfillment + STORAGE_EST_2MO
    return round(total, 2)


# ─────────────────────────────────────────────
# Risk classification
# ─────────────────────────────────────────────

def classify_risk(product: ProductOpportunity) -> tuple[RiskClass, str]:
    """
    Assign a risk classification based on trend signals.
    Default: SHORT_LIVED if longevity is ambiguous.
    """
    notes = ""
    metrics = product.tiktok_metrics
    velocity = product.trend_velocity

    # Signals pointing to SUSTAINED demand
    sustained_signals = 0
    if velocity == TrendVelocity.STABLE:
        sustained_signals += 1
    if velocity == TrendVelocity.RISING:
        sustained_signals += 1

    # Check trend start date — older trends are more likely sustained
    if metrics.trend_start_date:
        try:
            start = datetime.fromisoformat(metrics.trend_start_date)
            days_trending = (datetime.now() - start).days
            if days_trending >= 28:
                sustained_signals += 2
            elif days_trending >= 14:
                sustained_signals += 1
        except ValueError:
            pass

    # Category heuristics — home/utility products tend to be more sustained
    if product.category == "home" and "organiz" in product.product_name.lower():
        sustained_signals += 1
    if product.category == "beauty" and "viral" in product.notes.lower():
        sustained_signals -= 1  # Beauty trends can be very short

    if sustained_signals >= 3:
        return RiskClass.SUSTAINED, ""
    elif sustained_signals == 2:
        notes = "moderate sustained signals — monitor for 2+ weeks before bulk order"
        return RiskClass.SHORT_LIVED, notes
    else:
        notes = "trend longevity uncertain — defaulting to short-lived"
        return RiskClass.SHORT_LIVED, notes


# ─────────────────────────────────────────────
# Main calculation
# ─────────────────────────────────────────────

def calculate_profit(product: ProductOpportunity) -> ProductOpportunity:
    """
    Run full economics for a single product.
    Populates product.economics and applies go/no-go gate.
    """
    best: Optional[Supplier] = product.best_supplier
    margin_threshold = cfg.margin_threshold()
    max_budget = cfg.max_test_budget()

    # Cannot calculate without a supplier
    if not best:
        product.reject("no qualifying supplier — sourcing needed")
        log_rejection(product.product_name, "no supplier")
        return product

    # Get Amazon price
    amazon_price, price_source = get_amazon_price(product)
    if amazon_price <= 0:
        product.reject("could not determine Amazon selling price")
        return product

    # FBA fees
    fba_fees = calculate_fba_fees(amazon_price)

    # Net profit
    net_profit = round(amazon_price - best.landed_cost - fba_fees, 2)
    margin_pct = round(safe_divide(net_profit, amazon_price) * 100, 1)

    # Go / No-Go
    passes = margin_pct >= (margin_threshold * 100)
    go_no_go = "PASS" if passes else "REJECT"

    # Test order units in budget
    test_units = math.floor(max_budget / best.landed_cost) if best.landed_cost > 0 else 0

    # Risk classification
    risk_class, risk_notes = classify_risk(product)

    # Margin warning
    extra_notes = ""
    if passes and margin_pct < 35:
        extra_notes = "⚠️ Margin is marginal (30–35%) — verify price assumption before ordering."
    if test_units < 5:
        extra_notes += " ⚠️ Test order may be too small for meaningful validation — consider supplier negotiation."

    product.economics = Economics(
        landed_cost=best.landed_cost,
        amazon_price=amazon_price,
        amazon_price_source=price_source,
        fba_fees=fba_fees,
        net_profit=net_profit,
        margin_pct=margin_pct,
        go_no_go=go_no_go,
        test_units_in_budget=test_units,
        risk_notes=(risk_notes + " " + extra_notes).strip(),
    )
    product.risk_class = risk_class

    if not passes:
        product.reject(
            f"margin below {int(margin_threshold * 100)}% "
            f"(actual: {margin_pct:.1f}%)"
        )
        log_rejection(
            product.product_name,
            f"margin {margin_pct:.1f}% < {int(margin_threshold * 100)}% threshold",
        )
    elif test_units < 1:
        product.reject("min order exceeds $100 budget")
        log_rejection(product.product_name, "test order exceeds $100 budget")
    else:
        product.recommend()
        logger.info(
            f"[Profit] ✅ PASS: {product.product_name} | "
            f"margin={margin_pct:.1f}% | profit=${net_profit:.2f} | "
            f"risk={risk_class.value}"
        )

    return product


def run_profit_calculations(products: List[ProductOpportunity]) -> List[ProductOpportunity]:
    """
    Apply profit calculations to a list of products.
    Skips products already rejected by upstream stages.
    """
    for product in products:
        if product.status == ProductStatus.REJECTED:
            continue
        calculate_profit(product)

    passed = sum(1 for p in products if p.status == ProductStatus.RECOMMENDED)
    rejected = sum(1 for p in products if p.status == ProductStatus.REJECTED)
    logger.info(f"[Profit] Results: {passed} PASS, {rejected} REJECT (total: {len(products)})")

    return products
