#!/usr/bin/env python3
"""
Weekly SEO scan push script.
Queries seo_urls table, runs audit + email for each registered URL.
Runs every Monday 09:00 UTC (or configured time).

Usage:
  python3 scripts/seo_weekly_push.py          # run once
  python3 scripts/seo_weekly_push.py --dry-run  # preview without sending
"""
import sys
import json
import time
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv

# Database path
BASE_DIR = Path(__file__).parent.parent
DATABASE_PATH = Path("/data/ziwei.db") if Path("/data").exists() else BASE_DIR / "data" / "ziwei.db"
API_URL = "http://127.0.0.1:8119"

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def main():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    
    # Get all active URLs that haven't been scanned in the last 7 days
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = conn.execute("""
        SELECT su.*, ak.balance, ak.active as key_active
        FROM seo_urls su
        JOIN api_keys ak ON ak.key = su.api_key
        WHERE su.active = 1 AND ak.active = 1
        AND (su.last_scan IS NULL OR su.last_scan < ?)
        ORDER BY su.last_scan ASC
    """, (week_ago,)).fetchall()
    
    if not rows:
        log("No URLs due for weekly scan.")
        conn.close()
        return
    
    log(f"Found {len(rows)} URL(s) due for scan:")
    
    results = {"sent": 0, "skipped": 0, "errors": 0, "details": []}
    
    for row in rows:
        key = row["api_key"]
        url = row["url"]
        balance = row["balance"]
        
        log(f"  → {url} (key: {key[:12]}..., balance: {balance})")
        
        if balance < 1:
            log(f"     ⏭ SKIP: insufficient balance ({balance})")
            results["skipped"] += 1
            results["details"].append({"url": url, "status": "skipped", "reason": "no balance"})
            continue
        
        if DRY_RUN:
            log(f"     📋 DRY RUN: would scan and email report")
            results["details"].append({"url": url, "status": "dry-run"})
            continue
        
        # Call the email-report API
        try:
            import urllib.request
            payload = json.dumps({"url": url, "key": key}).encode()
            req = urllib.request.Request(
                f"{API_URL}/v1/seo/email-report",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            
            if data.get("success"):
                log(f"     ✅ Sent — Score: {data.get('score')}, Balance: {data.get('balance')}")
                results["sent"] += 1
                results["details"].append({
                    "url": url, "status": "sent",
                    "score": data.get("score"),
                    "balance": data.get("balance")
                })
            else:
                log(f"     ❌ Failed: {data.get('error', 'unknown')}")
                results["errors"] += 1
                results["details"].append({
                    "url": url, "status": "error",
                    "error": data.get("error")
                })
        except Exception as e:
            log(f"     ❌ Error: {e}")
            results["errors"] += 1
            results["details"].append({"url": url, "status": "error", "error": str(e)})
        
        # Small delay between scans to avoid hammering
        time.sleep(2)
    
    conn.close()
    
    log(f"\nDone: {results['sent']} sent, {results['skipped']} skipped, {results['errors']} errors")
    
    # Write summary to a log file for debugging
    log_path = BASE_DIR / "data" / "seo_push_log.jsonl"
    with open(log_path, "a") as f:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "total": len(rows),
            **results
        }
        f.write(json.dumps(record) + "\n")

if __name__ == "__main__":
    main()
