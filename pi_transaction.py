#!/usr/bin/env python3
import json
import sys
import time
import threading
from datetime import datetime, timedelta

import pytz
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import (
    Asset,
    Keypair,
    Network,
    Server,
    StrKey,
    TransactionBuilder,
)

CONFIG_FILE = "config.json"

def derive_strkey_seed(mnemonic: str) -> str:
    # 1) BIP39 → 64-byte seed
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    # 2) SLIP‑10 ed25519 at Pi path
    slip = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    raw = slip.DerivePath("m/44'/314159'/0'") \
             .PrivateKey().Raw().ToBytes()
    # 3) Encode to Stellar/StrKey secret seed
    return StrKey.encode_ed25519_secret_seed(raw)

def parse_local_to_utc(ts: str) -> float:
    # input is local Nigeria time → convert to UTC timestamp
    local = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    local = pytz.timezone("Africa/Lagos").localize(local)
    return local.astimezone(pytz.utc).timestamp()

def main():
    # load config
    try:
        cfg = json.load(open(CONFIG_FILE))
    except Exception as e:
        sys.exit(f"❌ Could not open {CONFIG_FILE}: {e}")

    try:
        mnemonic    = cfg["mnemonic"]
        destination = cfg["destination"]
        amount      = str(float(cfg["amount"]))
        network     = cfg["network"]
        start_time  = cfg["start_time"]
        duration    = float(cfg["duration"])
        concurrency = int(cfg["concurrency"])
    except KeyError as e:
        sys.exit(f"❌ Missing key in config: {e}")
    except Exception:
        sys.exit("❌ Invalid config values")

    # choose horizon & passphrase
    is_main = network.lower().startswith("pi main")
    horizon = "https://api.mainnet.minepi.com" if is_main else "https://api.testnet.minepi.com"
    passphrase = Network.PUBLIC_NETWORK_PASSPHRASE if is_main else Network.TESTNET_NETWORK_PASSPHRASE

    # derive keypair
    secret_seed = derive_strkey_seed(mnemonic)
    kp = Keypair.from_secret(secret_seed)
    pub = kp.public_key

    print("🔁 Pi Network P2P Flood Scheduler")
    print("✅ Derived keypair. Public key:", pub)

    # set up server
    server = Server(horizon_url=horizon)
    try:
        server.load_account(pub)
    except Exception:
        sys.exit(f"❌ Account {pub} not found or unfunded.")

    # compute timings
    start_ts = parse_local_to_utc(start_time)
    now      = time.time()
    wait_for = start_ts - now - 0.2  # fire .2s early
    if wait_for > 0:
        print(f"⏳ Waiting {wait_for:.2f}s until submission window…")
        time.sleep(wait_for)
    else:
        print("⚠️ Submission time is in the past; starting immediately")

    end_ts = time.time() + duration
    attempts = 0
    success  = threading.Event()
    lock     = threading.Lock()

    def worker(idx: int):
        nonlocal attempts
        while not success.is_set() and time.time() < end_ts:
            try:
                # always reload account to bump sequence
                acct    = server.load_account(pub)
                base_fee= server.fetch_base_fee()
                tx = (
                    TransactionBuilder(
                        source_account=acct,
                        network_passphrase=passphrase,
                        base_fee=base_fee
                    )
                    .append_payment_op(destination, Asset.native(), amount)
                    .set_timeout(30)
                    .build()
                )
                tx.sign(kp)

                with lock:
                    attempts += 1
                    n = attempts

                resp = server.submit_transaction(tx)
                print(f"✅ Thread {idx} attempt {n} succeeded: {resp['hash']}")
                success.set()
                return

            except Exception as e:
                with lock:
                    attempts += 1
                    n = attempts
                msg = getattr(e, "response", None)
                if msg:
                    try:
                        err = e.response.json()
                        print(f"❌ Thread {idx} attempt {n} failed, payload:\n{json.dumps(err, indent=2)}")
                    except:
                        print(f"❌ Thread {idx} attempt {n} failed: {e}")
                else:
                    print(f"❌ Thread {idx} attempt {n} failed: {e}")
                # retry immediately

    print(f"🌊 Flooding for {duration:.2f}s with {concurrency} threads…")
    threads = [threading.Thread(target=worker, args=(i+1,)) for i in range(concurrency)]
    for t in threads: t.start()
    for t in threads:
        remaining = end_ts - time.time()
        if remaining > 0:
            t.join(timeout=remaining)

    elapsed = (time.time() - start_ts) if start_ts>now else (time.time() - now)
    rate    = attempts/elapsed if elapsed>0 else 0
    print(f"\n🔄 Flood complete. Attempts: {attempts}, Time: {elapsed:.2f}s, Rate: {rate:.2f} tx/s")
    if not success.is_set():
        print("⚠️ All attempts failed.")

if __name__ == "__main__":
    main()
