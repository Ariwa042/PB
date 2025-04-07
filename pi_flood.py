#!/usr/bin/env python3
import sys
import time
from datetime import datetime
import pytz
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset
from queue import Queue, Empty
import threading
import os
from mover.utils import time_function

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'pi-python')))
#from pi_python import PiNetwork

@time_function
def derive_strkey_seed(mnemonic: str) -> str:
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    slip = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    raw = slip.DerivePath("m/44'/314159'/0'").PrivateKey().Raw().ToBytes()
    return StrKey.encode_ed25519_secret_seed(raw)

@time_function
def parse_utc(dt_str: str) -> float:
    """Parse UTC datetime string and return a UTC timestamp."""
    try:
        # Parse the input time as UTC
        utc_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        utc_time = pytz.utc.localize(utc_time)  # Ensure it's treated as UTC
        return utc_time.timestamp()
    except Exception as e:
        raise ValueError(f"Invalid datetime format: {str(e)}")

@time_function
def build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount):
    acct = server.load_account(public_key)
    tx = (
        TransactionBuilder(
            source_account=acct,
            network_passphrase=net_choice,
            base_fee=base_fee
        )
        .append_payment_op(destination, Asset.native(), amount)
        .set_timeout(30)
        .build()
    )
    tx.sign(kp)
    return tx.to_xdr()

@time_function
def main():
    print("🔁 Pi Network P2P Flood Scheduler")
    mnemonic       = input("🧠 24‑word mnemonic: ").strip()
    destination    = input("📤 Destination G... address: ").strip()
    amount_str     = input("💰 Amount of Pi: ").strip()
    net_choice     = input("🌐 Network (Pi Testnet/Mainnet): ").strip()
    start_time_str = input("⏰ Submission start UTC (YYYY-MM-DD HH:MM:SS): ").strip()
    duration_str   = input("⏱ Flood duration (s): ").strip()
    batch_str      = input("🔄 Concurrent submissions: ").strip()

    try:
        amount     = str(float(amount_str))
        start_ts   = parse_utc(start_time_str)
        duration   = float(duration_str)
        batch_size = int(batch_str)
    except:
        sys.exit("❌ Invalid input")

    secret_seed = derive_strkey_seed(mnemonic)
    kp          = Keypair.from_secret(secret_seed)
    public_key  = kp.public_key
    print("✅ Derived secret seed and public key:", public_key)

    horizon_url = "https://api.mainnet.minepi.com" if net_choice.lower().startswith("pi main") else "https://api.testnet.minepi.com"
    server      = Server(horizon_url=horizon_url)

    try:
        server.load_account(public_key)
    except:
        sys.exit(f"❌ Account {public_key} not found or unfunded.")

    base_fee = server.fetch_base_fee()

    # Prebuild and presign initial batch
    queue = Queue()
    for _ in range(batch_size):
        xdr = build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount)
        queue.put(xdr)
    print(f"✅ Prebuilt and presigned {batch_size} transactions.")

    # Wait until 0.2s before start time
    now = time.time()
    submission_time = start_ts - 0.2
    if submission_time > now:
        print(f"⏳ Waiting {submission_time - now:.2f}s until submission window…")
        time.sleep(submission_time - now)
    else:
        print("⚠️ Start time is in the past; flooding immediately.")

    flood_end    = time.time() + duration
    attempts     = 0
    success_flag = threading.Event()
    seq_lock     = threading.Lock()

    def worker(thread_id):
        nonlocal attempts
        while not success_flag.is_set() and time.time() < flood_end:
            try:
                xdr = queue.get(timeout=0.1)
            except Empty:
                continue
            with seq_lock:
                attempts += 1
                attempt_no = attempts
            try:
                server.submit_transaction(xdr)
                print(f"✅ Thread {thread_id} attempt {attempt_no} succeeded")
                success_flag.set()
                break
            except Exception as e:
                print(f"❌ Thread {thread_id} attempt {attempt_no} failed: {e}")
                # Rebuild and requeue
                try:
                    new_xdr = build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount)
                    queue.put(new_xdr)
                except:
                    pass

    # Start worker threads
    threads = []
    for i in range(batch_size):
        t = threading.Thread(target=worker, args=(i+1,))
        t.start()
        threads.append(t)

    for t in threads:
        remaining = flood_end - time.time()
        if remaining > 0:
            t.join(timeout=remaining)

    elapsed = time.time() - (start_ts if start_ts>now else now)
    rate = attempts / elapsed if elapsed>0 else 0
    print(f"\n🔄 Flood complete. Attempts: {attempts}, Time: {elapsed:.2f}s, Rate: {rate:.2f} tx/s")
    if not success_flag.is_set():
        print("⚠️ All attempts failed.")

def run_scheduler(params, log_callback):
    """Wrapper function for Flask integration"""
    mnemonic = params['mnemonic']
    destination = params['destination']
    amount = str(float(params['amount']))
    net_choice = params['network']
    start_ts = parse_utc(params['scheduled_time'])  # Convert to UTC timestamp
    duration = float(params['duration'])
    batch_size = int(params['concurrency'])

    secret_seed = derive_strkey_seed(mnemonic)
    kp = Keypair.from_secret(secret_seed)
    public_key = kp.public_key

    log_callback(f"✅ Derived public key: {public_key}")

    horizon_url = "https://api.mainnet.minepi.com" if net_choice.lower().startswith("pi main") else "https://api.testnet.minepi.com"
    server = Server(horizon_url=horizon_url)

    try:
        server.load_account(public_key)
    except:
        sys.exit(f"❌ Account {public_key} not found or unfunded.")

    base_fee = server.fetch_base_fee()

    # Prebuild and presign initial batch
    queue = Queue()
    for _ in range(batch_size):
        xdr = build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount)
        queue.put(xdr)
    log_callback(f"✅ Prebuilt and presigned {batch_size} transactions.")

    # Wait until 0.2s before start time
    now = time.time()
    submission_time = start_ts - 0.2
    if submission_time > now:
        wait_time = submission_time - now
        log_callback(f"⏳ Waiting {wait_time:.2f}s until submission window…")
        time.sleep(wait_time)
    else:
        log_callback("⚠️ Start time is in the past; flooding immediately.")

    flood_end = time.time() + duration
    attempts = 0
    success_flag = threading.Event()
    seq_lock = threading.Lock()

    def worker(thread_id):
        nonlocal attempts
        while not success_flag.is_set() and time.time() < flood_end:
            try:
                xdr = queue.get(timeout=0.1)
            except Empty:
                continue
            with seq_lock:
                attempts += 1
                attempt_no = attempts
            try:
                server.submit_transaction(xdr)
                log_callback(f"✅ Thread {thread_id} attempt {attempt_no} succeeded")
                success_flag.set()
                break
            except Exception as e:
                log_callback(f"❌ Thread {thread_id} attempt {attempt_no} failed")
                # Rebuild and requeue
                try:
                    new_xdr = build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount)
                    queue.put(new_xdr)
                except:
                    pass

    # Start worker threads
    threads = []
    for i in range(batch_size):
        t = threading.Thread(target=worker, args=(i + 1,))
        t.start()
        threads.append(t)

    for t in threads:
        remaining = flood_end - time.time()
        if remaining > 0:
            t.join(timeout=remaining)

    elapsed = time.time() - (start_ts if start_ts > now else now)
    rate = attempts / elapsed if elapsed > 0 else 0
    log_callback(f"\n🔄 Flood complete. Attempts: {attempts}, Time: {elapsed:.2f}s, Rate: {rate:.2f} tx/s")
    if not success_flag.is_set():
        log_callback("⚠️ All attempts failed.")

if __name__ == "__main__":
    main()

#PI-SCHEDULAR.PY