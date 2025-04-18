#!/usr/bin/env python3
import sys
import time
import json
from datetime import datetime
import pytz
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset
from queue import Queue, Empty
import threading
from mover.utils import time_function

CONFIG_FILE = "config.json"

@time_function
def derive_strkey_seed(mnemonic: str) -> str:
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    slip = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    raw = slip.DerivePath("m/44'/314159'/0'").PrivateKey().Raw().ToBytes()
    return StrKey.encode_ed25519_secret_seed(raw)

@time_function
def parse_utc(dt_str: str) -> float:
    """Parse LOCAL datetime string and return a UTC timestamp."""
    local = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    local = pytz.timezone("Africa/Lagos").localize(local)
    return local.astimezone(pytz.utc).timestamp()

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

    # Load config from JSON
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except Exception as e:
        sys.exit(f"❌ Failed to load config: {e}")

    try:
        mnemonic       = config["mnemonic"].strip()
        destination    = config["destination"].strip()
        amount         = str(float(config["amount"]))
        net_choice     = config["network"].strip()
        start_time_str = config["start_time"].strip()
        duration       = float(config["duration"])
        batch_size     = int(config["concurrency"])
    except KeyError as e:
        sys.exit(f"❌ Missing key in config: {e}")
    except Exception:
        sys.exit("❌ Invalid config values")

    start_ts = parse_utc(start_time_str)
    secret_seed = derive_strkey_seed(mnemonic)
    kp = Keypair.from_secret(secret_seed)
    public_key = kp.public_key
    print("✅ Derived secret seed and public key:", public_key)

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
    print(f"✅ Prebuilt and presigned {batch_size} transactions.")

    now = time.time()
    submission_time = start_ts - 0.2
    if submission_time > now:
        print(f"⏳ Waiting {submission_time - now:.2f}s until submission window…")
        time.sleep(submission_time - now)
    else:
        print("⚠️ Start time is in the past; flooding immediately.")

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
                print(f"✅ Thread {thread_id} attempt {attempt_no} succeeded")
                success_flag.set()
                break
            except Exception as e:
                print(f"❌ Thread {thread_id} attempt {attempt_no} failed: {e}")
                try:
                    new_xdr = build_signed_xdr(server, public_key, kp, net_choice, base_fee, destination, amount)
                    queue.put(new_xdr)
                except:
                    pass

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
    print(f"\n🔄 Flood complete. Attempts: {attempts}, Time: {elapsed:.2f}s, Rate: {rate:.2f} tx/s")
    if not success_flag.is_set():
        print("⚠️ All attempts failed.")

if __name__ == "__main__":
    main()
