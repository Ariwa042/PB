#!/usr/bin/env python3
import json
from datetime import datetime

def prompt_non_empty(prompt_text):
    while True:
        val = input(prompt_text).strip()
        if val:
            return val
        print("This field is required.")

def get_config():
    print("🚀 Config Setup for Pi Transaction Flood Tool\n")

    mnemonic = prompt_non_empty("Enter your 24-word mnemonic: ")
    destination = prompt_non_empty("Enter destination wallet address: ")
    amount = prompt_non_empty("Enter amount to send: ")

    network = ""
    while network.lower() not in ["pi mainnet", "pi testnet"]:
        network = input("Enter network (Pi mainnet or Pi testnet): ")

    while True:
        start_time = input("Enter start time (YYYY-MM-DD HH:MM:SS): ").strip()
        try:
            datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Invalid format. Use YYYY-MM-DD HH:MM:SS.")

    duration = prompt_non_empty("Enter duration (in seconds): ")
    concurrency = prompt_non_empty("Enter concurrency (number of workers): ")

    return {
        "mnemonic": mnemonic,
        "destination": destination,
        "amount": amount,
        "network": network,
        "start_time": start_time,
        "duration": duration,
        "concurrency": concurrency
    }

def save_config(cfg, filename="config.json"):
    with open(filename, "w") as f:
        json.dump(cfg, f, indent=4)
    print(f"\n✅ Configuration saved to '{filename}'.")

if __name__ == "__main__":
    config_data = get_config()
    save_config(config_data)
