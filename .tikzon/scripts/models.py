"""
models.py — Pydantic data models for [.tikzon] arbitrage agent.
All pipeline stages use these shared schemas.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class RiskClass(str, Enum):
    SHORT_LIVED = "short-lived"
    SUSTAINED = "sustained"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"


class ProductStatus(str, Enum):
    DISCOVERED = "discovered"
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    PURCHASED = "purchased"
    LISTED = "listed"
    SOLD = "sold"


class TrendVelocity(str, Enum):
    RISING = "rising"
    STABLE = "stable"
    COOLING = "cooling"


class SourcingStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "no suppliers found — manual search recommended"
    PARTIAL = "partial"


# ─────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────

class TikTokMetrics(BaseModel):
    shop_rank: Optional[int] = None
    video_views: int = 0
    engagement_rate: float = 0.0
    trend_start_date: Optional[str] = None
    trending: bool = False
    source: str = "unknown"  # tiktok_shop | fastmoss | kalodata | google_fallback


class Supplier(BaseModel):
    supplier_name: str
    platform: str  # aliexpress | alibaba | 1688
    unit_cost: float
    rating: float
    order_volume: int
    shipping_time_days: int
    shipping_cost: float
    estimated_duties: float
    landed_cost: float
    moq: int = 1  # minimum order quantity
    notes: str = ""


class AmazonStatus(BaseModel):
    existing_listing: bool = False
    num_sellers: int = 0
    avg_reviews: int = 0
    avg_rating: float = 0.0
    category_gated: bool = False
    category_verified: bool = True
    trademark_risk: bool = False
    amazon_choice_badge: bool = False
    fba_referral_fee_rate: float = 0.15
    fba_fulfillment_fee: float = 3.22
    fba_storage_monthly_est: float = 0.45
    notes: str = ""


class Economics(BaseModel):
    landed_cost: float
    amazon_price: float
    amazon_price_source: str = "scraped"  # scraped | estimated
    fba_fees: float
    net_profit: float
    margin_pct: float
    go_no_go: str  # PASS | REJECT
    test_units_in_budget: int = 0
    risk_notes: str = ""


# ─────────────────────────────────────────────
# Main product model
# ─────────────────────────────────────────────

class ProductOpportunity(BaseModel):
    product_name: str
    category: str
    scan_date: str = Field(default_factory=lambda: datetime.now().date().isoformat())
    tiktok_metrics: TikTokMetrics = Field(default_factory=TikTokMetrics)
    amazon_status: AmazonStatus = Field(default_factory=AmazonStatus)
    sourcing: List[Supplier] = []
    sourcing_status: SourcingStatus = SourcingStatus.NOT_FOUND
    economics: Optional[Economics] = None
    risk_class: Optional[RiskClass] = None
    priority: Optional[Priority] = None
    trend_velocity: Optional[TrendVelocity] = None
    status: ProductStatus = ProductStatus.DISCOVERED
    rejection_reason: Optional[str] = None
    notes: str = ""

    @property
    def best_supplier(self) -> Optional[Supplier]:
        """Return the supplier with the lowest landed cost."""
        if not self.sourcing:
            return None
        return min(self.sourcing, key=lambda s: s.landed_cost)

    def reject(self, reason: str) -> None:
        self.status = ProductStatus.REJECTED
        self.rejection_reason = reason

    def recommend(self) -> None:
        self.status = ProductStatus.RECOMMENDED

    def to_sheet_row(self) -> list:
        """Serialize to a flat list for Google Sheets row insertion."""
        s = self.best_supplier
        e = self.economics
        return [
            self.scan_date,
            self.product_name,
            self.category,
            self.tiktok_metrics.shop_rank or "",
            self.tiktok_metrics.video_views,
            f"{self.tiktok_metrics.engagement_rate:.1%}",
            self.trend_velocity.value if self.trend_velocity else "",
            self.risk_class.value if self.risk_class else "",
            self.priority.value if self.priority else "",
            f"{s.supplier_name} ({s.platform})" if s else "",
            f"${s.landed_cost:.2f}" if s else "",
            f"${e.amazon_price:.2f}" if e else "",
            f"${e.fba_fees:.2f}" if e else "",
            f"${e.net_profit:.2f}" if e else "",
            f"{e.margin_pct:.1f}%" if e else "",
            self.amazon_status.num_sellers,
            self.amazon_status.avg_reviews,
            self.status.value,
            self.notes,
            self.rejection_reason or "",
        ]


# ─────────────────────────────────────────────
# Scan result container
# ─────────────────────────────────────────────

class ScanResult(BaseModel):
    scan_date: str = Field(default_factory=lambda: datetime.now().isoformat())
    scan_status: str = "success"  # success | partial | failed
    categories_scanned: List[str] = []
    total_discovered: int = 0
    total_qualified: int = 0
    total_recommended: int = 0
    opportunities: List[ProductOpportunity] = []
    rejected: List[ProductOpportunity] = []
    errors: List[str] = []

    @property
    def recommendations(self) -> List[ProductOpportunity]:
        return [p for p in self.opportunities if p.status == ProductStatus.RECOMMENDED]
