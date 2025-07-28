import os
import shutil
import sys
from pathlib import Path
from subprocess import call

current_file = sys.argv[0]
BASE_DIR = Path(current_file).resolve().parent.parent
BASE_DIR = str(BASE_DIR).replace('\\', '/')
PACK_DIR = f'{BASE_DIR}/pack'


def get_dist_dir():
    return f'{PACK_DIR}/dist'


def get_build_dir():
    return f'{PACK_DIR}/build'


def run_cmd(cmd):
    ret = call(cmd, shell=True)
    if ret != 0:
        print(f'执行错误: {cmd}')
        raise


def pack():
    """打包"""
    build_dir = get_build_dir()
    dist_dir = get_dist_dir()
    cmd = f'pyinstaller manage.spec -y --clean --distpath {dist_dir} --workpath {build_dir}'
    run_cmd(cmd)


def remove_existed_pack():
    build_dir = get_build_dir()
    dist_dir = get_dist_dir()
    if os.path.lexists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.lexists(dist_dir):
        shutil.rmtree(dist_dir)


def main(is_remove_existed=False):
    if is_remove_existed:
        remove_existed_pack()
    pack()


if __name__ == '__main__':
    main(is_remove_existed=False)
