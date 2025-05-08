#!/usr/bin/env python3
import json, time, pytz, asyncio
from datetime import datetime
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset, Account
from stellar_sdk.transaction_builder import TransactionBuilder as TB
from httpx import AsyncClient, Timeout, Limits

# ─── Load Config ────────────────────────────────────────────────────────────
cfg            = json.load(open("bomber.json"))
NETWORK        = cfg["network"].lower()
MNEMONIC       = cfg["mnemonic"]
DESTINATION    = cfg["destination"]
START_TIME     = datetime.strptime(cfg["start_time"], "%Y-%m-%d %H:%M:%S")
CHANNEL_COUNT  = int(cfg["channel_count"])
CHANNEL_FUND   = float(cfg["channel_fund_pi"])
FLOOD_AMOUNT   = cfg["flood_amount_pi"]
FEE_MULTIPLIER = int(cfg["master_fee_multiplier"])

HORIZON, PASSPHRASE = (
    ("https://api.mainnet.minepi.com", "Pi Network")
    if NETWORK == "mainnet"
    else ("https://api.testnet.minepi.com", "Pi Testnet")
)

lagos = pytz.timezone("Africa/Lagos")
def to_utc(dt): return lagos.localize(dt).astimezone(pytz.utc).timestamp()

def derive(i):
    seed = Bip39SeedGenerator(MNEMONIC).Generate()
    slip = Bip32Slip10Ed25519.FromSeed(seed)
    raw  = slip.DerivePath(f"m/44'/314159'/{i}'").PrivateKey().Raw().ToBytes()
    return Keypair.from_secret(StrKey.encode_ed25519_secret_seed(raw))

async def main():
    server   = Server(HORIZON)
    master   = derive(0)
    base_fee = await asyncio.to_thread(server.fetch_base_fee)
    flood_fee = base_fee * FEE_MULTIPLIER

    print(f"[{NETWORK.upper()}] Master: {master.public_key} | base_fee={base_fee} flood_fee={flood_fee}")

    # 1) Wait for sufficient balance
    reserve = 0.5
    needed  = CHANNEL_COUNT * (CHANNEL_FUND + 2*reserve)
    while True:
        bal = float(next(
            b["balance"] for b in server.accounts()
                                  .account_id(master.public_key)
                                  .call()["balances"]
            if b["asset_type"]=="native"
        ))
        if bal >= needed:
            print(f"✅ Balance OK: {bal:.2f} ≥ {needed:.2f}")
            break
        print(f"⏳ Waiting for balance… {bal:.2f}/{needed:.2f}")
        await asyncio.sleep(1)

    # 2) Determine which channels are *new*
    channels    = [derive(i+1) for i in range(CHANNEL_COUNT)]
    new_channels = []
    for ch in channels:
        try:
            await asyncio.to_thread(server.load_account, ch.public_key)
        except:
            new_channels.append(ch)
    print(f"📡 New channels to fund: {len(new_channels)}")

    # 3) Fund new channels
    funded = []
    timeout = Timeout(30.0)
    limits  = Limits(max_connections=len(new_channels)*2 or 1)
    async with AsyncClient(http2=True, timeout=timeout, limits=limits) as client:
        if new_channels:
            # Build a single multi-op TX if there are any new
            master_acct = await asyncio.to_thread(server.load_account, master.public_key)
            tb = TransactionBuilder(master_acct, PASSPHRASE, base_fee)
            for ch in new_channels:
                tb.append_create_account_op(ch.public_key, f"{CHANNEL_FUND:.7f}")
            tx = tb.build()
            tx.sign(master)
            r = await client.post(f"{HORIZON}/transactions", data={"tx":tx.to_xdr()})
            if r.status_code == 200:
                print("✅ Bulk fund succeeded")
                funded = new_channels.copy()
            else:
                print("❌ Bulk fund failed, status:", r.status_code, r.text[:100])
        # If bulk didn't work or no new channels, fallback individually
        if not funded and new_channels:
            for ch in new_channels:
                for _ in range(3):
                    acct = await asyncio.to_thread(server.load_account, master.public_key)
                    tx   = (
                        TransactionBuilder(acct, PASSPHRASE, base_fee)
                        .append_create_account_op(ch.public_key, f"{CHANNEL_FUND:.7f}")
                        .build()
                    )
                    tx.sign(master)
                    r = await client.post(f"{HORIZON}/transactions", data={"tx":tx.to_xdr()})
                    if r.status_code==200:
                        print(f"✅ Funded: {ch.public_key[-6:]}")
                        funded.append(ch)
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise RuntimeError(f"Failed to fund {ch.public_key}")

    # 4) Pre-build flood payments
    flood_xdrs = []
    now = int(time.time())
    for ch in channels:
        acct = await asyncio.to_thread(server.load_account, ch.public_key)
        t = (
            TransactionBuilder(Account(ch.public_key, acct.sequence),
                               PASSPHRASE, flood_fee)
            .append_payment_op(DESTINATION, Asset.native(), FLOOD_AMOUNT)
            .set_timeout(30)
            .build()
        )
        t.sign(ch)
        flood_xdrs.append(t.to_xdr())

    # 5) Wait until START_TIME
    wait = to_utc(START_TIME) - time.time()
    if wait>0:
        print(f"⏳ Sleeping {wait:.1f}s until flood…")
        await asyncio.sleep(wait)
    else:
        print("🕒 START_TIME passed; flooding now")

    # 6) Dispatch all floods in parallel
    print(f"🚀 Launching {len(flood_xdrs)} flood TXs…")
    t0 = time.perf_counter()
    async with AsyncClient(http2=True, timeout=timeout, limits=limits) as client:
        results = await asyncio.gather(*[
            client.post(f"{HORIZON}/transactions", data={"tx": x})
            for x in flood_xdrs
        ], return_exceptions=True)

    for i, r in enumerate(results, 1):
        if isinstance(r, Exception):
            print(f"[{i}] ✗ Exception:", r)
        else:
            print(f"[{i}] {r.status_code}", 
                  r.json().get("hash", r.text)[:64])

    print(f"🎉 Completed in {(time.perf_counter()-t0)*1000:.1f} ms")

if __name__=="__main__":
    asyncio.run(main())
