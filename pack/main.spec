# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs


current_file = sys.argv[0]
BASE_DIR = Path(current_file).resolve().parent.parent
sys.path.append(str(BASE_DIR))

CAIDAO_DIR = BASE_DIR.parent / 'caidao'
# print('CAIDAO_DIR', CAIDAO_DIR)

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


# hidden_import_list += collect_submodules('cryptography')

# hidden_import_list += collect_submodules('pandas')
# hidden_import_list += collect_submodules('numpy')

hidden_import_list += collect_submodules('cffi')
hidden_import_list += collect_submodules('pycparser')
hidden_import_list += [
    'cffi._pycparser',
    'cffi.model',
    'cffi.api',
    'cffi.ffiplatform',
    'cffi.verifier',
    'cffi.lock',
    'cffi.error',
    'pycparser.c_parser',
    'pycparser.c_lexer',
    'pycparser.c_ast',
]



binaries = collect_dynamic_libs('numpy')
# hidden_import_list += ['numpy', 'numpy.core._multiarray_umath']  # 显式导入缺失模块
hidden_import_list += collect_submodules('waitress')
hidden_import_list += collect_submodules('whitenoise')

datas = collect_data_files('pandas')
datas += collect_data_files('cffi')
datas += collect_data_files('pycparser')

datas += [
    (str(BASE_DIR / 'templates'), './templates'),
    (str(BASE_DIR / 'config'), './config'),
    # (str(BASE_DIR / 'manage.py'), '.'),  # Django manage.py（保留兼容性）
    (str(CAIDAO_DIR / 'queue_redis_json.cfg'), '.'),
    (str(CAIDAO_DIR / 'mobans'), './mobans'),
    (str(CAIDAO_DIR / 'prompt'), './prompt'),  # prompt 模板文件目录
    (str(CAIDAO_DIR / 'cn_stopwords.txt'), '.'),  # jieba 停用词表
    (str(CAIDAO_DIR / 'cn_userdict_hairstyles.txt'), '.'),  # jieba 用户词典

]

staticfiles_dir = BASE_DIR / 'staticfiles'
if staticfiles_dir.exists():
    datas.append((str(staticfiles_dir), './staticfiles'))

a = Analysis(
    ['../main.py'],
    pathex=[CAIDAO_DIR, '../'],
    binaries=binaries,  # 格式: (来源目录, 目标目录), 根据实际情况修改来源目录
    datas=datas,  #(来源目录, 目标目录), 根据实际情况修改来源目录
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
