"""
Worker 模块
监听 ws_to_worker 队列，处理业务逻辑，将结果推送到 worker_to_ws 队列
集成 Django 环境，支持数据库操作和机器人管理
"""
import os


import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "an_taskflow.settings")
django.setup()

import threading
import time
import json
import os
import sys
import traceback
from typing import Callable, Dict, Any, Optional
from commons.queue_manager import get_queue_manager
from base.models import 定时任务, 配置表
from an_taskflow.settings import CONFIGS






try:
    from PIL import Image, ImageDraw, ImageFont
    import io
except ImportError:
    Image = None
    print("未安装 PIL/Pillow，将使用模拟 Base64 图片数据（前端无法正常渲染真实图片）")



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
            print(f"生成截图失败: {e}")
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









class RobotManager:
    """
    机器人管理器
    管理多个机器人线程的生命周期
    """

    def __init__(self):
        # 存储运行的机器人线程 {robot_id: thread}
        self.robots: Dict[str, threading.Thread] = {}
        # 存储机器人停止标志 {robot_id: threading.Event}
        self.stop_events: Dict[str, threading.Event] = {}
        self.lock = threading.Lock()
        self.queue_manager = get_queue_manager()
        self.screenshot_generator = ScreenshotGenerator()
        self.frame_count = 0

    def start_robot(self, robot_id: str, config: Dict) -> bool:
        """
        启动一个机器人线程

        Args:
            robot_id: 机器人唯一标识
            config: 机器人配置参数

        Returns:
            bool: 是否成功启动
        """
        with self.lock:
            # 检查是否已存在
            if robot_id in self.robots and self.robots[robot_id].is_alive():
                print(f"[RobotManager] 机器人 {robot_id} 已在运行中")
                return False

            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[robot_id] = stop_event

            # 创建并启动线程
            thread = threading.Thread(
                target=self._robot_loop,
                args=(robot_id, config, stop_event),
                daemon=True,
                name=f"Robot-{robot_id}"
            )
            thread.start()
            self.robots[robot_id] = thread

            print(f"[RobotManager] 机器人 {robot_id} 已启动")
            return True

    def stop_robot(self, robot_id: str) -> bool:
        """
        停止指定机器人

        Args:
            robot_id: 机器人唯一标识

        Returns:
            bool: 是否成功停止
        """
        with self.lock:
            if robot_id not in self.robots:
                print(f"[RobotManager] 机器人 {robot_id} 不存在")
                return False

            # 设置停止标志
            if robot_id in self.stop_events:
                self.stop_events[robot_id].set()

            print(f"[RobotManager] 机器人 {robot_id} 停止信号已发送")
            return True

    def stop_all_robots(self):
        """停止所有机器人"""
        with self.lock:
            robot_ids = list(self.robots.keys())

        for robot_id in robot_ids:
            self.stop_robot(robot_id)

    def get_robot_status(self, robot_id: Optional[str] = None) -> Dict:
        """
        获取机器人状态

        Args:
            robot_id: 指定机器人ID，None则返回所有

        Returns:
            状态信息字典
        """
        with self.lock:
            if robot_id:
                if robot_id in self.robots:
                    return {
                        "robot_id": robot_id,
                        "is_alive": self.robots[robot_id].is_alive(),
                        "is_stopping": self.stop_events.get(robot_id, threading.Event()).is_set()
                    }
                return {"error": "机器人不存在"}

            # 返回所有机器人状态
            return {
                rid: {
                    "is_alive": t.is_alive(),
                    "is_stopping": self.stop_events.get(rid, threading.Event()).is_set()
                }
                for rid, t in self.robots.items()
            }

    def _robot_loop(self, robot_id: str, config: Dict, stop_event: threading.Event):
        """
        机器人主循环（死循环，直到收到停止信号）

        Args:
            robot_id: 机器人ID
            config: 配置参数
            stop_event: 停止事件标志
        """
        print(f"[Robot-{robot_id}] 机器人线程启动，配置: {config}")

        # 模拟机器人初始化
        interval = config.get("interval", 5)  # 默认5秒执行一次

        loop_count = 0
        while not stop_event.is_set():
            try:
                loop_count += 1
                print(f"[Robot-{robot_id}] 执行操作 #{loop_count}")

                # ====== 在这里实现具体的机器人业务逻辑 ======
                # 例如：
                # - 爬取数据
                # - 发送消息
                # - 监控状态
                # - 定时任务等

                # 示例：模拟业务操作
                self._do_robot_work(robot_id, config, loop_count)

                # 等待间隔或停止信号
                # 使用 wait 而不是 time.sleep，这样可以及时响应停止信号
                if stop_event.wait(timeout=interval):
                    break

            except Exception as e:
                print(f"[Robot-{robot_id}] 执行出错: {e}")
                time.sleep(1)  # 出错后短暂休眠

        print(f"[Robot-{robot_id}] 机器人线程已停止，共执行 {loop_count} 次")

        # 清理资源
        with self.lock:
            if robot_id in self.robots:
                del self.robots[robot_id]
            if robot_id in self.stop_events:
                del self.stop_events[robot_id]

    def _do_robot_work(self, robot_id: str, config: Dict, iteration: int):
        """
        执行具体的机器人业务逻辑

        这里可以实现：
        - API 调用
        - 数据库操作
        - 文件处理
        - 消息发送等
        """
        # 示例：打印日志，实际业务中替换为真实逻辑
        task_type = config.get("task_type", "default")
        print(f"[Robot-{robot_id}] 正在执行任务: {task_type}, 第 {iteration} 次迭代")
        # 如果需要 Django ORM 操作，可以在这里导入并使用

        print('ip_port', CONFIGS.get('ip_port'))

        screenshot_bytes = self.screenshot_generator.generate()

        if screenshot_bytes:
            self.frame_count += 1
            result = {
                'type': 'screenshot_data',
                'data': screenshot_bytes,
                'frame_count': self.frame_count,
                'timestamp': time.time()
            }

            success = self.queue_manager.put_to_ws(result, block=False)
            if not success:
                print(f"警告: 结果队列已满，screenshot_data消息可能丢失")

        定时任务.IP_PORT = CONFIGS.get('ip_port')
        定时任务.执行一轮定时任务(group_name__isnull=False)



class Worker:
    """
    工作进程
    消费 ws_to_worker 队列，处理业务，生产到 worker_to_ws 队列
    集成 Django 环境
    """

    def __init__(self, worker_id: Optional[str] = None, num_threads: int = 2):
        self.worker_id = worker_id or f"worker-{threading.current_thread().ident}"
        self.queue_manager = get_queue_manager()
        self.num_threads = num_threads

        self.threads: list[threading.Thread] = []
        self.running = False

        # 初始化机器人管理器
        self.robot_manager = RobotManager()

        # 初始化 Django 环境
        # self._setup_django()

        # 业务处理器注册表
        self.handlers: Dict[str, Callable] = {}
        self._register_handlers()

    # def _setup_django(self):
    #     """初始化 Django 环境"""
    #     import os
    #     import django
    #     os.environ.setdefault("DJANGO_SETTINGS_MODULE", "an_taskflow.settings")
    #     django.setup()

    def _register_handlers(self):
        """注册业务处理器"""
        # 核心处理器
        self.handlers["group_switch"] = self._handle_group_switch
        self.handlers["start_robot"] = self._handle_start_robot
        self.handlers["stop_robot"] = self._handle_stop_robot
        self.handlers["query_robot_status"] = self._handle_robot_status
        self.handlers["echo"] = self._handle_echo

        print(f"[Worker] 已注册处理器: {list(self.handlers.keys())}")

    def _handle_group_switch(self, data: Dict) -> Dict:
        """
        处理 group_switch 类型：保存数据到数据库
        """
        try:
            selected_list = data.get('selected')
            unselected_list = data.get('unselected')
            # print('selected_list', selected_list)
            # print('unselected_list', unselected_list)

            if selected_list:
                定时任务.更新技能激活状态(selected_list, True)
                group_status_data = {i: True for i in selected_list}

            elif unselected_list:
                定时任务.更新技能激活状态(unselected_list, False)
                group_status_data = {i: False for i in unselected_list}

            ret_data = {
                'type': 'group_switch_result',
                'group_status_data': group_status_data,
                'timestamp': time.time(),
            }

            return ret_data

        except Exception as e:
            print(f"[Worker] group_switch 处理失败: {e}")
            return {
                "type": "group_switch_response",
                "success": False,
                "error": str(e)
            }

    def _handle_start_robot(self, data: Dict) -> Dict:
        """
        处理 start_robot 类型：启动机器人线程

        期望数据格式：
        {
            "type": "start_robot",
            "robot_id": "robot_001",
            "config": {
                "interval": 5,
                "task_type": "monitor",
                ...
            }
        }
        """
        try:
            robot_id = data.get("robot_id")
            config = data.get("config", {})

            if not robot_id:
                return {
                    "type": "robot_status",
                    "state": "running",
                    "success": False,
                    "error": "缺少 robot_id 参数"
                }

            # 启动机器人
            success = self.robot_manager.start_robot(robot_id, config)

            if success:
                return {
                    "type": "robot_status",
                    "state": "running",
                    "success": True,
                    "robot_id": robot_id,
                    "message": f"机器人 {robot_id} 启动成功"
                }
            else:
                return {
                    "type": "robot_status",
                    "state": "running",
                    "success": False,
                    "robot_id": robot_id,
                    "error": "机器人已在运行中"
                }

        except Exception as e:
            print(f"[Worker] start_robot 处理失败: {e}")
            return {
                "type": "robot_status",
                "state": "running",
                "success": False,
                "error": str(e)
            }

    def _handle_stop_robot(self, data: Dict) -> Dict:
        """
        处理 stop_robot 类型：停止机器人线程

        期望数据格式：
        {
            "type": "stop_robot",
            "robot_id": "robot_001"
        }
        """
        try:
            robot_id = data.get("robot_id")

            if not robot_id:
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": False,
                    "error": "缺少 robot_id 参数"
                }

            # 停止机器人
            success = self.robot_manager.stop_robot(robot_id)

            if success:
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": True,
                    "robot_id": robot_id,
                    "message": f"机器人 {robot_id} 停止信号已发送"
                }
            else:
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": False,
                    "robot_id": robot_id,
                    "error": "机器人不存在或已停止"
                }

        except Exception as e:
            print(f"[Worker] stop_robot 处理失败: {e}")
            return {
                "type": "robot_status",
                "success": False,
                "error": str(e)
            }

    def _handle_robot_status(self, data: Dict) -> Dict:
        """查询机器人状态"""
        robot_id = data.get("robot_id")
        state_data = self.robot_manager.get_robot_status(robot_id)
        is_alive = state_data.get('is_alive')
        is_stopping = state_data.get('is_stopping')
        if is_stopping:
            state = 'stopping'
        elif is_alive:
            state = 'running'
        else:
            state = 'stopped'
        
        return {
            "type": "robot_status",
            "success": True,
            "state": state
        }

    def _handle_echo(self, data: Dict) -> Dict:
        """回声处理器（测试用）"""
        return {
            "type": "echo_response",
            "original_data": data,
            "timestamp": time.time(),
            "worker_id": self.worker_id
        }

    def process_message(self, data: Dict) -> Dict:
        """
        处理单条消息

        Args:
            data: 从队列获取的消息数据

        Returns:
            处理结果
        """
        # 提取消息类型
        msg_type = data.get("type", "echo")

        # 保留客户端路由信息
        client_id = data.get("_client_id")
        websocket_id = data.get("_websocket_id")

        # 查找处理器
        handler = self.handlers.get(msg_type)

        if handler:
            try:
                result = handler(data)
            except Exception as e:
                result = {
                    "type": "error",
                    "message": f"处理异常: {str(e)}"
                }
        else:
            result = {
                "type": "error",
                "message": f"未知消息类型: {msg_type}",
                "supported_types": list(self.handlers.keys())
            }

        # 添加路由信息到结果，以便WebSocket知道发送给谁
        if client_id:
            result["_target_client_id"] = client_id
        if websocket_id:
            result["_target_websocket_id"] = websocket_id

        # 添加处理元信息
        result["_processed_by"] = self.worker_id
        result["_processing_time"] = time.time()

        return result

    def worker_loop(self, thread_id: int):
        """
        单个工作线程的主循环

        Args:
            thread_id: 线程标识
        """
        print(f"[Worker] 工作线程 {thread_id} 已启动")

        while self.running:
            try:
                # 从队列获取数据（阻塞等待）
                data = self.queue_manager.get_for_worker(block=True, timeout=0.5)

                if data is None:
                    continue

                print(f"[Worker-{thread_id}] 收到任务: {data.get('type', 'unknown')}")

                # 处理消息
                result = self.process_message(data)

                # 标记任务完成
                self.queue_manager.task_done_for_worker()

                # 将结果推送到 worker_to_ws 队列
                success = self.queue_manager.put_to_ws(result, block=False)
                if not success:
                    print(f"[Worker-{thread_id}] 警告: 结果队列已满，消息可能丢失")

                print(f"[Worker-{thread_id}] 任务处理完成，结果已推送")

            except Exception as e:
                traceback.print_exc()
                if self.running:
                    print(f"[Worker-{thread_id}] 处理错误: {e}")
                time.sleep(0.1)

        print(f"[Worker] 工作线程 {thread_id} 已停止")

    def start(self):
        """启动Worker（启动多个工作线程）"""
        print(f"[Worker] 启动 {self.num_threads} 个工作线程...")
        self.running = True

        for i in range(self.num_threads):
            thread = threading.Thread(
                target=self.worker_loop,
                args=(i,),
                daemon=True,
                name=f"WorkerThread-{i}"
            )
            thread.start()
            self.threads.append(thread)

        print(f"[Worker] Worker {self.worker_id} 已启动")

    def stop(self):
        """停止Worker"""
        print("[Worker] 正在停止...")
        self.running = False

        # 停止所有机器人
        print("[Worker] 正在停止所有机器人...")
        self.robot_manager.stop_all_robots()

        # 等待所有工作线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)

        print("[Worker] 已停止")

    def is_alive(self) -> bool:
        """检查Worker是否仍在运行"""
        return any(t.is_alive() for t in self.threads)


# 便捷启动函数
def start_worker(num_threads: int = 2) -> Worker:
    """启动Worker并返回实例"""
    worker = Worker(num_threads=num_threads)
    worker.start()
    return worker


def open_browser():
    """延迟打开浏览器（等待Django服务启动）"""
    import webbrowser
    time.sleep(3)
    sn = 配置表.获取sn()
    sn_arg = f'?sn={sn}' if sn else ''
    url = f"http://localhost:8001/base/control{sn_arg}"
    try:
        webbrowser.open(url)  # 打开默认浏览器
    except Exception as e:
        print(f"打开浏览器失败：{e}")


def start_browser_worker():
    thread = threading.Thread(target=open_browser, daemon=True)
    thread.start()
    return thread