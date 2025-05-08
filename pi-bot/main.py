#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

def setup_environment():
    """Set up the environment by ensuring config and proper dependencies"""
    # Always run setup_config to get fresh user input
    print("🔧 Running setup wizard...")
    try:
        import setup_config
        config_data = setup_config.get_config()
        setup_config.save_config(config_data)
    except ImportError:
        print("❌ Error: setup_config.py not found. Unable to create configuration.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error setting up configuration: {e}")
        sys.exit(1)
    
    # Import required packages
    try:
        import asyncio
        import pytz
        from bip_utils import Bip39SeedGenerator
        from stellar_sdk import Keypair
        import httpx
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install required packages using: pip install -r requirements.txt")
        sys.exit(1)
    
    return True

def run_transaction_flood():
    """Run the main transaction flood application"""
    # This function simply imports and runs the app2 module
    try:
        # First try importing as a module
        try:
            import app2
            import asyncio
            asyncio.run(app2.main())
        except ImportError:
            # If that fails, try running it as a script
            if os.path.exists('app2.py'):
                print("🚀 Running transaction flood from app2.py...")
                exec(open('app2.py').read())
            else:
                raise ImportError("app2.py not found")
    except Exception as e:
        print(f"❌ Error running transaction flood: {e}")
        sys.exit(1)

def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description='Pi Transaction Flood Tool')
    parser.add_argument('--setup-only', action='store_true', help='Run only the setup wizard without executing transactions')
    args = parser.parse_args()
    
    print("🚀 Pi Transaction Flood Tool")
    print("-" * 50)
    
    # Set up environment - always run setup first
    setup_environment()
    
    # If --setup-only flag is provided, exit after setup
    if args.setup_only:
        print("✅ Setup complete. Run without --setup-only to start the transaction flood.")
        return
    
    # Run the transaction flood
    print("▶️ Starting transaction flood based on the provided configuration...")
    run_transaction_flood()

if __name__ == "__main__":
    main()