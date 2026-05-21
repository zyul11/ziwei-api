#!/usr/bin/env python3
"""
USDT (TRC-20) Payment Monitor
Queries TronGrid every 2 minutes for incoming USDT transfers.
Auto-confirms matching pending orders from the API.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

# ─── Config ──────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8119"
USDT_WALLET = "TMVWYC7SYnDg5UVFuBGbMY1Q2PbpnaXPei"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT (TRC-20) mainnet
TRONGRID = "https://api.trongrid.io"
PROCESSED_FILE = "/home/ubuntu/ziwei-api/usdt_processed.json"
LOCK_FILE = "/tmp/check_usdt.lock"


def load_processed() -> set:
    """Load set of already-processed tx_hashes."""
    if not os.path.exists(PROCESSED_FILE):
        return set()
    try:
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        return set()


def save_processed(tx_hashes: set):
    """Persist processed tx_hashes."""
    with open(PROCESSED_FILE, "w") as f:
        json.dump(sorted(tx_hashes), f, indent=2)


def get_pending_orders() -> list:
    """Fetch pending USDT orders from the API."""
    try:
        resp = requests.get(f"{API_BASE}/v1/seo/pending-usdt-orders", timeout=10)
        data = resp.json()
        if data.get("success"):
            return data.get("data", [])
    except Exception as e:
        print(f"[usdt-mon] Failed to fetch pending orders: {e}")
    return []


def get_recent_transfers() -> list:
    """Fetch recent USDT TRC-20 transfers to our wallet from TronGrid."""
    try:
        params = {
            "limit": 50,
            "contract_address": USDT_CONTRACT,
            "only_to": True,
            "min_timestamp": int((datetime.now() - timedelta(hours=72)).timestamp() * 1000),
        }
        resp = requests.get(
            f"{TRONGRID}/v1/accounts/{USDT_WALLET}/transactions/trc20",
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[usdt-mon] TronGrid returned {resp.status_code}")
            return []
        return resp.json().get("data", [])
    except Exception as e:
        print(f"[usdt-mon] TronGrid error: {e}")
        return []


def confirm_order(order_id: str, tx_hash: str) -> bool:
    """Call the API to confirm a USDT payment."""
    try:
        resp = requests.post(
            f"{API_BASE}/v1/seo/confirm-usdt",
            json={"tx_hash": tx_hash, "order_id": order_id},
            timeout=15,
        )
        data = resp.json()
        if data.get("success"):
            key = data.get("data", {}).get("key", "?")
            print(f"[usdt-mon] ✅ Order {order_id} confirmed! Key: {key}")
            return True
        else:
            print(f"[usdt-mon] ❌ Confirm failed for {order_id}: {data.get('error')}")
            return False
    except Exception as e:
        print(f"[usdt-mon] ❌ Confirm error for {order_id}: {e}")
        return False


def main():
    # Prevent concurrent runs
    if os.path.exists(LOCK_FILE):
        age = time.time() - os.path.getmtime(LOCK_FILE)
        if age < 60:
            print("[usdt-mon] ⏳ Previous run still in progress (<60s), skipping")
            return
        else:
            print("[usdt-mon] ⚠️ Stale lock file, proceeding")
    open(LOCK_FILE, "w").close()

    try:
        processed = load_processed()
        orders = get_pending_orders()
        transfers = get_recent_transfers()

        print(f"[usdt-mon] 📊 Pending orders: {len(orders)}, Transfers: {len(transfers)}, "
              f"Already processed: {len(processed)}")

        for tx in transfers:
            tx_hash = tx.get("transaction_id", "")
            if not tx_hash or tx_hash in processed:
                continue

            # Parse amount (USDT has 6 decimals)
            try:
                amount = int(tx.get("value", "0")) / 1_000_000
            except (ValueError, TypeError):
                continue

            print(f"[usdt-mon] 🔍 Found transfer: {tx_hash[:16]}... ${amount:.2f}")

            # Find matching pending order
            matched = None
            for order in orders:
                expected = order.get("amount", 0)
                if abs(amount - expected) < 0.01:
                    matched = order
                    break

            if matched:
                oid = matched["order_id"]
                print(f"[usdt-mon] ✅ Matched order {oid} (${amount:.2f})")
                ok = confirm_order(oid, tx_hash)
                if ok:
                    processed.add(tx_hash)
                    save_processed(processed)
                # If confirm failed (e.g. already processed), still mark as done
                else:
                    err_check = requests.post(
                        f"{API_BASE}/v1/seo/confirm-usdt",
                        json={"tx_hash": tx_hash, "order_id": oid},
                        timeout=10,
                    ).json().get("error", "")
                    if "already processed" in err_check or "already used" in err_check:
                        processed.add(tx_hash)
                        save_processed(processed)
            else:
                print(f"[usdt-mon] ⏳ No matching order for ${amount:.2f} (tx: {tx_hash[:16]}...)")
                # Mark as processed after 24 hours even without match (prevent re-checking old tx)
                processed.add(tx_hash)
                save_processed(processed)

        # Clean old processed entries (keep last 1000)
        if len(processed) > 1000:
            processed = set(list(processed)[-1000:])
            save_processed(processed)

        print(f"[usdt-mon] ✅ Done. Total processed: {len(processed)}")

    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
