# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('prompts', 'prompts'), ('assets', 'assets'), ('default.txt', '.')],
    hiddenimports=['AppKit', 'Quartz', 'ApplicationServices'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pynput', 'pystray', 'pyautogui'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KPrompter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KPrompter',
)
app = BUNDLE(
    coll,
    name='KPrompter.app',
    icon='assets/icon.icns',
    bundle_identifier='com.ktorres.kprompter',
)
