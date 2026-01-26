# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/gcse_toolkit/gui_v2/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/gcse_toolkit/gui_v2/styles/logo.png', 'gcse_toolkit/gui_v2/styles'),
        ('src/gcse_toolkit/gui_v2/styles/icons', 'gcse_toolkit/gui_v2/styles/icons'),
        ('src/gcse_toolkit/plugins', 'gcse_toolkit/plugins'),
        ('build_resources/logo.icns', '.'),
        ('pyproject.toml', '.'),
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'fitz',  # PyMuPDF
        'yaml',
        'sklearn',
        'sklearn.linear_model',
        'sklearn.linear_model._logistic',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'torch',
        'transformers',
        'pytest',
        'tkinter',
        'notebook',
        'ipython',
        'setuptools',
        'distutils',
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
    name='GCSE Test Builder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,  # Critical: True causes macOS argument parsing issues
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='build_resources/logo.icns',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GCSE Test Builder',
)
app = BUNDLE(
    coll,
    name='GCSE Test Builder.app',
    icon='build_resources/logo.icns',
    bundle_identifier='com.gcsetestbuilder.gui',
)
