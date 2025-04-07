#!/usr/bin/env python3
import sys
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
from stellar_sdk import Keypair, Server, TransactionBuilder, StrKey, Asset

# Point at your local pi-python folder
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'pi-python')))
from pi_python import PiNetwork

def derive_strkey_seed(mnemonic: str) -> str:
    # 1) BIP39 mnemonic → 64-byte seed
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    # 2) SLIP‑10 ed25519 derive at Pi path
    slip = Bip32Slip10Ed25519.FromSeed(seed_bytes)
    raw = slip.DerivePath("m/44'/314159'/0'").PrivateKey().Raw().ToBytes()
    # 3) Encode to Stellar StrKey (starts with “S…”)
    return StrKey.encode_ed25519_secret_seed(raw)

def main():
    print("🔁 Pi Network P2P Transfer")
    mnemonic    = input("🧠 24‑word mnemonic: ").strip()
    destination = input("📤 Destination G... address: ").strip()
    amount_str  = input("💰 Amount of Pi: ").strip()
    net_choice  = input("🌐 Network (Pi Testnet/Mainnet): ").strip()

    # parse amount
    try:
        amount = str(float(amount_str))
    except:
        print("❌ Invalid amount."); sys.exit(1)

    # Derive the secret seed & keypair
    print("🔐 Deriving secret seed from mnemonic…")
    try:
        secret_seed = derive_strkey_seed(mnemonic)
        kp          = Keypair.from_secret(secret_seed)
        public_key  = kp.public_key
        print("✅ Secret seed:", secret_seed)
        print("📬 Public key:", public_key)
    except Exception as e:
        print("❌ Derivation error:", e); sys.exit(1)

    # Initialize Pi SDK (optional, for other SDK calls)
    # pi = PiNetwork()
    # pi.initialize(api_key, secret_seed, net_choice)

    # Connect to Pi’s Horizon
    horizon_url = (
        "https://api.mainnet.minepi.com" if net_choice.lower().startswith("pi main")
        else "https://api.testnet.minepi.com"
    )
    server = Server(horizon_url=horizon_url)

    # Check account exists
    try:
        acct = server.load_account(public_key)
    except Exception:
        print(f"❌ Account {public_key} not found or unfunded. Fund it first."); sys.exit(1)

    # Build transaction using Pi’s own passphrase (net_choice)
    print("🚀 Building transaction…")
    base_fee = server.fetch_base_fee()
    print(f"ℹ️ Recommended base fee: {base_fee}")

    tx = (
        TransactionBuilder(
            source_account=acct,
            network_passphrase=net_choice,   # Use Pi Network passphrase!
            base_fee=base_fee
        )
        .append_payment_op(destination, Asset.native(), amount)
        .set_timeout(30)
        .build()
    )

    # Sign with the same keypair
    print("🔑 Signing transaction…")
    tx.sign(kp)
    print("✅ Transaction signed.")

    # Submit
    print("📤 Submitting…")
    try:
        res = server.submit_transaction(tx)
        print("✅ Success! Transaction hash:", res["hash"])
    except Exception as e:
        # Show the Horizon result codes if available
        try:
            extras = e.response.json().get("extras", {})
            print("❌ Submission failed:", extras.get("result_codes", {}))
        except:
            print("❌ Submission failed:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
#TRANSFER TO WALLET SCRIPT