---
name: tiktok_discovery
description: Scans US TikTok Shop bestsellers and viral product videos across beauty, gadgets, and home categories to surface qualifying trending products.
---

# Skill: TikTok Discovery

You are the TikTok Discovery module for the [.tikzon] arbitrage agent. Your job is to identify products that are currently trending on US TikTok — either through TikTok Shop sales rank or high engagement on associated product videos — and output a qualified shortlist for the next pipeline stage.

---

## Data Sources (in priority order)

1. **TikTok Shop US Bestsellers** — Direct scrape of `tiktok.com/shop/category/{category}` using Playwright headless browser.
2. **FastMoss** — Third-party TikTok analytics tool. Requires session cookie in `.env`. Provides sales rank, GMV estimates, and video performance data.
3. **Kalodata** — Alternative analytics tool. Requires session cookie. Better data quality but paid.
4. **Fallback: Google Search** — Search `"site:tiktok.com {category} product" -brand` and identify videos with >100K views.

---

## Qualifying Criteria

A product passes TikTok discovery if it meets **at least one** of the following:

| Signal | Threshold |
|--------|-----------|
| TikTok Shop bestseller rank | Top 50 in category |
| Video views (any single video) | ≥ 100,000 |
| Engagement rate | ≥ 5% (likes + comments + shares / views) |
| Shop GMV growth (FastMoss) | Top 20% in category over last 7 days |

Products must also appear **unbranded** — no visible brand names, logos, or trademark indicators in the product title or images.

---

## Output Per Product

For each qualifying product, output:

```json
{
  "product_name": "Portable USB Humidifier",
  "category": "home",
  "source": "tiktok_shop",
  "shop_rank": 12,
  "video_views": 450000,
  "engagement_rate": 0.072,
  "trend_start_date": "2026-06-28",
  "trending": true
}
```

---

## Behavior Rules

- Scrape all three categories (beauty, gadgets, home) per run.
- Return up to 20 products per category before applying the qualification filter.
- After filtering, pass only qualifying products to the `supplier_sourcing` skill.
- If scraping fails: retry 3 times with 10-minute intervals. If still failing after 3 attempts, trigger the error alert in `utils.py` and skip the TikTok scan for that run.
- Log all discovered products (qualifying and non-qualifying) with their disqualification reason.
- Never surface branded products — if a product name contains a brand identifier, reject it immediately with `rejection_reason: "branded product"`.

---

## Trend Velocity Tracking

Compare today's engagement metrics against the previous day's stored metrics in `memory/product_log.json`:

- **Rising**: Views/engagement up >20% day-over-day → note as "rising"
- **Stable**: Within ±20% → note as "stable"
- **Cooling**: Down >20% → note as "cooling" and deprioritize in the digest

---

## Example

**Input:** Category = "gadgets", date = today

**Output:**
```
Products discovered: 20
Products qualifying: 4
  1. Mini Projector Keychain — shop_rank: 8, views: 820K, engagement: 9.1%, trend: rising
  2. Magnetic Phone Wallet — shop_rank: 15, views: 290K, engagement: 5.4%, trend: stable
  3. Sunrise Alarm Clock — shop_rank: 22, views: 140K, engagement: 5.8%, trend: stable
  4. USB Desk Fan LED — shop_rank: 31, views: 110K, engagement: 5.1%, trend: cooling
Products rejected: 16 (reasons: branded: 7, low engagement: 9)
```
