# encoding: utf-8
"""
Created on 2015年8月14日

@author: root
"""


from django.core.management.base import BaseCommand


# from my_robot.base.models import 手机设备

from base.models import 定时任务

from adb_tools import tool_xpath

import tool_env
from adb_tools.helper_adb import BaseAdb


import requests
import tempfile
from urllib.parse import unquote

import config_reader


from django.utils import timezone
from datetime import datetime

import tool_date

from adb_tools import tool_xpath

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
    print(data)
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


def get_query_kwargs(line: str, 不考虑任务时间因素=False):
    kwargs = {"不考虑任务时间因素": 不考虑任务时间因素}
    if tool_env.is_number(line):
        kwargs.update(id=line)
    else:
        kwargs.update(group_name=line)
    return kwargs
    # return 定时任务.得到所有待执行的任务(**kwargs)


def list_tasks(line: str):
    kwargs = get_query_kwargs(line, 不考虑任务时间因素=True)
    q = 定时任务.得到所有待执行的任务(**kwargs)
    assert q.count(), "没有找到定时任务"
    print("=" * 50)
    print(f"总共包含任务数：{q.count()}")
    for i, x in enumerate(q):
        print(i, x)
    # return kwargs


class Command(BaseCommand):
    def add_arguments(self, parser):
        # parser.add_argument("--wxrobot", action="store_true", default=False)
        parser.add_argument(
            "--ip_port", nargs="?", default="192.168.0.146:7080", type=str
        )
        # parser.add_argument("--usb", nargs="?", default=None, type=str)
        # parser.add_argument("--fpath", nargs="?", default=None, type=str)
        parser.add_argument("--testit", action="store_true", default=False)

        parser.add_argument("--span", nargs="?", default=1, type=int)

        # # parser.add_argument("--group_name", nargs="?", default="主机器人", type=str)
        # parser.add_argument(
        #     "--state", nargs="?", default="状态_等待微信新消息", type=str
        # )
        parser.add_argument("--step", action="store_true", default=False)
        # parser.add_argument("--debug", action="store_true", default=False)

        # parser.add_argument("--发送", action="store_true", default=False)
        parser.add_argument("--强制更新", action="store_true", default=False)

        parser.add_argument("--删除所有任务", action="store_true", default=False)

        # parser.add_argument("--强制第一次运行", action="store_true", default=False)

        parser.add_argument("--运行定时任务", nargs="?", default=None, type=str)

        parser.add_argument("--导入网络任务", nargs="?", default=None, type=str)

        # https://file.j1.sale/api/file/jobs/49_抖音_同步寻找目标视频并评论2.json

        # parser.add_argument("--测试加好友", action="store_true", default=False)
        # parser.add_argument("--exclude", nargs="?", default=None, type=str)
        parser.add_argument("--列出", nargs="?", default=None, type=str)

        parser.add_argument("--重置更新时间", nargs="?", default=None, type=str)

        parser.add_argument("--最低分", nargs="?", default=60, type=int)

        parser.add_argument("--最高上限", nargs="?", default=2000, type=int)

        parser.add_argument("--最低下限", nargs="?", default=100, type=int)

        parser.add_argument("--最低互动总数", nargs="?", default=0, type=int)
        
        parser.add_argument("--不回关", nargs="?", default=0, type=int)

        # parser.add_argument(
        #     "--关键词",
        #     nargs="?",
        #     default="美甲,法式甲,甲片延长,贴片甲,光疗甲,短甲款式,猫眼甲,半永久甲,新娘甲,卸甲油,不伤甲,护甲油",
        #     type=str,
        # )

        parser.add_argument(
            "--关键词",
            nargs="?",
            default="",
            type=str,
        )

        parser.add_argument("--排除关键词", nargs="?", default="游戏", type=str)
        parser.add_argument("--心跳上报", action="store_true", default=False)

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
            # usb_device = BaseAdb.first_device_usb()
            # adb = BaseAdb(usb_device)
            # print(adb)
            # package = "com.tencent.mm"
            # activity = ".ui.LauncherUI"
            # adb.open_certain_app(package, activity)
            # cfg = config_reader.read_config_from_file("config.txt")
            # print(cfg)
            sd = tool_xpath.SteadyDevice.from_ip_port(
                定时任务.IP_PORT,
                refresh_init=False,
                need_screen=False,
                need_xml=True,
            )
            print(sd.adb.serialno)

            return

        if options.get("导入网络任务"):
            url = options.get("导入网络任务")
            定时任务.导入网络定时任务(url, options.get("强制更新"))

        if options.get("删除所有任务"):
            print(定时任务.objects.all().delete())

        if options.get("列出"):
            list_tasks(options.get("列出"))

        if options.get("重置更新时间"):
            kwargs = get_query_kwargs(
                options.get("重置更新时间"), 不考虑任务时间因素=True
            )
            q = 定时任务.得到所有待执行的任务(**kwargs)
            assert q.count(), "没有找到定时任务"
            print("=" * 50)
            tdate = "2000-01-01"
            print(f"将总共重置以下任务的更新日期到：{tdate}")
            for i, x in enumerate(q):
                print(i, x)
            naive_datetime = datetime.strptime(tdate, "%Y-%m-%d")
            aware_datetime = timezone.make_aware(naive_datetime)
            q.update(update_time=aware_datetime)

        if options.get("运行定时任务"):
            tool_xpath.global_rom.最低分 = options.get("最低分")
            tool_xpath.global_rom.关键词 = options.get("关键词")  # .split(",")
            tool_xpath.global_rom.排除关键词 = options.get("排除关键词")  # .split(",")
            tool_xpath.global_rom.最高上限 = options.get("最高上限")
            tool_xpath.global_rom.最低下限 = options.get("最低下限")
            tool_xpath.global_rom.最低互动总数 = options.get("最低互动总数")
            tool_xpath.global_rom.不回关 = options.get("不回关")

            list_tasks(options.get("运行定时任务"))
            kwargs = get_query_kwargs(
                options.get("运行定时任务"), 不考虑任务时间因素=False
            )
            try:
                定时任务.执行所有定时任务(
                    单步=options.get("step"),
                    每轮间隔秒数=options.get("span"),
                    **kwargs,
                )
            except KeyboardInterrupt:
                pass
            return

        if options.get('心跳上报'):
            import time
            import traceback
            from tool_sys_info import get_termux_sys_info
            from commons.external_api import push_sys_info
            from adb_tools.tool_xpath import SteadyDevice

            device_id = ''

            device = SteadyDevice.from_ip_port(
                    定时任务.IP_PORT,
                )
            if device is not None:
                device_id = device.adb.serialno

            while 1:
                data = {
                    'device_id': device_id,
                    'sys_info': get_termux_sys_info()
                }
                print(data)
                try:
                    ret_data = push_sys_info(data)
                    print(ret_data)
                except:
                    traceback.print_exc()
                print('----------------------')
                time.sleep(10)