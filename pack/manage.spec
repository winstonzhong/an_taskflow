# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs


current_file = sys.argv[0]
BASE_DIR = Path(current_file).resolve().parent.parent
sys.path.append(str(BASE_DIR))

CAIDAO_DIR = BASE_DIR.parent / 'caidao'
print('CAIDAO_DIR', CAIDAO_DIR)

hidden_import_list = [
    'database_router',
    'requests',
]

hidden_import_list += collect_submodules('django.contrib.staticfiles')
hidden_import_list += collect_submodules('django.contrib.admin')
hidden_import_list += collect_submodules('django.contrib.auth')
hidden_import_list += collect_submodules('django.contrib.contenttypes')
hidden_import_list += collect_submodules('django.contrib.sessions')
hidden_import_list += collect_submodules('django.contrib.messages')
hidden_import_list += collect_submodules('django.db.backends')
hidden_import_list += collect_submodules('corsheaders')

# hidden_import_list += collect_submodules('cryptography')

# hidden_import_list += collect_submodules('pandas')
# hidden_import_list += collect_submodules('numpy')

# datas = collect_data_files('pandas') + collect_data_files('numpy')
binaries = collect_dynamic_libs('numpy')
hidden_import_list += ['numpy', 'numpy.core._multiarray_umath']  # 显式导入缺失模块
# binaries = [('.venv/Lib/site-packages/numpy/.libs/*', 'numpy/.libs')]  # 包含动态库
# binaries = []
datas = []

binaries += [
    # ('/data/data/com.termux/files/usr/lib/libexpat.so.1', '.'),
    # ('/data/data/com.termux/files/usr/lib/libsqlite3.so', '.'),
    # ('/data/data/com.termux/files/usr/lib/libffi.so', '.'),
    # ('/data/data/com.termux/files/usr/lib/python3.12/site-packages/numpy/core/_multiarray_umath.cpython-312.so', '.'),
    # ('', '.'),
    # ('', '.'),
    # ('', '.'),
    # ('', '.'),







]




a = Analysis(
    ['../manage.py'],
    pathex=[CAIDAO_DIR, '../'],
    binaries=binaries,  # 格式: (来源目录, 目标目录), 根据实际情况修改来源目录
    datas=[('../config.txt', './')] + datas,  #(来源目录, 目标目录), 根据实际情况修改来源目录
    hiddenimports=hidden_import_list,
    hookspath=['hooks'],
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
    name='manage',
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
    name='manage',
)
