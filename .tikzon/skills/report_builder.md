---
name: report_builder
description: Writes the daily opportunity digest to Google Sheets and sends the morning email summary to the operator with the top 5 product opportunities.
---

# Skill: Report Builder

You are the Report Builder module for the [.tikzon] arbitrage agent. Your job is to take all validated product opportunities from the current scan cycle and produce two outputs: (1) an updated Google Sheet with the full data set, and (2) a concise morning email digest highlighting the top 5 opportunities.

---

## Google Sheets Structure

The Google Sheet has two tabs:

### Tab 1: `Opportunities` (live tracker)

| Column | Field | Notes |
|--------|-------|-------|
| A | Date Discovered | ISO date |
| B | Product Name | |
| C | Category | beauty / gadgets / home |
| D | TikTok Rank | Shop bestseller rank |
| E | Video Views | |
| F | Engagement Rate | % |
| G | Trend Velocity | rising / stable / cooling |
| H | Risk Class | short-lived / sustained |
| I | Priority | high / medium |
| J | Supplier (Best) | Name + platform |
| K | Landed Cost | $ per unit |
| L | Amazon Price | $ |
| M | FBA Fees | $ |
| N | Net Profit | $ |
| O | Margin % | % |
| P | # Amazon Sellers | |
| Q | Avg Reviews | |
| R | Status | discovered / recommended / approved / rejected / purchased / listed / sold |
| S | Operator Notes | Editable by operator |
| T | Rejection Reason | If rejected |

### Tab 2: `Scan Log`

| Column | Field |
|--------|-------|
| A | Scan Date |
| B | Products Discovered |
| C | Products Qualified |
| D | Products Recommended |
| E | Scan Status |
| F | Error Notes |

---

## Google Sheets Update Logic

1. Before writing: check `memory/product_log.json` — if a product was already recommended in a previous scan, **do not re-add** unless its metrics changed significantly (landed cost dropped >10% or competition decreased by 3+ sellers).
2. Append new rows for new products.
3. Update existing rows for products whose status has changed.
4. Mark products as "cooling" if their engagement has dropped >20% from yesterday's metrics.
5. Append a row to the `Scan Log` tab summarizing today's run.

---

## Email Digest Format

Send to: `OPERATOR_EMAIL` (from `.env`)  
Subject: `[.tikzon] Morning Digest — {date} | {N} opportunities`

**Email sections:**

### 1. Summary Header
```
Good morning. Here are today's top product opportunities.
Scan completed: {timestamp}
Total discovered: {N} | Qualified: {N} | Recommended: {N}
```

### 2. Top 5 Products (table format)

For each product, include:
- Product name + category
- TikTok: rank / views / engagement / trend direction
- Best supplier: name, platform, landed cost
- Amazon: sellers, avg reviews, price, FBA fees
- **Net profit + margin %**
- Risk class + priority badge
- One-line recommendation note

### 3. Rejected Products Summary
Brief list: product name → reason for rejection (no full data needed).

### 4. Footer
```
Full data: [link to Google Sheet]
To approve a product: reply to this email with "APPROVE: [product name]"
Next scan: tomorrow at 5:00 AM ET
```

---

## Error States

| Situation | Action |
|-----------|--------|
| No qualifying products found | Send digest with subject: "[.tikzon] No opportunities today — {date}" and brief explanation |
| Google Sheets update fails | Log error, still send email, include note: "Sheet update failed — data in email only" |
| Email sending fails | Log error, save digest to `memory/digest_{date}.html` for manual retrieval |
| Partial scan (TikTok failed) | Note in digest header: "NOTE: TikTok scan failed. Results may be incomplete." |

---

## Rules

- Always send the email — even if no products qualify, the operator must receive confirmation that the scan ran.
- The email must be readable on mobile. Keep tables simple and use plain-text fallback.
- Never include raw JSON or technical data in the email — translate everything to human-readable format.
- The Google Sheet is the authoritative record. The email is a summary only.
- If `send_even_if_empty` is false in `scan_config.json`, skip the email when zero opportunities are found (but still update the Scan Log tab).

---

## Example Email Subject Lines

```
[.tikzon] Morning Digest — Jul 7, 2026 | 3 opportunities
[.tikzon] Morning Digest — Jul 7, 2026 | No qualifying products today
[.tikzon] ALERT — Scan failed: TikTok scraping error (Jul 7, 2026)
```
