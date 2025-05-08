# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['build_temp/main.py'],
    pathex=[],
    binaries=[],
    datas=[('setup_config.py', '.'), ('app2.py', '.'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/chinese_traditional.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/italian.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/korean.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/chinese_simplified.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/czech.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/portuguese.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/english.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/spanish.txt', 'bip_utils/bip/bip39/wordlist'), ('/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/bip_utils/bip/bip39/wordlist/french.txt', 'bip_utils/bip/bip39/wordlist')],
    hiddenimports=['stellar_sdk', 'bip_utils', 'bip_utils.bip.bip39.wordlist', 'pytz', 'httpx', 'asyncio', 'datetime', 'json', 'time', 'coincurve._cffi_backend'],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PiFlood',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PiFlood',
)
