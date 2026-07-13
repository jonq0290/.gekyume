"""
main.py — Daily entry point and pipeline orchestrator for [.tikzon] arbitrage agent.
Coordinates TikTok discovery, supplier sourcing, Amazon validation, profit calculation,
and report/email digest delivery.
"""

import sys
import argparse
import json
import math
from pathlib import Path
from loguru import logger
import schedule
import time

# Import local modules
from scripts.config import cfg
from scripts.models import ScanResult, ProductOpportunity, ProductStatus, SourcingStatus
from scripts.utils import (
    setup_logging,
    load_product_log,
    save_product_log,
    get_previously_recommended,
    update_context,
    send_alert_email,
    today_str,
)
from scripts.tiktok_scraper import get_tiktok_trending
from scripts.supplier_search import search_suppliers
from scripts.amazon_checker import check_amazon_for_products
from scripts.profit_calc import run_profit_calculations
from scripts.sheets_manager import update_google_sheets
from scripts.email_sender import send_digest


def run_full_pipeline(no_email: bool = False) -> ScanResult:
    """Run the entire 5-stage research pipeline."""
    errors = []
    opportunities = []
    
    logger.info("[.tikzon] Starting full daily research pipeline run.")
    
    # Stage 1: TikTok Discovery
    previously_recommended = get_previously_recommended(cfg.MEMORY_DIR / "product_log.json")
    try:
        logger.info("Stage 1: Running TikTok Discovery...")
        opportunities = get_tiktok_trending(previously_recommended)
    except Exception as exc:
        logger.error(f"TikTok discovery failed: {exc}")
        errors.append(f"TikTok discovery failed: {exc}")
        # Error Recovery: Try to load cached products from yesterday if available
        try:
            log_path = cfg.MEMORY_DIR / "product_log.json"
            log_data = load_product_log(log_path)
            cached_products = []
            for p_dict in log_data.get("products", []):
                if p_dict.get("status") in ["discovered", "recommended"]:
                    cached_products.append(ProductOpportunity(**p_dict))
            if cached_products:
                logger.info(f"Loaded {len(cached_products)} cached products from product_log.json to continue.")
                opportunities = cached_products
            else:
                opportunities = []
        except Exception as cache_exc:
            logger.error(f"Failed to load cached products: {cache_exc}")
            opportunities = []

    total_discovered = len(opportunities)
    total_qualified = len(opportunities)

    # Stage 2: Supplier Sourcing
    if opportunities:
        try:
            logger.info("Stage 2: Running Supplier Sourcing...")
            opportunities = search_suppliers(opportunities)
        except Exception as exc:
            logger.error(f"Supplier sourcing failed: {exc}")
            errors.append(f"Supplier sourcing failed: {exc}")
    
    # Stage 3: Amazon Checker
    if opportunities:
        try:
            logger.info("Stage 3: Running Amazon Checker...")
            opportunities = check_amazon_for_products(opportunities)
        except Exception as exc:
            logger.error(f"Amazon checker failed: {exc}")
            errors.append(f"Amazon checker failed: {exc}")

    # Stage 4: Profit Calculator
    if opportunities:
        try:
            logger.info("Stage 4: Running Profit Calculator...")
            opportunities = run_profit_calculations(opportunities)
        except Exception as exc:
            logger.error(f"Profit calculations failed: {exc}")
            errors.append(f"Profit calculations failed: {exc}")

    # Stage 5: Report Builder & Updates
    recommended = [p for p in opportunities if p.status == ProductStatus.RECOMMENDED]
    rejected = [p for p in opportunities if p.status == ProductStatus.REJECTED]

    scan_result = ScanResult(
        scan_date=today_str(),
        scan_status="success" if not errors else "partial",
        categories_scanned=cfg.categories(),
        total_discovered=total_discovered,
        total_qualified=total_qualified,
        total_recommended=len(recommended),
        opportunities=recommended,
        rejected=rejected,
        errors=errors
    )

    # 5a. Update Google Sheets
    sheets_success = False
    try:
        logger.info("Stage 5a: Updating Google Sheets...")
        sheets_success = update_google_sheets(scan_result)
        if not sheets_success:
            errors.append("Google Sheets update returned False")
    except Exception as exc:
        logger.error(f"Google Sheets update failed: {exc}")
        errors.append(f"Google Sheets update failed: {exc}")

    # 5b. Send Morning Digest Email
    email_success = False
    if no_email:
        logger.info("Stage 5b: Email skipped (--no-email flag).")
        email_success = True
    else:
        try:
            logger.info("Stage 5b: Sending morning email digest...")
            email_success = send_digest(scan_result)
            if not email_success:
                errors.append("Email digest sending returned False")
        except Exception as exc:
            logger.error(f"Email digest sending failed: {exc}")
            errors.append(f"Email digest sending failed: {exc}")

    # 5c. Local Memory Updates
    try:
        logger.info("Updating local memory (context.json & product_log.json)...")
        update_context(cfg.MEMORY_DIR / "context.json", scan_result)
        
        log_path = cfg.MEMORY_DIR / "product_log.json"
        log_data = load_product_log(log_path)
        
        # Merge new scan results into local log
        product_map = {p["product_name"].lower(): p for p in log_data.get("products", [])}
        for p in opportunities:
            p_dict = json.loads(p.model_dump_json())
            product_map[p.product_name.lower()] = p_dict
            
        log_data["products"] = list(product_map.values())
        log_data["last_scan"] = scan_result.scan_date
        log_data["scan_count"] = log_data.get("scan_count", 0) + 1
        
        save_product_log(log_path, log_data)
    except Exception as exc:
        logger.error(f"Failed to update local memory: {exc}")
        errors.append(f"Failed to update local memory: {exc}")

    if errors:
        scan_result.scan_status = "partial"
        scan_result.errors = errors
        # Send system failure alert email
        try:
            subject = f"[.tikzon] ⚠️ Alert: Scan finished with {len(errors)} errors"
            body = "The daily scan completed with the following errors:\n\n" + "\n".join([f"- {err}" for err in errors])
            send_alert_email(subject, body, cfg)
        except Exception as alert_exc:
            logger.error(f"Failed to send system alert email: {alert_exc}")

    logger.info(f"[.tikzon] Pipeline run complete. Status: {scan_result.scan_status}")
    return scan_result


def approve_product(product_name: str):
    """Approve a product, update Sheets & log, and output ordering instructions."""
    logger.info(f"Processing manual operator approval for product: {product_name}")
    log_path = cfg.MEMORY_DIR / "product_log.json"
    log_data = load_product_log(log_path)
    
    products = log_data.get("products", [])
    found_prod = None
    for p in products:
        if p.get("product_name", "").lower() == product_name.lower():
            found_prod = p
            break
            
    if not found_prod:
        logger.error(f"Product '{product_name}' not found in local product log.")
        sys.exit(1)
        
    # Update status to approved
    found_prod["status"] = "approved"
    save_product_log(log_path, log_data)
    
    product_opportunity = ProductOpportunity(**found_prod)
    
    # Update Google Sheets
    try:
        from scripts.sheets_manager import get_client, get_or_create_sheet, get_existing_product_names, append_or_update_product
        client = get_client()
        ws = get_or_create_sheet(client, "Opportunities")
        existing = get_existing_product_names(ws)
        append_or_update_product(ws, product_opportunity, existing)
        logger.info(f"Google Sheets updated with approved status for '{product_name}'.")
    except Exception as e:
        logger.error(f"Failed to update Google Sheets: {e}")
        
    # Generate ordering instructions
    best_supplier = product_opportunity.best_supplier
    if best_supplier:
        landed = best_supplier.landed_cost
        moq = best_supplier.moq
        max_budget = cfg.max_test_budget()
        test_units = math.floor(max_budget / landed) if landed > 0 else 0
        total_cost = landed * test_units
        
        instructions_text = f"""
============================================================
[.tikzon] ORDERING INSTRUCTIONS FOR {product_opportunity.product_name.upper()}
============================================================
Supplier Name: {best_supplier.supplier_name}
Platform: {best_supplier.platform.upper()}
Landed Cost per Unit: ${landed:.2f}
Unit Sourcing Cost: ${best_supplier.unit_cost:.2f}
Shipping Cost: ${best_supplier.shipping_cost:.2f}
Estimated Duties: ${best_supplier.estimated_duties:.2f}
Minimum Order Quantity (MOQ): {moq}
Estimated Shipping Time: {best_supplier.shipping_time_days} days

RECOMMENDED ACTION PLAN:
1. Navigate to {best_supplier.platform.upper()} and find the supplier: "{best_supplier.supplier_name}".
2. Place a test order of exactly {test_units} units.
   - Cost per unit: ${landed:.2f}
   - Estimated total: ${total_cost:.2f} (Fits within the $100 risk limit)
3. Once purchase is complete, manually change status in Google Sheet to "PURCHASED".
4. Additional Notes: {best_supplier.notes}
============================================================
"""
        instructions_html = f"""
<h2>Ordering Instructions: {product_opportunity.product_name}</h2>
<p><strong>Supplier:</strong> {best_supplier.supplier_name} ({best_supplier.platform.upper()})</p>
<ul>
  <li><strong>Landed Cost:</strong> ${landed:.2f} (Unit: ${best_supplier.unit_cost:.2f}, Shipping: ${best_supplier.shipping_cost:.2f}, Duties: ${best_supplier.estimated_duties:.2f})</li>
  <li><strong>Minimum Order Quantity (MOQ):</strong> {moq}</li>
  <li><strong>Estimated Shipping Time:</strong> {best_supplier.shipping_time_days} days</li>
</ul>
<h3>Action Plan:</h3>
<ol>
  <li>Log in to <strong>{best_supplier.platform.upper()}</strong> and find the supplier <em>"{best_supplier.supplier_name}"</em>.</li>
  <li>Place a test order of <strong>{test_units} units</strong>.
    <ul>
      <li>Estimated Total Cost: <strong>${total_cost:.2f}</strong> (Under your max risk budget of ${max_budget:.2f})</li>
    </ul>
  </li>
  <li>Update the Google Sheets opportunity status to <strong>PURCHASED</strong> once the order is placed.</li>
  <li>Supplier Notes: {best_supplier.notes}</li>
</ol>
"""
    else:
        instructions_text = f"Approved '{product_opportunity.product_name}'. No supplier details were found in local history."
        instructions_html = f"<p>Approved '{product_opportunity.product_name}'. No supplier details were found in local history.</p>"
        
    print(instructions_text)
    
    # Send email confirmation
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import smtplib
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[.tikzon] Approval Confirmation — {product_opportunity.product_name}"
        msg["From"] = cfg.SMTP_USER
        msg["To"] = cfg.OPERATOR_EMAIL
        msg.attach(MIMEText(instructions_text, "plain"))
        msg.attach(MIMEText(instructions_html, "html"))
        
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.sendmail(cfg.SMTP_USER, cfg.OPERATOR_EMAIL, msg.as_string())
        logger.info(f"Approval confirmation email successfully sent to {cfg.OPERATOR_EMAIL}.")
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")


def main():
    parser = argparse.ArgumentParser(description="[.tikzon] Arbitrage Pipeline Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Validate environment configuration and exit")
    parser.add_argument("--categories", type=str, help="Comma-separated categories to scan (overrides scan_config.json)")
    parser.add_argument("--force", action="store_true", help="Skip any schedule/lock checks and run immediately")
    parser.add_argument("--approve", type=str, help="Approve a product opportunity by product name")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode with standard daily scheduler")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email digest (useful for --force test runs)")
    
    args = parser.parse_args()
    
    # Initialize logging
    setup_logging(cfg.LOGS_DIR)
    cfg.ensure_dirs()
    
    # Handle dry run
    if args.dry_run:
        logger.info("[.tikzon] Running configuration and dependency validation...")
        if cfg.validate():
            logger.info("[.tikzon] Dry run validation PASSED. Environment is fully configured.")
            sys.exit(0)
        else:
            logger.error("[.tikzon] Dry run validation FAILED.")
            sys.exit(1)

    # Validate settings before executing tasks
    if not cfg.validate():
        logger.critical("[.tikzon] Configuration validation failed. Run with --dry-run for detailed issues.")
        sys.exit(1)

    # Handle manual approval
    if args.approve:
        approve_product(args.approve)
        sys.exit(0)

    # Override categories if passed
    if args.categories:
        cats = [c.strip() for c in args.categories.split(",")]
        cfg._scan_config["categories"] = cats
        logger.info(f"Overridden categories to scan: {cats}")

    # Handle daemon mode
    if args.daemon:
        scan_time = f"{cfg.SCAN_HOUR:02d}:{cfg.SCAN_MINUTE:02d}"
        logger.info(f"Starting scheduler loop. Runs daily scan at {scan_time} ({cfg.OPERATOR_TIMEZONE}).")
        
        # Schedule the daily scan
        schedule.every().day.at(scan_time).do(run_full_pipeline)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Scheduler daemon stopped by operator.")
            sys.exit(0)
    else:
        # Default behavior: run pipeline immediately
        run_full_pipeline(no_email=args.no_email)


if __name__ == "__main__":
    main()
