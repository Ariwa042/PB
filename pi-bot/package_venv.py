#!/usr/bin/env python3
"""
Build script for Pi Transaction Flood Tool
This script:
1. Copies all necessary files to a build directory
2. Creates a main.py entry point
3. Runs PyInstaller to create a standalone executable
"""

import os
import sys
import shutil
import platform
import importlib.util
from pathlib import Path

# Check if PyInstaller is installed
try:
    from PyInstaller.__main__ import run as pyinstaller_run
except ImportError:
    print("❌ PyInstaller not found. Please install it with: pip install pyinstaller")
    sys.exit(1)

# Define paths
BUILD_DIR = "build_temp"
DIST_DIR = "dist"

def clean_directories():
    """Clean up build and dist directories"""
    print("🧹 Cleaning up previous builds...")
    for directory in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(directory):
            shutil.rmtree(directory)

def copy_files_to_build():
    """Copy all necessary files to the build directory"""
    print("📂 Copying files to build directory...")
    
    # Create build directory if it doesn't exist
    if not os.path.exists(BUILD_DIR):
        os.makedirs(BUILD_DIR)
    
    # Copy app2.py to the build directory
    if os.path.exists("app2_fixed.py"):
        shutil.copy2("app2_fixed.py", os.path.join(BUILD_DIR, "app2.py"))
        print("✅ Copied app2_fixed.py -> app2.py")
    elif os.path.exists("app2.py"):
        shutil.copy2("app2.py", os.path.join(BUILD_DIR, "app2.py"))
        print("✅ Copied app2.py")
    else:
        print("❌ app2.py not found")
        return False
    
    # Copy setup_config.py to the build directory
    if os.path.exists("setup_config_fixed.py"):
        shutil.copy2("setup_config_fixed.py", os.path.join(BUILD_DIR, "setup_config.py"))
        print("✅ Copied setup_config_fixed.py -> setup_config.py")
    elif os.path.exists("setup_config.py"):
        shutil.copy2("setup_config.py", os.path.join(BUILD_DIR, "setup_config.py"))
        print("✅ Copied setup_config.py")
    else:
        print("❌ setup_config.py not found")
        return False
    
    # Copy main.py to the build directory
    if os.path.exists("main.py"):
        shutil.copy2("main.py", os.path.join(BUILD_DIR, "main.py"))
        print("✅ Copied main.py")
    else:
        print("❌ main.py not found")
        return False
    
    # Copy requirements.txt to the build directory
    if os.path.exists("requirements.txt"):
        shutil.copy2("requirements.txt", os.path.join(BUILD_DIR, "requirements.txt"))
        print("✅ Copied requirements.txt")
    
    return True

def find_bip_utils_wordlists():
    """Find the bip_utils wordlist files using a more robust approach"""
    try:
        # Try to import bip_utils
        import bip_utils
        bip_path = os.path.dirname(bip_utils.__file__)
        wordlist_path = os.path.join(bip_path, 'bip', 'bip39', 'wordlist')
        
        if os.path.exists(wordlist_path):
            print(f"✅ Found bip_utils wordlist directory at: {wordlist_path}")
            wordlist_files = [
                os.path.join(wordlist_path, f)
                for f in os.listdir(wordlist_path)
                if f.endswith('.txt')
            ]
            return wordlist_path, wordlist_files
    except ImportError:
        print("⚠️ Cannot import bip_utils directly, trying to find it in site-packages...")
    
    # If we can't import it directly, search in site-packages
    try:
        # Find all potential Python paths
        python_paths = sys.path
        
        for path in python_paths:
            if not os.path.isdir(path):
                continue
                
            # Look for bip_utils directory
            bip_path = os.path.join(path, 'bip_utils')
            if os.path.isdir(bip_path):
                wordlist_path = os.path.join(bip_path, 'bip', 'bip39', 'wordlist')
                if os.path.exists(wordlist_path):
                    print(f"✅ Found bip_utils wordlist directory at: {wordlist_path}")
                    wordlist_files = [
                        os.path.join(wordlist_path, f)
                        for f in os.listdir(wordlist_path)
                        if f.endswith('.txt')
                    ]
                    return wordlist_path, wordlist_files
        
        # Try conda environments - specifically check the paths found in your error
        conda_paths = [
            "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist",
            "/home/zeus/miniconda3/envs/cloudspace/lib/python3.10/site-packages/bip_utils/bip/bip39/wordlist"
        ]
        
        for path in conda_paths:
            if os.path.exists(path):
                print(f"✅ Found bip_utils wordlist directory at: {path}")
                wordlist_files = [
                    os.path.join(path, f)
                    for f in os.listdir(path)
                    if f.endswith('.txt')
                ]
                return path, wordlist_files
    
    except Exception as e:
        print(f"⚠️ Error searching for bip_utils: {e}")
    
    print("⚠️ Warning: Could not find bip_utils wordlist directory")
    return None, []

def run_pyinstaller():
    """Run PyInstaller to create standalone executable"""
    print("🚀 Running PyInstaller...")
    
    # Define the PyInstaller command
    separator = ";" if platform.system() == "Windows" else ":"
    
    # Get wordlist files
    wordlist_path, wordlist_files = find_bip_utils_wordlists()
    datas = []
    
    if wordlist_path and wordlist_files:
        print(f"📚 Found {len(wordlist_files)} BIP39 wordlist files")
        
        # Create a hook file for bip_utils
        with open(os.path.join(BUILD_DIR, "hook-bip_utils.py"), "w") as f:
            f.write("from PyInstaller.utils.hooks import collect_data_files\n")
            f.write("datas = collect_data_files('bip_utils')\n")
        print("✅ Created PyInstaller hook for bip_utils")
        
        # Copy individual wordlist files directly to the build directory
        for wordlist_file in wordlist_files:
            # Get just the filename
            filename = os.path.basename(wordlist_file)
            # Create data file entry for each wordlist file
            datas.append(f"--add-data={wordlist_file}{separator}bip_utils/bip/bip39/wordlist")
            print(f"✅ Added {filename} to PyInstaller data files")
    else:
        print("⚠️ No BIP39 wordlist files found! The application might not work correctly.")
    
    # Change to the build directory
    os.chdir(BUILD_DIR)
    
    # Define PyInstaller command
    pyinstaller_cmd = [
        "main.py",
        "--name=PiFlood",
        "--onedir",
        "--add-data=setup_config.py{0}.".format(separator),
        "--add-data=app2.py{0}.".format(separator),
        "--additional-hooks-dir=.",
        "--clean",
        # Add common hidden imports
        "--hidden-import=stellar_sdk",
        "--hidden-import=bip_utils",
        "--hidden-import=bip_utils.bip.bip39.wordlist",
        "--hidden-import=pytz",
        "--hidden-import=httpx",
        "--hidden-import=asyncio",
        "--hidden-import=datetime",
        "--hidden-import=json",
        "--hidden-import=time",
        "--hidden-import=coincurve._cffi_backend",
    ]
    
    # Add data files
    pyinstaller_cmd.extend(datas)
    
    # Print the command for debugging
    print(f"⚙️ PyInstaller command: {' '.join(pyinstaller_cmd)}")
    
    # Run PyInstaller
    pyinstaller_run(pyinstaller_cmd)
    
    # Return to original directory
    os.chdir("..")
    
    # Check if build was successful
    if os.path.exists(os.path.join(DIST_DIR, "PiFlood")):
        print("\n✅ Build successful! Final files are in 'dist/PiFlood' folder")
        return True
    else:
        print("\n❌ Build failed! Check the errors above.")
        return False

def main():
    """Main function"""
    print("🛠️ Building Pi Transaction Flood Tool...")
    
    # Clean up previous builds
    clean_directories()
    
    # Copy files to build directory
    if not copy_files_to_build():
        print("❌ Failed to copy files to build directory.")
        return
    
    # Run PyInstaller
    if run_pyinstaller():
        # Clean up build directory
        if os.path.exists(BUILD_DIR):
            shutil.rmtree(BUILD_DIR)
        
        print("\n✅ Build complete!")
        print("You can find the executable in 'dist/PiFlood'.")
        print("You can zip this folder to distribute it.")
    else:
        print("\n❌ Build failed.")

if __name__ == "__main__":
    main()