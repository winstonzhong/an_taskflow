# encoding: utf-8
"""
Created on 2015年8月14日

@author: root
"""


from django.core.management.base import BaseCommand


# from my_robot.base.models import 手机设备
from base.models import  定时任务

import tool_env
from adb_tools.helper_adb import BaseAdb



import requests
import tempfile
from urllib.parse import unquote

import config_reader

# def change_suffix(url, suffix):
#     return url.rsplit(".", 1)[0] + "." + suffix


def set_file(content, to_url):
    url = "https://file.j1.sale/api/set"
    form_data = {"file": ("test", content)}
    data = {"url": to_url}
    data = requests.post(url, data=data, files=form_data).json()
    # return "https://file.j1.sale" + data["data"]["url"]
    # print(data)
    return data


def upload_file(content, fname, project_name="robot"):
    url = f"https://file.j1.sale/api/file"
    form_data = {"file": (fname, content)}
    data = {"project": project_name}
    data = requests.post(url, data=data, files=form_data).json()
    return "https://file.j1.sale" + data["data"]["url"]


def download_file(url, suffix=".mp3"):
    with requests.get(url, stream=True) as r:
        # print(dir(r))
        if r.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=suffix)
            # print(r.headers['Content-Disposition'])
            fname = r.headers["Content-Disposition"].rsplit("'", maxsplit=1)[-1]
            fname = unquote(fname)
            with open(tmp.name, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            return tmp.name, fname


class Command(BaseCommand):
    def add_arguments(self, parser):
        # parser.add_argument("--wxrobot", action="store_true", default=False)
        parser.add_argument(
            "--ip_port", nargs="?", default="192.168.0.146:7080", type=str
        )
        # parser.add_argument("--usb", nargs="?", default=None, type=str)
        # parser.add_argument("--fpath", nargs="?", default=None, type=str)
        parser.add_argument("--testit", action="store_true", default=False)
        # parser.add_argument("--span", nargs="?", default=0, type=int)
        # # parser.add_argument("--group_name", nargs="?", default="主机器人", type=str)
        # parser.add_argument(
        #     "--state", nargs="?", default="状态_等待微信新消息", type=str
        # )
        parser.add_argument("--step", action="store_true", default=False)
        # parser.add_argument("--debug", action="store_true", default=False)

        # parser.add_argument("--发送", action="store_true", default=False)
        # parser.add_argument("--接收", action="store_true", default=False)

        parser.add_argument("--运行定时任务", nargs="?", default=None, type=str)

        # parser.add_argument("--测试加好友", action="store_true", default=False)
        # parser.add_argument("--exclude", nargs="?", default=None, type=str)
        # parser.add_argument("--list", action="store_true", default=False)
        

    def handle(self, *args, **options):
        定时任务.IP_PORT = options.get("ip_port")
        
        if options.get("usb"):
            data_list = BaseAdb.get_devcie_usb()
            if data_list:
                usb = options.get("usb")
                if tool_env.is_int(usb) and int(usb) >= 0 and int(usb) < len(data_list):
                    usb_device = data_list[int(usb)]
                elif usb in [x.get("id") for x in data_list]:
                    usb_device = BaseAdb.get_device_by_id(usb)
                else:
                    print("输入的usb序号不正确")
                    return
                adb = BaseAdb(usb_device)
                # print(adb)
                ip_port = adb.auto_init_wifi_connection()
                adb = BaseAdb({"id": ip_port})
                print(adb)
                print(adb.connect())
            else:
                print("没有检测到任何设备。。。")
            return

        if options.get("testit"):
            usb_device = BaseAdb.first_device_usb()
            adb = BaseAdb(usb_device)
            print(adb)
            package = 'com.tencent.mm'
            activity = '.ui.LauncherUI'
            adb.open_certain_app(package, activity)
            cfg = config_reader.read_config_from_file("config.txt")
            print(cfg)
            return


        if options.get("运行定时任务"):
            # 基础机器.设置默认选中设备(options.get("ip_port"))

            if tool_env.is_number(options.get("运行定时任务")):
                kwargs = {"id": options.get("运行定时任务")}
            else:
                kwargs = {"group_name": options.get("运行定时任务"),
                          "_exclude":options.get("exclude") or "",
                          }
            q = 定时任务.得到所有待执行的任务(**kwargs)
            assert q.count(), "没有找到定时任务"
            print(f"开始执行以下任务：{q.count()}")
            for i, x in enumerate(q):
                print(i, x)

            if options.get("list"):
                return
            定时任务.执行所有定时任务(
                单步=options.get("step"),
                每轮间隔秒数=options.get("span"),
                **kwargs,
            )
