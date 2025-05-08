#!/usr/bin/env python3
import json, time, asyncio, pytz
from datetime import datetime
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset
from stellar_sdk.transaction_builder import TransactionBuilder as TB
from httpx import AsyncClient, Timeout, Limits

# ─── Load config ───────────────────────────────────────────────────────────────
cfg = json.load(open("config.json"))
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
    server  = Server(HORIZON)
    master  = derive_master(MNEMONIC)
    base_fee= server.fetch_base_fee()

    print(f"[{NETWORK.upper()}] {master.public_key} · fee={base_fee}")

    # wait until balance is ready
    reserve = 0.5 * 2
    
    # setup two persistent HTTP/2 clients
    timeout = Timeout(30, connect=5, read=600, write=600)
    limits  = Limits(max_connections=CONCURRENCY * 2)
    reader  = AsyncClient(http2=True, timeout=timeout, limits=limits)
    writer  = AsyncClient(http2=True, timeout=timeout, limits=limits)
    
    
    # ensure HTTP/2 connection is ready before starting the flood
    await writer.get(f"{HORIZON}/transactions")  # Simple test request to ensure connection
    print("✅ HTTP/2 connection established.")

#    while True:
#        try:
#            bal = float(
#                next(b for b in server.accounts()
#                         .account_id(master.public_key).call()["balances"]
#                     if b["asset_type"]=="native")["balance"]
#            )
#            if bal >= reserve * CONCURRENCY:
#                break
#            print(f"⏳ Waiting for balance: {bal:.2f}/{reserve*CONCURRENCY:.2f}…")
#        except Exception as e:
#            print(f"Error fetching balance: {e}")
#        await asyncio.sleep(1)



    # wait until start
    wait = to_utc(START_TIME) - time.time() - 4.0
    while wait > 0:
        print(f"⏳ Countdown: {wait:.2f}s until flood starts...")
        await asyncio.sleep(1.0)  # reducing delay to check every 0.1s
        wait = to_utc(START_TIME) - time.time()  # recalculate remaining time

    print(f"🚀 Launching flood: {CONCURRENCY} workers for {DURATION}s…")
    end = time.time() + DURATION

    # Track transaction count
    tx_count = 0

    async def worker(idx: int):
        nonlocal end, tx_count
        while time.time() < end:
            try:
                xdr = await build_feebumped_xdr(server, master, DESTINATION, AMOUNT, base_fee)
                res = await writer.post(f"{HORIZON}/transactions", data={"tx": xdr})
                if res.status_code == 200:
                    tx_count += 1
                    print(f"[{idx}] ✅ {res.json().get('hash')}")
                else:
                    # retry instantly without logging
                    res2 = await writer.post(f"{HORIZON}/transactions", data={"tx": xdr})
                    if res2.status_code == 200:
                        tx_count += 1
                        print(f"[{idx}] ✅(retry) {res2.json().get('hash')}")
                    else:
                        print(f"[{idx}] ❌(retry) {res2.status_code}")
            except Exception as e:
                print(f"[{idx}] ⚠️ Error: {e}")

    # Start workers
    start_time = time.time()
    await asyncio.gather(*[worker(i+1) for i in range(CONCURRENCY)])

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    print(f"\n🎉 Flood complete! Total transactions: {tx_count} | Time elapsed: {elapsed_time:.2f}s")

    await reader.aclose()
    await writer.aclose()

if __name__ == "__main__":
    asyncio.run(main())
