"""
统一入口模块
使用多线程同时启动 WebSocket Server、Django Server 和 Worker
"""

import sys
import time
import signal
import threading
import os
from typing import List

# 导入各模块
from django.core.management import call_command

from commons.queue_manager import get_queue_manager
from commons.websocket_server import start_websocket_server
from commons.helper_worker import start_worker, start_browser_worker


class ApplicationManager:
    """
    应用管理器
    统一管理所有服务的生命周期
    """

    def __init__(self):
        self.queue_manager = get_queue_manager()
        self.websocket_server = None
        self.django_server = None
        self.worker = None
        self.browser = None
        self.running = False


        # Django 项目 manage.py 路径
        # self.django_manage_py_path = django_manage_py_path or "manage.py"

        # 存储所有线程
        self.threads: List[threading.Thread] = []

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理系统信号，实现优雅关闭"""
        print(f"\n[Main] 收到信号 {signum}，正在关闭服务...")
        self.stop()
        sys.exit(0)

    def start_all(self):
        """启动所有服务"""
        print("=" * 50)
        print("正在启动后端服务...")
        print("=" * 50)

        self.running = True

        # 1. 首先启动 Worker（先启动消费者，避免消息丢失）
        print("\n[1/3] 启动 Worker...")
        self.worker = start_worker(num_threads=2)


        # 2. 启动 WebSocket Server
        print("\n[2/3] 启动 WebSocket Server...")
        self.websocket_server = start_websocket_server(host="0.0.0.0", port=8765)

        # 3. 启动 Django Server（通过子进程方式启动，避免配置冲突）
        print("\n[3/3] 启动 Django Server...")
        self._start_django_server()

        print("\n" + "=" * 50)
        print("所有服务已启动！")
        print("=" * 50)
        print("服务地址：")
        print("  - WebSocket: ws://localhost:8765")
        print("  - Django HTTP: http://localhost:8001")
        print("=" * 50)
        print("按 Ctrl+C 停止服务")
        print("=" * 50 + "\n")

        self.browser = start_browser_worker()

        # 主循环：监控服务状态
        self._monitor_loop()

    def _start_django_server(self):
        """
        在新线程中启动 Django 开发服务器
        使用 os.system 或 subprocess 调用已有的 manage.py
        """
        # def _run_django():
        #     """运行 Django 服务器的线程函数"""
        #     print(f"[Django] 通过 {self.django_manage_py_path} 启动服务...")
        #
        #     # 使用 subprocess 启动 Django，这样可以正确隔离环境
        #     import subprocess
        #
        #     cmd = [
        #         sys.executable,  # 当前 Python 解释器
        #         self.django_manage_py_path,
        #         "runserver",
        #         "0.0.0.0:8001",
        #         "--noreload",  # 禁用自动重载，避免多线程问题
        #     ]
        #
        #     try:
        #         # 启动 Django 进程并等待
        #         process = subprocess.Popen(
        #             cmd,
        #             cwd=os.path.dirname(os.path.abspath(self.django_manage_py_path)) or None,
        #             stdout=sys.stdout,
        #             stderr=sys.stderr,
        #         )
        #
        #         # 保存进程引用以便后续终止
        #         self.django_process = process
        #
        #         # 等待进程结束
        #         process.wait()
        #
        #     except Exception as e:
        #         print(f"[Django] 启动失败: {e}")

        def run_django():
            try:
                # 启动 Django runserver（同步阻塞）
                call_command(
                    "runserver",
                    f"0.0.0.0:8001",
                    use_reloader=False,  # 关闭自动重载（异步环境下必须）
                    use_ipv6=False,
                    verbosity=1
                )
            except Exception as e:
                print(f"Django Web 服务启动失败：{e}")
            finally:
                print("Django Web 服务线程已退出")





        # 在新线程中启动 Django
        self.django_thread = threading.Thread(
            target=run_django,
            daemon=True,
            name="DjangoThread"
        )
        self.django_thread.start()

        # 等待一下确保 Django 启动
        time.sleep(2)
        print("[Django] 服务器线程已启动")

    def _monitor_loop(self):
        """主监控循环"""
        try:
            while self.running:
                # 检查各服务状态
                ws_alive = (self.websocket_server.thread is not None and
                           self.websocket_server.thread.is_alive())
                worker_alive = self.worker.is_alive()
                django_alive = self.django_thread.is_alive() if hasattr(self, 'django_thread') else False

                browser_alive = self.browser.is_alive()

                if not ws_alive:
                    print("[Main] 警告: WebSocket Server 线程已停止")
                if not worker_alive:
                    print("[Main] 警告: Worker 线程已停止")
                if not django_alive:
                    print("[Main] 警告: Django Server 线程已停止")

                # if not browser_alive:
                #     print("[Main] 警告: browser 线程已停止")

                # 每5秒打印一次队列状态
                stats = self.queue_manager.get_stats()
                # print(f"[Main] 队列状态 - ws_to_worker: {stats['ws_to_worker_size']}, "
                #       f"worker_to_ws: {stats['worker_to_ws_size']}")

                time.sleep(5)

        except KeyboardInterrupt:
            print("\n[Main] 收到键盘中断")
        finally:
            self.stop()

    def stop(self):
        """停止所有服务"""
        print("\n[Main] 正在停止所有服务...")
        self.running = False

        # 停止 Django（如果有进程）
        if hasattr(self, 'django_process') and self.django_process:
            print("[Main] 正在停止 Django...")
            self.django_process.terminate()
            try:
                self.django_process.wait(timeout=5)
            except:
                self.django_process.kill()

        # 停止 WebSocket
        if self.websocket_server:
            self.websocket_server.stop()

        # 停止 Worker
        if self.worker:
            self.worker.stop()

        # 停止 browser
        if self.browser:
            self.browser.stop()

        print("[Main] 所有服务已停止")


def main():
    """主入口函数"""
    # 检查依赖
    try:
        import websockets
    except ImportError:
        print("错误：缺少 websockets 库，请安装: pip install websockets")
        sys.exit(1)

    # 检查 manage.py 是否存在
    # manage_py = "manage.py"
    # if len(sys.argv) > 1:
    #     manage_py = sys.argv[1]
    #
    # if not os.path.exists(manage_py):
    #     print(f"错误：找不到 Django manage.py 文件: {manage_py}")
    #     print("用法: python main.py [path/to/manage.py]")
    #     sys.exit(1)

    # 启动应用
    app_manager = ApplicationManager()
    app_manager.start_all()


if __name__ == "__main__":
    main()