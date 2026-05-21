# chronicforge.spec
# PyInstaller spec file for ChronicForge — onedir mode
# Run with: pyinstaller --clean chronicforge.spec
# Or simply: ./build.sh

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = os.path.abspath('.')

# Collect all SQLAlchemy submodules to avoid missing dialect errors at runtime
sqlalchemy_hidden = collect_submodules('sqlalchemy')

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('assets/sprites', 'assets/sprites'),
        ('voice_samples', 'voice_samples'),
    ],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.pool',
        'sqlalchemy.event',
        'PySide6.QtSvg',
        'PySide6.QtPrintSupport',
        'PySide6.QtOpenGL',
        'groq',
        'psutil',
        'pydub',
        'requests',
        'tomli_w',
    ] + sqlalchemy_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChronicForge',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChronicForge',
)
