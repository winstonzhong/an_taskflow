"""
统一入口模块
使用多线程同时启动 WebSocket Server、Django Server 和 Worker
"""

import multiprocessing
multiprocessing.freeze_support()  # Windows 打包必需，防止子进程无限递归

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
        """
        处理系统信号，实现优雅关闭
        
        使用带超时的机制确保即使 stop() 方法挂起，主进程也能退出
        """
        import threading
        
        print(f"\n[Main] 收到信号 {signum}，正在关闭服务...")
        self.running = False
        
        # 检查是否已经在停止过程中（防止重复调用）
        if hasattr(self, '_stopping') and self._stopping:
            print("[Main] 停止已在进行中，跳过...")
            return
        self._stopping = True
        
        # 使用后台线程执行 stop()，防止在主线程中挂起
        stop_thread = threading.Thread(target=self._safe_stop, name="signal_stop_handler")
        stop_thread.daemon = True
        stop_thread.start()
        
        # 等待 stop() 完成，但设置超时
        stop_timeout = 15  # 总超时 15 秒
        
        # 检查 stop_thread 是否是当前线程（理论上不应该）
        if stop_thread is not threading.current_thread():
            stop_thread.join(timeout=stop_timeout)
        
        if stop_thread.is_alive():
            print(f"\n[Main] 警告: 服务停止超时（{stop_timeout}s），强制退出...")
            # 最后手段：强制杀死所有子进程
            self._kill_remaining_children()
        
        print("\n[Main] 退出")
        sys.exit(0)
    
    def _safe_stop(self):
        """
        安全地执行 stop()，捕获所有异常
        """
        import threading
        
        try:
            current_thread = threading.current_thread()
            
            # 如果监控线程存在、不是当前线程、且还活着，才等待它
            if (hasattr(self, '_monitor_thread') and 
                self._monitor_thread is not current_thread and 
                self._monitor_thread.is_alive()):
                try:
                    self._monitor_thread.join(timeout=2)
                except RuntimeError:
                    # 无法 join 当前线程，忽略
                    pass
            
            # 执行停止
            self.stop()
        except Exception as e:
            print(f"\n[Main] 停止服务时出错: {e}")
            import traceback
            traceback.print_exc()
            # 即使出错也尝试清理子进程
            self._kill_remaining_children()

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

        # self.browser = start_browser_worker()

        # 主循环：监控服务状态
        self._monitor_loop()

    def _start_django_server(self):
        """
        使用 subprocess 启动 Django 开发服务器
        subprocess 模式避免线程问题
        """
        import subprocess
        import sys
        
        try:
            # 判断是否为打包环境，使用正确的 Python 解释器
            if getattr(sys, 'frozen', False):
                # 打包环境：使用 _internal 目录下的 python.exe
                python_exe = os.path.join(os.path.dirname(sys.executable), '_internal', 'python.exe')
                if not os.path.exists(python_exe):
                    # 备选：使用系统 PATH 中的 python
                    python_exe = 'python'
            else:
                # 开发环境
                python_exe = sys.executable
            
            # 定位 manage.py 的正确路径
            if getattr(sys, 'frozen', False):
                # 打包环境：manage.py 在 exe 所在目录的上一级（与 _internal 同级）
                base_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境：当前文件所在目录
                base_dir = os.path.dirname(os.path.abspath(__file__))
            
            manage_py = os.path.join(base_dir, "manage.py")
            
            # 使用 subprocess 启动 Django
            self.django_process = subprocess.Popen(
                [python_exe, manage_py, "runserver", "0.0.0.0:8001", "--noreload"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 等待 Django 启动
            time.sleep(3)
            
            # 检查进程是否正常运行
            if self.django_process.poll() is None:
                print("[Django] 服务器已在子进程中启动 (PID: %d)" % self.django_process.pid)
                
                # 启动一个线程来读取输出
                def read_output():
                    for line in self.django_process.stdout:
                        print(f"[Django] {line.rstrip()}")
                
                output_thread = threading.Thread(target=read_output, daemon=True)
                output_thread.start()
            else:
                stdout, stderr = self.django_process.communicate(timeout=1)
                print(f"[Django] 启动失败，退出码: {self.django_process.returncode}")
                if stdout:
                    print(f"[Django] 输出: {stdout}")
                if stderr:
                    print(f"[Django] 错误: {stderr}")
                    
        except Exception as e:
            print(f"[Django] 启动异常: {e}")
            import traceback
            traceback.print_exc()

    def _monitor_loop(self):
        """主监控循环"""
        self._monitor_thread = threading.current_thread()
        try:
            while self.running:
                # 检查各服务状态
                ws_alive = (self.websocket_server.thread is not None and
                           self.websocket_server.thread.is_alive())
                worker_alive = self.worker.is_alive()
                # Django 是通过 subprocess 启动的，检查进程是否仍在运行
                django_alive = (hasattr(self, 'django_process') and 
                               self.django_process and 
                               self.django_process.poll() is None)

                if not ws_alive:
                    print("[Main] 警告: WebSocket Server 线程已停止")
                if not worker_alive:
                    print("[Main] 警告: Worker 线程已停止")
                if not django_alive:
                    print("[Main] 警告: Django Server 线程已停止")

                # 使用短间隔睡眠以便及时响应 Ctrl+C
                # 总共等待5秒，但每次只睡0.1秒
                for _ in range(50):
                    if not self.running:
                        break
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n[Main] 收到键盘中断")
        finally:
            # 避免重复调用 stop（如果 _signal_handler 已经调用了）
            if not (hasattr(self, '_stopping') and self._stopping):
                self.stop()

    def stop(self):
        """停止所有服务"""
        print("\n[Main] 正在停止所有服务...")
        self.running = False

        # 首先发送停止信号给所有子进程（温和方式）
        # 停止 Worker（会停止机器人进程和截图器）
        if self.worker:
            try:
                print("[Main] 正在停止 Worker 和机器人...")
                self.worker.stop()
            except Exception as e:
                print(f"[Main] Worker 停止异常: {e}")

        # 停止 WebSocket
        if self.websocket_server:
            try:
                print("[Main] 正在停止 WebSocket...")
                self.websocket_server.stop()
            except Exception as e:
                print(f"[Main] WebSocket 停止异常: {e}")

        # 停止 Django（如果有进程）
        if hasattr(self, 'django_process') and self.django_process:
            print("[Main] 正在停止 Django...")
            try:
                self.django_process.terminate()
                # 给Django进程更多时间退出
                for _ in range(10):  # 等待最多5秒
                    if self.django_process.poll() is not None:
                        break
                    time.sleep(0.5)
                if self.django_process.poll() is None:
                    print("[Main] Django 未响应，强制终止...")
                    self.django_process.kill()
                    self.django_process.wait(timeout=2)
            except Exception as e:
                print(f"[Main] Django 停止异常: {e}")
                try:
                    self.django_process.kill()
                except:
                    pass

        # 停止 browser
        if self.browser:
            try:
                self.browser.stop()
            except:
                pass

        # 最后手段：强制终止所有残留的子进程
        self._kill_remaining_children()
        
        print("[Main] 所有服务已停止")
        
    def _kill_remaining_children(self):
        """清理所有残留的子进程"""
        import psutil
        import os
        
        current_process = psutil.Process(os.getpid())
        children = current_process.children(recursive=True)
        
        if children:
            print(f"[Main] 发现 {len(children)} 个残留子进程，正在清理...")
            for child in children:
                try:
                    print(f"[Main] 终止子进程 PID {child.pid}")
                    child.terminate()
                except:
                    pass
            
            # 等待一会儿
            gone, alive = psutil.wait_procs(children, timeout=3)
            
            # 强制杀死未退出的进程
            for child in alive:
                try:
                    print(f"[Main] 强制终止子进程 PID {child.pid}")
                    child.kill()
                except:
                    pass


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