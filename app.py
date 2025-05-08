#!/usr/bin/env python3
import json, time, pytz, asyncio
from datetime import datetime
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import (
    Keypair, Server, TransactionBuilder, StrKey,
    Asset, Account
)
from stellar_sdk.transaction_builder import TransactionBuilder as TB
from httpx import AsyncClient, Timeout, Limits

# ─── Load config ───────────────────────────────────────────────────────────────
cfg         = json.load(open("config.json"))
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

# ─── Build & fee-bump one payment TX and return envelope XDR ──────────────────
async def build_feebumped_xdr(server, kp, destination, amount, base_fee):
    # fetch current sequence
    acct = await asyncio.to_thread(server.load_account, kp.public_key)
    # build inner payment
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
    # fee-bump
    fb = TB.build_fee_bump_transaction(
        fee_source=kp.public_key,
        base_fee=base_fee * 2,
        inner_transaction_envelope=tx,
        network_passphrase=PASSPHRASE
    )
    fb.sign(kp)
    return fb.to_xdr()

# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    server  = Server(HORIZON)
    master  = derive_master(MNEMONIC)
    base_fee= server.fetch_base_fee()

    print(f"[{NETWORK.upper()}] {master.public_key} · fee={base_fee}")

    # wait for at least one base reserve
    reserve = 0.5 * 2
    while True:
        bal = float(
            next(b for b in server.accounts()
                     .account_id(master.public_key).call()["balances"]
                 if b["asset_type"]=="native")["balance"]
        )
        if bal >= reserve * CONCURRENCY:
            break
        print(f"Waiting balance {bal:.2f}/{reserve*CONCURRENCY:.2f}…")
        await asyncio.sleep(1)

    # two persistent HTTP/2 clients
    timeout = Timeout(60, connect=5, read=60, write=30)
    limits  = Limits(max_connections=CONCURRENCY*2)
    reader  = AsyncClient(http2=True, timeout=timeout, limits=limits)
    writer  = AsyncClient(http2=True, timeout=timeout, limits=limits)

    # wait until start
    wait = to_utc(START_TIME) - time.time()
    if wait>0:
        await asyncio.sleep(wait)

    print(f"🚀 Launching flood: {CONCURRENCY} concurrent streams for {DURATION}s…")
    end = time.time()+DURATION

    async def worker(idx:int):
        nonlocal end
        while time.time()<end:
            # build fee-bumped XDR via reader’s connection
            xdr = await build_feebumped_xdr(server, master, DESTINATION, AMOUNT, base_fee)
            # submit via writer’s connection
            res = await writer.post(f"{HORIZON}/transactions", data={"tx":xdr})
            if res.status_code==200:
                print(f"[{idx}] ✅ {res.json().get('hash')}")
            else:
                # retry once on failure
                res2 = await writer.post(f"{HORIZON}/transactions", data={"tx":xdr})
                if res2.status_code==200:
                    print(f"[{idx}] ✅(retry) {res2.json().get('hash')}")
                else:
                    print(f"[{idx}] ❌ {res2.status_code}")

    await asyncio.gather(*[worker(i+1) for i in range(CONCURRENCY)])
    await reader.aclose()
    await writer.aclose()

    print("🎉 Flood complete")

if __name__=="__main__":
    asyncio.run(main())
