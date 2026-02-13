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
hidden_import_list += collect_submodules('rest_framework')

hidden_import_list += collect_submodules('pandas')
hidden_import_list += collect_submodules('numpy')
# hidden_import_list += [
#                 'pandas',
#                 'pandas._libs',
#                 'pandas._libs.tslibs',
#                 'pandas._libs.window',
#                 'pandas._libs.window.aggregations',
#                 'pandas._libs.window.indexers',
#                 'pandas._libs.aggregations',
#                 ]

# hidden_import_list += collect_submodules('cryptography')

# hidden_import_list += collect_submodules('pandas')
# hidden_import_list += collect_submodules('numpy')

datas = collect_data_files('pandas')

# + collect_data_files('numpy')
binaries = collect_dynamic_libs('numpy')
hidden_import_list += ['numpy', 'numpy.core._multiarray_umath']  # 显式导入缺失模块
# binaries += [(r'.\venv_win/Lib/site-packages/numpy/.libs/*', 'numpy/.libs')]  # 包含动态库
# binaries = []
# datas = []
# datas = [
#             (r'.\venv_win\Lib\site-packages\pandas\_libs', 'pandas/_libs'),
#         ]
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
    ['../main.py'],
    pathex=[CAIDAO_DIR, '../'],
    binaries=binaries,  # 格式: (来源目录, 目标目录), 根据实际情况修改来源目录
    datas=[('../templates', './templates'), ('../config', './config'), (f'{CAIDAO_DIR}/queue_redis_json.cfg', '.')] + datas,  #(来源目录, 目标目录), 根据实际情况修改来源目录
    hiddenimports=hidden_import_list,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,

    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,

)
pyz = PYZ(a.pure,
          a.zipped_data,
          cipher=None
          )

# exe = EXE(
#     pyz,
#     a.scripts,
#     [],
#     exclude_binaries=True,
#     name='main',
#     debug=True,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=False,
#     console=True,
#     disable_windowed_traceback=False,
#     argv_emulation=False,
#     target_arch=None,
#     codesign_identity=None,
#     entitlements_file=None,
# )



exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='main',  # 生成的exe文件名
    debug=False,  # 调试完成后改为False
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX压缩（UPX可能损坏pandas的DLL文件）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保持控制台输出，便于查看错误日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # 自动匹配系统架构
    codesign_identity=None,
    entitlements_file=None,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='main',
)
