#!/usr/bin/env python3
import sys
import time
import json
import pytz
import requests
from datetime import datetime
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import (
    Keypair, Server, TransactionBuilder, StrKey, Asset, TransactionEnvelope
)
from stellar_sdk.exceptions import NotFoundError
from queue import Queue, Empty
import threading

CONFIG_FILE = "config.json"

def derive_strkey_seed(mnemonic: str) -> str:
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    slip = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    raw = slip.DerivePath("m/44'/314159'/0'").PrivateKey().Raw().ToBytes()
    return StrKey.encode_ed25519_secret_seed(raw)

def parse_utc(dt_str: str) -> float:
    local = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    local = pytz.timezone("Africa/Lagos").localize(local)
    return local.astimezone(pytz.utc).timestamp()

def build_signed_xdr(server, public_key, kp, passphrase, base_fee, destination, amount):
    acct = server.load_account(public_key)
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
    return tx.to_xdr()

def main():
    print("🔁 Pi Network P2P Flood Scheduler\n")

    cfg = json.load(open(CONFIG_FILE))
    mnemonic    = cfg["mnemonic"]
    destination = cfg["destination"]
    amount      = str(float(cfg["amount"]))
    network     = cfg["network"]
    start_time  = cfg["start_time"]
    duration    = float(cfg["duration"])
    concurrency = int(cfg["concurrency"])

    is_mainnet = network.lower().startswith("pi main")
    # <<< Use Pi’s passphrases, not Stellar’s defaults >>>
    passphrase = "Pi Network" if is_mainnet else "Pi Testnet"
    horizon    = "https://api.mainnet.minepi.com" if is_mainnet else "https://api.testnet.minepi.com"
    server     = Server(horizon)

    # Derive and confirm keypair
    secret = derive_strkey_seed(mnemonic)
    kp     = Keypair.from_secret(secret)
    pubkey = kp.public_key
    print("✅ Derived Keypair:")
    print("   Secret Seed:", secret)
    print("   Public Key:", pubkey)

    # Verify account exists
    try:
        resp = server.accounts().account_id(pubkey).call()
    except NotFoundError:
        sys.exit(f"❌ Account {pubkey} not found or unfunded.")

    # Confirm signer
    if not any(s["key"] == pubkey for s in resp["signers"]):
        sys.exit("❌ Derived public key is not a signer on the account!")

    print("✅ Public key confirmed as account signer.")

    base_fee = server.fetch_base_fee()

    # Prebuild for testnet
    q = Queue()
    if not is_mainnet:
        for _ in range(concurrency):
            q.put(build_signed_xdr(server, pubkey, kp, passphrase, base_fee, destination, amount))
        print(f"✅ Prebuilt {concurrency} transactions for testnet\n")

    # Wait until just before start
    start_ts = parse_utc(start_time)
    delay    = start_ts - time.time() - 0.2
    if delay > 0:
        print(f"⏳ Waiting {delay:.2f}s until submission…\n")
        time.sleep(delay)
    else:
        print("⚠️ Submission time is in the past; flooding immediately\n")

    end_ts   = time.time() + duration
    attempts = 0
    success  = threading.Event()
    seq_lock = threading.Lock()

    def worker(idx):
        nonlocal attempts
        while not success.is_set() and time.time() < end_ts:
            try:
                if is_mainnet:
                    with seq_lock:
                        xdr = build_signed_xdr(server, pubkey, kp, passphrase, base_fee, destination, amount)
                else:
                    xdr = q.get(timeout=0.1)
                env = TransactionEnvelope.from_xdr(xdr, passphrase)
            except Empty:
                continue
            except Exception as e:
                print(f"❌ Thread {idx} build error: {e}")
                continue

            with seq_lock:
                attempts += 1
                n = attempts

            try:
                resp = server.submit_transaction(env)
                print(f"✅ Thread {idx} attempt {n} succeeded: {resp['hash']}")
                success.set()
                return
            except Exception as e:
                # print Horizon error details
                if hasattr(e, "response"):
                    try:
                        print(json.dumps(e.response.json(), indent=2))
                    except:
                        print(e)
                else:
                    print(e)

                # re-queue on testnet
                if not is_mainnet:
                    q.put(build_signed_xdr(server, pubkey, kp, passphrase, base_fee, destination, amount))

    # Start threads
    threads = []
    for i in range(concurrency):
        t = threading.Thread(target=worker, args=(i+1,))
        t.start()
        threads.append(t)

    for t in threads:
        rem = end_ts - time.time()
        if rem > 0:
            t.join(timeout=rem)

    elapsed = time.time() - max(start_ts, time.time() - duration)
    rate    = attempts / elapsed if elapsed > 0 else 0
    print(f"\n🔄 Flood complete. Attempts: {attempts}, Time: {elapsed:.2f}s, Rate: {rate:.2f} tx/s")
    if not success.is_set():
        print("⚠️ All attempts failed.")

if __name__ == "__main__":
    main()
