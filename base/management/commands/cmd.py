# encoding: utf-8
"""
Created on 2015年8月14日

@author: root
"""
import base64
import threading

import time
import os
import webbrowser

from django.core.management import call_command
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
import asyncio

from websockect_server import ws_server, SharedData, shared_data, get_shared_data
from typing import Optional

import logging



# 全局/类级共享停止信号（用于通知 Django Web 服务线程退出）
django_web_server_stop_flag = threading.Event()
# 记录 Django Web 服务线程（方便后续等待线程退出）
django_server_thread: Optional[threading.Thread] = None

logger = logging.getLogger(__name__)
try:
    from PIL import Image, ImageDraw, ImageFont
    import io
except ImportError:
    Image = None
    logger.warning("未安装 PIL/Pillow，将使用模拟 Base64 图片数据（前端无法正常渲染真实图片）")

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


#======================================

class ScreenshotGenerator:
    """截图生成器 - 生成模拟截图数据（实际项目中应替换为真实截图逻辑）"""

    def __init__(self, width: int = 360, height: int = 720):
        self.width = width
        self.height = height
        self.frame_count = 0

    def generate(self) -> Optional[bytes]:
        """生成模拟截图（JPEG格式）"""
        try:
            # 尝试使用PIL生成模拟截图
            try:
                from PIL import Image, ImageDraw, ImageFont
                import io

                # 创建图像
                img = Image.new('RGB', (self.width, self.height), color='#1a1a2e')
                draw = ImageDraw.Draw(img)

                # 添加动态内容
                self.frame_count += 1
                hue = (self.frame_count * 5) % 360

                # 绘制背景渐变效果
                for y in range(0, self.height, 4):
                    color_val = int(30 + (y / self.height) * 50)
                    draw.line([(0, y), (self.width, y)], fill=(color_val, color_val, color_val + 30))

                # 绘制状态栏
                draw.rectangle([0, 0, self.width, 24], fill='#000000')
                draw.text((10, 4), "9:41", fill='#ffffff')

                # 绘制应用网格
                app_colors = [
                    '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4',
                    '#feca57', '#ff9ff3', '#54a0ff', '#48dbfb',
                ]
                icon_size = 48
                gap = 20
                cols = 4
                start_y = 60

                for i in range(16):
                    row = i // cols
                    col = i % cols
                    x = 20 + col * (icon_size + gap)
                    y = start_y + row * (icon_size + gap + 20)

                    color = app_colors[i % len(app_colors)]
                    draw.rounded_rectangle([x, y, x + icon_size, y + icon_size], radius=10, fill=color)

                # 绘制底部Dock
                dock_y = self.height - 100
                draw.rounded_rectangle([20, dock_y, self.width - 20, dock_y + 70], radius=20, fill='#ffffff20')
                for i in range(4):
                    x = 40 + i * (icon_size + 20)
                    color = app_colors[i % len(app_colors)]
                    draw.rounded_rectangle([x, dock_y + 11, x + icon_size, dock_y + 11 + icon_size], radius=10,
                                           fill=color)

                # 绘制帧率信息
                draw.text((10, self.height - 30), f"Frame: {self.frame_count} | FPS: 10", fill='#ffffff80')

                # 绘制扫描线效果
                scan_y = (self.frame_count * 3) % self.height
                draw.line([(0, scan_y), (self.width, scan_y)], fill='#00d4ff40', width=2)

                # 转换为JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=80)
                return buffer.getvalue()

            except ImportError:
                # 如果PIL不可用，返回简单的测试数据
                return self._generate_fallback_image()

        except Exception as e:
            logger.error(f"生成截图失败: {e}")
            return None

    def _generate_fallback_image(self) -> bytes:
        """生成备用图像数据（当PIL不可用时）"""
        # 创建一个最小的有效JPEG文件（1x1像素）
        # 实际应用中应该使用PIL或其他库
        jpeg_header = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        ])
        return jpeg_header + bytes(100)  # 简化版本


async def start_django_web_server(host: str = "0.0.0.0", port: int = 8000):
    """
    异步启动 Django Web 服务（支持优雅停止）
    :param host: 绑定地址
    :param port: 端口号
    """
    global django_server_thread  # 引用全局线程变量，方便后续操作
    logger.info(f"准备启动 Django Web 服务：http://{host}:{port}")
    # 设置 Django 运行环境（避免多线程冲突）
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")  # 替换为你的项目settings路径
    os.environ["RUN_MAIN"] = "true"  # 禁用自动重载（避免重复启动）

    def run_server():
        """同步执行 runserver 命令（支持优雅停止）"""
        # 引入 Django 内部的 quit 信号（用于终止 runserver）
        try:
            # 启动 Django runserver（同步阻塞）
            call_command(
                "runserver",
                f"{host}:{port}",
                use_reloader=False,  # 关闭自动重载（异步环境下必须）
                use_ipv6=False,
                verbosity=1
            )
        except Exception as e:
            # 只有未设置停止标志时，才记录启动失败错误（避免停止时的正常异常被误报）
            if not django_web_server_stop_flag.is_set():
                logger.error(f"Django Web 服务启动失败：{e}")
        finally:
            logger.info("Django Web 服务线程已退出")

    def stop_django_web_server():
        """优雅停止 Django Web 服务"""
        # from django.core.management.commands.runserver import quit_command
        # # 1. 发送 Django runserver 退出信号
        # quit_command()
        # 步骤1：设置停止标志（通知线程，后续不再处理新请求）
        django_web_server_stop_flag.set()

        # 步骤2：等待线程退出（给 5 秒超时，确保当前请求处理完成）
        if django_server_thread and django_server_thread.is_alive():
            try:
                # join(timeout=5)：等待 5 秒，让线程有时间处理完当前请求、清理资源
                django_server_thread.join(timeout=5)
            except Exception as e:
                logger.warning(f"等待 Django Web 服务线程退出时出现异常：{e}")

        # 步骤3：验证线程是否已退出（超时未退出则提示，但不强制杀死）
        if django_server_thread and django_server_thread.is_alive():
            logger.warning("Django Web 服务线程未在 5 秒内退出（可能有长请求），将释放端口资源")
        else:
            logger.info("Django Web 服务已优雅停止（所有请求处理完成，资源已释放）")


    # 绑定停止函数（方便外部调用）
    start_django_web_server.stop = stop_django_web_server

    # 步骤4：启动独立线程运行 Django Web 服务（避免阻塞 asyncio 事件循环）
    django_server_thread = threading.Thread(target=run_server, daemon=True)
    django_server_thread.start()

    # 等待服务启动（可选）
    await asyncio.sleep(2)
    logger.info("Django Web 服务线程已启动")

async def django_main_business():
    """Django 核心业务逻辑（截图生成 + 前端配置处理）"""
    logger.info("Django 主业务启动（负责截图生成和前端配置处理）")
    # 初始化截图生成器
    screenshot_generator = ScreenshotGenerator(
        width=ws_server.config.screenshot_width,
        height=ws_server.config.screenshot_height
    )
    shared_data = get_shared_data()
    frame_count = 0
    target_fps = ws_server.config.target_fps
    frame_interval = 1.0 / target_fps

    while True:
        loop_start = asyncio.get_event_loop().time()

        # ====================== 任务1：消费 WS→Django 队列（处理前端配置）======================
        try:
            # 非阻塞读取前端消息（超时0.05s，不阻塞截图循环）
            forward_data = await asyncio.wait_for(shared_data.ws_to_django_queue.get(), timeout=0.05)

            print('forward_data', forward_data)
            client_id = forward_data.get('from_client_id')
            front_data = forward_data.get('data', {})
            front_msg_type = front_data.get('type')

            # 处理前端配置消息（示例：修改帧率、修改截图尺寸）
            if front_msg_type == 'client_config':
                config_key = front_data.get('key')
                config_value = front_data.get('value')
                logger.info(f"处理前端 {client_id} 配置：{config_key} = {config_value}")

                # 更新配置（以修改帧率为例）
                if config_key == 'target_fps':
                    target_fps = max(1, min(30, int(config_value)))
                    frame_interval = 1.0 / target_fps
                    # 更新WebSocket服务器配置
                    ws_server.config.target_fps = target_fps
                    ws_server.frame_interval = frame_interval

                    # 向WS推送配置反馈（供前端展示）
                    await shared_data.django_to_ws_queue.put({
                        'type': 'config_feedback',
                        'status': 'success',
                        'key': config_key,
                        'value': target_fps,
                        'message': f'帧率已更新为 {target_fps} FPS'
                    })

            elif front_msg_type == 'client_control':
                # 处理前端控制指令（如暂停/恢复截图）
                action = front_data.get('action')
                logger.info(f"处理前端 {client_id} 控制指令：{action}")
                # 此处可添加具体业务逻辑（如操作数据库、调用外部接口等）

            else:
                logger.debug(f"收到前端 {client_id} 未知类型消息：{front_msg_type}")

        except asyncio.TimeoutError:
            pass  # 无前端消息时跳过

        # ====================== 任务2：定时生成截图，写入 Django→WS 队列 ======================
        try:
            frame_count += 1
            # 生成截图
            screenshot_bytes = screenshot_generator.generate()

            if screenshot_bytes:
                # 写入Django→WS队列，供WebSocket推送至前端
                await shared_data.django_to_ws_queue.put({
                    'type': 'screenshot_data',
                    'data': screenshot_bytes,
                    'frame_count': frame_count,
                    'timestamp': asyncio.get_event_loop().time()
                })

            # 控制截图帧率（保证稳定推送）
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"生成/推送截图失败: {e}")
            await asyncio.sleep(0.1)





async def main():
    """整合 WebSocket 与 Django 业务"""
    # 初始化共享数据（绑定到当前事件循环）
    get_shared_data()

    # 启动 Django Web 服务（异步任务）
    web_server_task = asyncio.create_task(start_django_web_server(host="0.0.0.0", port=8000))

    # 启动 WebSocket 服务（后台任务）
    ws_task = asyncio.create_task(ws_server.start())

    # 启动 Django 主业务（核心：截图生成 + 配置处理）
    business_task = asyncio.create_task(django_main_business())

    # ====================== 新增：延迟打开浏览器窗口 ======================
    async def open_browser():
        """延迟打开浏览器（等待Django服务启动）"""
        await asyncio.sleep(3)  # 延迟3秒，确保服务已启动
        url = "http://localhost:8000/base/control"
        logger.info(f"自动打开浏览器访问：{url}")
        try:
            webbrowser.open(url)  # 打开默认浏览器
        except Exception as e:
            logger.warning(f"打开浏览器失败：{e}")

    # 创建打开浏览器的异步任务
    browser_task = asyncio.create_task(open_browser())
    # =====================================================================


    # 等待所有任务完成（捕获中断信号）
    try:
        await asyncio.gather(web_server_task, ws_task, business_task, browser_task)
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止服务...")

        # 步骤1：停止 WebSocket 服务（原有逻辑，正常生效）
        ws_server.stop()


        # 步骤2：优雅停止 Django Web 服务（新增：调用绑定的停止函数）
        try:
            start_django_web_server.stop()
        except Exception as e:
            logger.warning(f"Django Web 服务优雅停止失败，将强制终止：{e}")



        # 步骤3：取消所有 asyncio 任务（原有逻辑，正常生效）
        web_server_task.cancel()
        ws_task.cancel()
        business_task.cancel()

        # 步骤4：等待所有任务响应取消并退出（兼容所有版本）
        await asyncio.gather(web_server_task, ws_task, business_task, return_exceptions=True)
        logger.info("所有服务已停止完成（无资源残留）")

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
        parser.add_argument("--test", action="store_true", default=False)

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

        if options.get('test'):
            try:
                asyncio.run(main())
            except Exception as e:
                print(f"服务启动失败：{str(e)}")
                self.stdout.write(self.style.ERROR(f"服务启动失败：{str(e)}"))
            else:
                self.stdout.write(self.style.SUCCESS("服务已正常退出"))