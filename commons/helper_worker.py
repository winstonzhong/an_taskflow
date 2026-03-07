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
from multiprocessing import Process, Queue as ProcessQueue
from multiprocessing.managers import DictProxy
from commons.queue_manager import get_queue_manager
from base.models import 定时任务, 配置表
from an_taskflow.settings import CONFIGS






# 屏幕截图模块
from commons.screen_capturer import ScreenCapturer, CaptureMethod
from commons.scrcpy_capturer import ScrcpyCapturer


def robot_process_main(robot_id: str, config: Dict, cmd_queue: ProcessQueue, shared_data: DictProxy):
    """
    机器人进程入口函数
    在独立进程中运行机器人业务逻辑
    
    Args:
        robot_id: 机器人ID
        config: 配置参数
        cmd_queue: 命令队列（主进程传入）
        shared_data: 共享数据字典
    """
    import signal
    
    # 子进程忽略 SIGINT (Ctrl+C)，由主进程统一处理
    # 但保留 SIGTERM 以便父进程可以优雅地终止子进程
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    # 子进程退出标志
    should_exit = threading.Event()
    
    def sigterm_handler(signum, frame):
        """处理 SIGTERM 信号（来自父进程的 terminate()）"""
        print(f"[Robot-{robot_id}] 收到 SIGTERM，准备退出...")
        should_exit.set()
    
    signal.signal(signal.SIGTERM, sigterm_handler)
    
    # 在子进程中设置 Django 环境
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "an_taskflow.settings")
    django.setup()
    
    from base.models import 定时任务
    from an_taskflow.settings import CONFIGS
    
    print(f"[Robot-{robot_id}] 进程已启动，PID: {os.getpid()}")
    
    # 更新共享状态
    shared_data[f'robot_{robot_id}_status'] = 'running'
    shared_data[f'robot_{robot_id}_pid'] = os.getpid()
    
    interval = config.get("interval", 5)
    loop_count = 0
    
    try:
        while not should_exit.is_set():
            try:
                # 检查命令队列（非阻塞，超时 0.1 秒）
                try:
                    cmd = cmd_queue.get(timeout=0.1)
                    if cmd.get('cmd') == 'stop':
                        print(f"[Robot-{robot_id}] 收到停止命令")
                        break
                except:
                    pass
                
                # 检查退出标志
                if should_exit.is_set():
                    break
                
                loop_count += 1
                print(f"[Robot-{robot_id}] 执行操作 #{loop_count}")
                
                # 执行业务逻辑
                定时任务.IP_PORT = CONFIGS.get('ip_port')
                
                try:
                    # 直接执行业务逻辑（同步方式）
                    # 注意：执行期间无法响应停止命令，需要等待本轮完成
                    定时任务.执行一轮定时任务(group_name__isnull=False)
                except Exception as task_e:
                    print(f"[Robot-{robot_id}] 业务逻辑执行异常: {task_e}")
                    shared_data[f'robot_{robot_id}_error'] = str(task_e)
                    # 出错后等待一下再继续
                    time.sleep(1)
                
                # 更新共享状态
                shared_data[f'robot_{robot_id}_loop_count'] = loop_count
                shared_data[f'robot_{robot_id}_last_active'] = time.time()
                
                # 等待间隔（分段等待以便及时响应退出信号）
                for _ in range(int(interval)):
                    if should_exit.is_set():
                        break
                    time.sleep(1)
                
            except Exception as e:
                print(f"[Robot-{robot_id}] 执行出错: {e}")
                shared_data[f'robot_{robot_id}_error'] = str(e)
                time.sleep(1)
    finally:
        # 进程退出前的清理
        print(f"[Robot-{robot_id}] 进程即将退出，共执行 {loop_count} 次")
        shared_data[f'robot_{robot_id}_status'] = 'stopped'
        shared_data[f'robot_{robot_id}_exit_time'] = time.time()




class RobotManager:
    """
    机器人管理器
    管理多个机器人进程的生命周期
    """

    def __init__(self):
        # 存储运行的机器人进程 {robot_id: Process}
        self.robots: Dict[str, Process] = {}
        # 存储进程命令队列 {robot_id: ProcessQueue}
        self.command_queues: Dict[str, ProcessQueue] = {}
        self.lock = threading.Lock()
        self.queue_manager = get_queue_manager()
        
        # 获取 Manager 用于进程间共享数据
        self.manager = self.queue_manager.get_manager()
        self.shared_data = self.queue_manager.shared_data
        
        # 初始化屏幕截图器（ADB 模式）
        screen_capture_config = CONFIGS.get('screen_capture', {})
        capture_interval = screen_capture_config.get('interval', 2.0)   # 默认 0.5fps（2秒间隔）
        capture_quality = screen_capture_config.get('quality', 80)      # 默认80%质量
        capture_scale = screen_capture_config.get('scale', 0.5)         # 默认50%缩放
        
        # 从配置文件读取设备IP，确保截图和执行任务使用同一设备
        capture_device = CONFIGS.get('ip_port')
        if capture_device:
            print(f"[RobotManager] 截图器将使用配置设备: {capture_device}")
        else:
            print("[RobotManager] 警告: 配置文件中未找到 ip_port，截图器将自动选择设备")
        
        # 优先使用 ScrcpyCapturer（真正的视频流），降级到 ScreenCapturer
        self.scrcpy_capturer = ScrcpyCapturer(
            device_serial=capture_device,  # 使用配置文件中的 ip_port
            capture_interval=capture_interval,
            quality=capture_quality,
            scale=capture_scale,
            max_size=720,
            bit_rate=2000000,
            max_fps=30
        )
        # 设置截图回调
        self.scrcpy_capturer.on_capture = self._on_screenshot
        self.scrcpy_capturer.on_error = self._on_screenshot_error
        self.scrcpy_capturer.on_status_change = self._on_screenshot_status_change
        
        # 保留 ScreenCapturer 作为降级方案
        self.screen_capturer = None  # 降级方案占位
        
        self.frame_count = 0

    def _on_screenshot(self, screenshot_bytes: bytes):
        """截图回调：推送截图到前端"""
        self.frame_count += 1
        result = {
            'type': 'screenshot_data',
            'data': screenshot_bytes,
            'frame_count': self.frame_count,
            'timestamp': time.time()
        }
        
        success = self.queue_manager.put_to_ws(result, block=False)
        if success:
            # 每10帧打印一次日志，避免日志过多
            if self.frame_count % 10 == 0:
                print(f"[RobotManager] 截图帧 #{self.frame_count} 已发送 ({len(screenshot_bytes)} bytes)")
        else:
            print(f"[RobotManager] 警告: 结果队列已满，screenshot_data消息可能丢失")
    
    def _on_screenshot_error(self, error_msg: str):
        """截图错误回调"""
        # 发送错误状态到前端
        result = {
            'type': 'device_status',
            'connected': False,
            'error': error_msg,
            'timestamp': time.time()
        }
        self.queue_manager.put_to_ws(result, block=False)
    
    def _on_screenshot_status_change(self, status: str):
        """截图状态变化回调"""
        connected = status == "running"
        result = {
            'type': 'device_status',
            'connected': connected,
            'status': status,
            'timestamp': time.time()
        }
        self.queue_manager.put_to_ws(result, block=False)

    def start_robot(self, robot_id: str, config: Dict) -> bool:
        """
        启动一个机器人进程

        Args:
            robot_id: 机器人唯一标识
            config: 机器人配置参数

        Returns:
            bool: 是否成功启动
        """
        with self.lock:
            # 检查是否已存在且正在运行
            if robot_id in self.robots and self.robots[robot_id].is_alive():
                print(f"[RobotManager] 机器人 {robot_id} 已在运行中")
                return False

            # 清理旧的队列（如果存在）
            if robot_id in self.command_queues:
                self.queue_manager.remove_process_queue(robot_id)

            # 创建进程间通信队列
            cmd_queue = self.queue_manager.create_process_queue(robot_id)
            self.command_queues[robot_id] = cmd_queue

            # 创建并启动进程
            process = Process(
                target=robot_process_main,
                args=(robot_id, config, cmd_queue, self.shared_data),
                daemon=True,
                name=f"Robot-{robot_id}"
            )
            process.start()
            self.robots[robot_id] = process
            
            # 启动截图器（实时截图，不等待任务执行）
            if not self.scrcpy_capturer._running:
                print(f"[RobotManager] 启动截图器...")
                self.scrcpy_capturer.start()

            print(f"[RobotManager] 机器人 {robot_id} 已启动，PID: {process.pid}")
            return True

    def stop_robot(self, robot_id: str, force: bool = False, timeout: float = 5.0) -> tuple:
        """
        停止指定机器人

        Args:
            robot_id: 机器人唯一标识
            force: 是否强制终止（True=立即强制终止，False=温和停止）
            timeout: 温和停止的超时时间（秒）

        Returns:
            tuple: (success: bool, is_immediate: bool)
                   success: 是否成功发送停止命令/执行停止
                   is_immediate: 是否立即停止完成（强制模式为True，温和模式为False）
        """
        with self.lock:
            if robot_id not in self.robots:
                print(f"[RobotManager] 机器人 {robot_id} 不存在")
                return False, True

            process = self.robots[robot_id]
            
            if force:
                # 强制终止：立即发送 SIGTERM，超时后 SIGKILL
                print(f"[RobotManager] 强制终止机器人 {robot_id} (PID: {process.pid})")
                process.terminate()  # SIGTERM
                process.join(timeout=1)
                if process.is_alive():
                    print(f"[RobotManager] 机器人 {robot_id} 未响应 SIGTERM，发送 SIGKILL")
                    process.kill()  # SIGKILL
                    process.join(timeout=1)
                
                # 强制模式下立即清理
                self._cleanup(robot_id)
                
                # 停止截图器（所有机器人停止时）
                if len(self.robots) == 0 and self.scrcpy_capturer._running:
                    print(f"[RobotManager] 停止截图器...")
                    self.scrcpy_capturer.stop()
                
                print(f"[RobotManager] 机器人 {robot_id} 已强制终止")
                return True, True  # (success, is_immediate)
            else:
                # 温和停止：发送停止命令，不等待进程退出（后台等待）
                print(f"[RobotManager] 发送停止命令给机器人 {robot_id}")
                
                # 标记正在停止状态
                if self.shared_data:
                    self.shared_data[f'robot_{robot_id}_stopping'] = True
                
                if robot_id in self.command_queues:
                    try:
                        self.command_queues[robot_id].put({'cmd': 'stop'})
                    except Exception as e:
                        print(f"[RobotManager] 发送停止命令失败: {e}")
                        return False, True
                
                # 启动后台线程等待进程退出并清理
                def wait_and_cleanup(rm_self, qm):
                    process.join(timeout=timeout)
                    if process.is_alive():
                        print(f"[RobotManager] 机器人 {robot_id} 超时未退出，强制终止")
                        process.terminate()
                        process.join(timeout=2)
                        if process.is_alive():
                            process.kill()
                            process.join()
                    
                    # 清除停止标记
                    if rm_self.shared_data:
                        rm_self.shared_data[f'robot_{robot_id}_stopping'] = False
                    
                    # 清理资源
                    rm_self._cleanup(robot_id)
                    
                    # 停止截图器（所有机器人停止时）
                    screenshot_stopped = False
                    if len(rm_self.robots) == 0 and rm_self.scrcpy_capturer._running:
                        print(f"[RobotManager] 停止截图器...")
                        rm_self.scrcpy_capturer.stop()
                        screenshot_stopped = True
                    
                    print(f"[RobotManager] 机器人 {robot_id} 已停止")
                    
                    # 发送截图停止通知（醒目的提示）
                    if screenshot_stopped:
                        try:
                            screenshot_stop_msg = {
                                "type": "screenshot_stopped",
                                "success": True,
                                "message": "📷 图片流传输已停止",
                                "timestamp": time.time()
                            }
                            qm.put_to_ws(screenshot_stop_msg, block=False)
                            print(f"[RobotManager] 已发送截图停止通知")
                        except Exception as e:
                            print(f"[RobotManager] 发送截图停止通知失败: {e}")
                    
                    # 发送机器人状态更新通知到前端（广播给所有客户端）
                    try:
                        status_msg = {
                            "type": "robot_status",
                            "state": "stopped",
                            "success": True,
                            "robot_id": robot_id,
                            "message": f"机器人 {robot_id} 已完全停止",
                            "screenshot_stopped": screenshot_stopped
                        }
                        qm.put_to_ws(status_msg, block=False)
                        print(f"[RobotManager] 已发送停止完成通知")
                    except Exception as e:
                        print(f"[RobotManager] 发送状态通知失败: {e}")
                
                cleanup_thread = threading.Thread(
                    target=wait_and_cleanup, 
                    args=(self, self.queue_manager),
                    daemon=True
                )
                cleanup_thread.start()
                
                # 温和模式下返回 is_immediate=False，表示后台正在停止
                return True, False  # (success, is_immediate)
    
    def _cleanup(self, robot_id: str):
        """清理指定机器人的资源"""
        with self.lock:
            # 从字典中移除
            if robot_id in self.robots:
                del self.robots[robot_id]
            
            # 移除命令队列
            if robot_id in self.command_queues:
                self.queue_manager.remove_process_queue(robot_id)
                del self.command_queues[robot_id]
            
            # 更新共享数据
            if self.shared_data:
                self.shared_data[f'robot_{robot_id}_status'] = 'stopped'
                self.shared_data[f'robot_{robot_id}_cleanup_time'] = time.time()

    def stop_all_robots(self, force: bool = False):
        """
        停止所有机器人
        
        Args:
            force: 是否强制终止
        """
        with self.lock:
            robot_ids = list(self.robots.keys())

        if not robot_ids:
            return

        print(f"[RobotManager] 停止 {len(robot_ids)} 个机器人 (force={force})...")
        
        for robot_id in robot_ids:
            try:
                success, is_immediate = self.stop_robot(robot_id, force=force)
                if success and not is_immediate and not force:
                    # 温和停止，需要等待后台线程完成
                    print(f"[RobotManager] 机器人 {robot_id} 正在后台停止中...")
            except Exception as e:
                print(f"[RobotManager] 停止机器人 {robot_id} 时出错: {e}")
        
        # 如果不是强制模式，等待一段时间让机器人退出
        if not force:
            import time
            time.sleep(2)
            
            # 检查是否还有存活的机器人
            still_alive = []
            with self.lock:
                for rid in robot_ids:
                    if rid in self.robots and self.robots[rid].is_alive():
                        still_alive.append(rid)
            
            if still_alive:
                print(f"[RobotManager] {len(still_alive)} 个机器人仍在运行，强制终止...")
                for rid in still_alive:
                    try:
                        self.stop_robot(rid, force=True)
                    except Exception as e:
                        print(f"[RobotManager] 强制停止机器人 {rid} 时出错: {e}")
        
        # 确保截图器也被停止
        if self.scrcpy_capturer._running:
            print("[RobotManager] 停止截图器...")
            try:
                self.scrcpy_capturer.stop()
            except Exception as e:
                print(f"[RobotManager] 停止截图器时出错: {e}")

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
                    process = self.robots[robot_id]
                    is_alive = process.is_alive()
                    
                    # 检查是否正在停止（共享数据中标记）
                    is_stopping = False
                    if self.shared_data:
                        is_stopping = self.shared_data.get(f'robot_{robot_id}_stopping', False)
                    
                    status = {
                        "robot_id": robot_id,
                        "is_alive": is_alive,
                        "is_stopping": is_stopping,
                        "pid": process.pid if is_alive else None,
                    }
                    # 从共享数据中获取更多信息
                    if self.shared_data:
                        status["loop_count"] = self.shared_data.get(f'robot_{robot_id}_loop_count', 0)
                        status["last_error"] = self.shared_data.get(f'robot_{robot_id}_error', None)
                        # 机器人已停止且清理完成
                        if not is_alive and not is_stopping:
                            status["status"] = "stopped"
                        elif is_stopping:
                            status["status"] = "stopping"
                        else:
                            status["status"] = "running"
                    return status
                return {"error": "机器人不存在", "status": "stopped"}

            # 返回所有机器人状态
            result = {}
            for rid, process in self.robots.items():
                is_alive = process.is_alive()
                is_stopping = self.shared_data.get(f'robot_{rid}_stopping', False) if self.shared_data else False
                result[rid] = {
                    "is_alive": is_alive,
                    "is_stopping": is_stopping,
                    "pid": process.pid if process.is_alive() else None,
                }
                if self.shared_data:
                    result[rid]["loop_count"] = self.shared_data.get(f'robot_{rid}_loop_count', 0)
            return result





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
                    "state": "stopped",
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
                # 启动失败，返回当前实际状态
                current_status = self.robot_manager.get_robot_status(robot_id)
                actual_state = "stopped"
                if current_status and not current_status.get("error"):
                    if current_status.get("is_alive"):
                        actual_state = "running"
                
                return {
                    "type": "robot_status",
                    "state": actual_state,
                    "success": False,
                    "robot_id": robot_id,
                    "error": "机器人已在运行中或启动失败"
                }

        except Exception as e:
            print(f"[Worker] start_robot 处理失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "type": "robot_status",
                "state": "stopped",
                "success": False,
                "error": str(e)
            }

    def _handle_stop_robot(self, data: Dict) -> Dict:
        """
        处理 stop_robot 类型：停止机器人进程

        期望数据格式：
        {
            "type": "stop_robot",
            "robot_id": "robot_001",
            "force": false  // 可选，默认为 false（温和停止），true 为强制终止
        }
        
        返回数据格式：
        {
            "type": "robot_status",
            "state": "stopped" | "stopping" | "running",
            "success": true | false,
            ...
        }
        """
        try:
            robot_id = data.get("robot_id")
            force = data.get("force", False)

            if not robot_id:
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": False,
                    "error": "缺少 robot_id 参数"
                }

            # 先检查当前状态
            current_status = self.robot_manager.get_robot_status(robot_id)
            if current_status and current_status.get("error"):
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": False,
                    "robot_id": robot_id,
                    "error": "机器人不存在"
                }

            # 停止机器人（支持强制终止）
            # stop_robot 返回 (success, is_immediate)
            success, is_immediate = self.robot_manager.stop_robot(robot_id, force=force)

            if success:
                if is_immediate:
                    # 强制停止或已立即停止
                    return {
                        "type": "robot_status",
                        "state": "stopped",
                        "success": True,
                        "robot_id": robot_id,
                        "force": force,
                        "message": f"机器人 {robot_id} 已{'强制终止' if force else '停止'}"
                    }
                else:
                    # 温和停止，后台正在等待进程退出
                    return {
                        "type": "robot_status",
                        "state": "stopping",
                        "success": True,
                        "robot_id": robot_id,
                        "force": force,
                        "message": f"机器人 {robot_id} 正在停止中..."
                    }
            else:
                return {
                    "type": "robot_status",
                    "state": "stopped",
                    "success": False,
                    "robot_id": robot_id,
                    "error": "停止机器人失败"
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
        
        if state_data and state_data.get("error"):
            return {
                "type": "robot_status",
                "success": True,  # 查询成功
                "state": "stopped",
                "robot_id": robot_id,
                "exists": False,
                "message": "机器人不存在"
            }
        
        is_alive = state_data.get('is_alive', False)
        is_stopping = state_data.get('is_stopping', False)
        
        if is_stopping:
            state = 'stopping'
        elif is_alive:
            state = 'running'
        else:
            state = 'stopped'

        return {
            "type": "robot_status",
            "success": True,
            "state": state,
            "robot_id": robot_id,
            "exists": True,
            "is_alive": is_alive,
            "pid": state_data.get('pid'),
            "loop_count": state_data.get('loop_count', 0)
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
        
        poll_count = 0  # 轮询计数器

        while self.running:
            try:
                # 轮询开始日志（每 10 次打印一次）
                poll_count += 1
                if poll_count % 10 == 0:
                    print(f"[Worker-{thread_id}] 进入第 {poll_count} 次轮询，等待任务...")
                
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

    def stop(self, timeout: float = 10.0):
        """
        停止 Worker
        
        Args:
            timeout: 总超时时间（秒），默认 10 秒
        """
        print("[Worker] 正在停止...")
        start_time = time.time()
        self.running = False

        # 首先温和停止所有机器人（给它们机会优雅退出）
        print("[Worker] 正在停止所有机器人...")
        self.robot_manager.stop_all_robots(force=False)
        
        # 轮询等待机器人进程退出（而不是固定 sleep）
        graceful_timeout = min(3.0, timeout * 0.3)  # 优雅关闭最多 3 秒或 30% 超时时间
        elapsed = 0
        check_interval = 0.1
        while elapsed < graceful_timeout:
            remaining = [rid for rid in self.robot_manager.robots.keys() 
                         if self.robot_manager.robots[rid].is_alive()]
            if not remaining:
                print(f"[Worker] 所有机器人已优雅退出")
                break
            time.sleep(check_interval)
            elapsed += check_interval
        
        # 检查是否还有存活的机器人，如果有则强制停止
        remaining = [rid for rid in self.robot_manager.robots.keys() 
                     if self.robot_manager.robots[rid].is_alive()]
        if remaining:
            print(f"[Worker] 发现 {len(remaining)} 个机器人未停止，强制终止...")
            self.robot_manager.stop_all_robots(force=True)
            
            # 等待强制终止完成
            force_timeout = min(2.0, timeout * 0.2)
            elapsed = 0
            while elapsed < force_timeout:
                remaining = [rid for rid in self.robot_manager.robots.keys() 
                             if self.robot_manager.robots[rid].is_alive()]
                if not remaining:
                    break
                time.sleep(0.1)
                elapsed += 0.1

        # 停止截图器
        if hasattr(self.robot_manager, 'scrcpy_capturer') and self.robot_manager.scrcpy_capturer._running:
            print("[Worker] 正在停止截图器...")
            self.robot_manager.scrcpy_capturer.stop()

        # 等待所有工作线程结束
        print("[Worker] 等待工作线程结束...")
        remaining_timeout = timeout - (time.time() - start_time)
        for i, thread in enumerate(self.threads):
            if thread.is_alive() and remaining_timeout > 0:
                thread.join(timeout=remaining_timeout)
                if thread.is_alive():
                    print(f"[Worker] 警告: 工作线程 {i} 未在超时内结束")
                remaining_timeout = timeout - (time.time() - start_time)

        # 清理僵尸进程
        try:
            import os
            import signal
            os.waitpid(-1, os.WNOHANG)
        except:
            pass

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