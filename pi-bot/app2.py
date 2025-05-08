#!/usr/bin/env python3
import json, time, asyncio, pytz, os, sys
from datetime import datetime
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset
from stellar_sdk.transaction_builder import TransactionBuilder as TB
from httpx import AsyncClient, Timeout, Limits

# ─── Determine resource paths ───────────────────────────────────────────────────
def get_base_dir():
    """Get the base directory for resources based on how the application is running"""
    if getattr(sys, 'frozen', False):
        # Running as compiled (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

# ─── Load config ───────────────────────────────────────────────────────────────
config_path = os.path.join(get_base_dir(), "config.json")
print(f"Looking for config file at: {config_path}")

try:
    with open(config_path, 'r') as f:
        cfg = json.load(f)
    print("✅ Config loaded successfully!")
except FileNotFoundError:
    print(f"❌ Config file not found at {config_path}")
    sys.exit(1)
except json.JSONDecodeError:
    print(f"❌ Config file found but contains invalid JSON")
    sys.exit(1)

MNEMONIC    = cfg["mnemonic"]
DESTINATION = cfg["destination"]
AMOUNT      = str(float(cfg["amount"]))
NETWORK     = cfg["network"].lower()
START_TIME  = datetime.strptime(cfg["start_time"], "%Y-%m-%d %H:%M:%S")
DURATION    = float(cfg["duration"])
CONCURRENCY = int(cfg["concurrency"])

IS_MAINNET  = NETWORK.startswith("pi main")
HORIZON     = "https://api.mainnet.minepi.com" if IS_MAINNET else "https://api.testnet.minepi.com"
PASSPHRASE  = "Pi Network" if IS_MAINNET else "Pi Testnet"

# ─── Helpers ───────────────────────────────────────────────────────────────────
lagos = pytz.timezone("Africa/Lagos")
def to_utc(dt): return lagos.localize(dt).astimezone(pytz.utc).timestamp()

def derive_master(mnemonic):
    seed = Bip39SeedGenerator(mnemonic).Generate()
    slip = Bip32Slip10Ed25519.FromSeed(seed)
    raw  = slip.DerivePath("m/44'/314159'/0'").PrivateKey().Raw().ToBytes()
    return Keypair.from_secret(StrKey.encode_ed25519_secret_seed(raw))

async def build_feebumped_xdr(server, kp, destination, amount, base_fee):
    acct = await asyncio.to_thread(server.load_account, kp.public_key)
    tx = (
        TransactionBuilder(
            source_account=acct,
            network_passphrase=PASSPHRASE,
            base_fee=base_fee,
        )
        .append_payment_op(destination, Asset.native(), amount)
        .set_timeout(30)
        .build()
    )
    tx.sign(kp)
    return tx.to_xdr()

# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    print(f"🔄 Connecting to {NETWORK}...")
    server  = Server(HORIZON)
    master  = derive_master(MNEMONIC)
    base_fee= server.fetch_base_fee()

    print(f"[{NETWORK.upper()}] {master.public_key} · fee={base_fee}")

    # setup two persistent HTTP/2 clients
    timeout = Timeout(30, connect=5, read=600, write=600)
    limits  = Limits(max_connections=CONCURRENCY * 2)
    reader  = AsyncClient(http2=True, timeout=timeout, limits=limits)
    writer  = AsyncClient(http2=True, timeout=timeout, limits=limits)
    
    
    # ensure HTTP/2 connection is ready before starting the flood
    await writer.get(f"{HORIZON}/transactions")  # Simple test request to ensure connection
    print("✅ HTTP/2 connection established.")

    # wait until start
    print(f"⏳ Scheduled start time: {START_TIME}")
    wait = to_utc(START_TIME) - time.time() - 4.0
    if wait > 0:
        print(f"⏳ Countdown: {wait:.2f}s until flood starts...")
        while wait > 0:
            print(f"⏳ Time remaining: {wait:.2f}s", end="\r")
            await asyncio.sleep(1.0)  
            wait = to_utc(START_TIME) - time.time()  # recalculate remaining time
        print()  # newline after countdown

    print(f"🚀 Launching flood: {CONCURRENCY} workers for {DURATION}s…")
    end = time.time() + DURATION

    # Track transaction count
    tx_count = 0
    success_count = 0
    error_count = 0

    async def worker(idx: int):
        nonlocal end, tx_count, success_count, error_count
        while time.time() < end:
            try:
                xdr = await build_feebumped_xdr(server, master, DESTINATION, AMOUNT, base_fee)
                res = await writer.post(f"{HORIZON}/transactions", data={"tx": xdr})
                if res.status_code == 200:
                    tx_count += 1
                    success_count += 1
                    print(f"[{idx}] ✅ {res.json().get('hash')}")
                else:
                    # retry instantly without logging
                    res2 = await writer.post(f"{HORIZON}/transactions", data={"tx": xdr})
                    if res2.status_code == 200:
                        tx_count += 1
                        success_count += 1
                        print(f"[{idx}] ✅(retry) {res2.json().get('hash')}")
                    else:
                        error_count += 1
                        print(f"[{idx}] ❌(retry) {res2.status_code}")
            except Exception as e:
                error_count += 1
                print(f"[{idx}] ⚠️ Error: {e}")

    # Start workers
    start_time = time.time()
    await asyncio.gather(*[worker(i+1) for i in range(CONCURRENCY)])

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    print(f"\n🎉 Flood complete!")
    print(f"Total transactions: {tx_count} ({success_count} successful, {error_count} failed)")
    print(f"Time elapsed: {elapsed_time:.2f}s")
    print(f"Transactions per second: {tx_count/elapsed_time:.2f}")

    await reader.aclose()
    await writer.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)