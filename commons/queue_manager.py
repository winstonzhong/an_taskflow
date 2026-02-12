"""
数据队列管理模块
负责管理 WebSocket Server 与 Worker 之间的双向通信队列
"""

import queue
from typing import Any, Optional
import threading


class QueueManager:
    """
    队列管理器单例类
    管理两个核心队列：
    - ws_to_worker: WebSocket -> Worker (前端请求发送到后端处理)
    - worker_to_ws: Worker -> WebSocket (后端结果返回到前端)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, maxsize: int = 0):
        """
        初始化队列管理器

        Args:
            maxsize: 队列最大长度，0表示无限制
        """
        # 避免重复初始化
        if self._initialized:
            return

        self._maxsize = maxsize

        # WebSocket -> Worker 队列：存储前端发送的请求
        self.ws_to_worker: queue.Queue = queue.Queue(maxsize=maxsize)

        # Worker -> WebSocket 队列：存储Worker处理的结果
        self.worker_to_ws: queue.Queue = queue.Queue(maxsize=maxsize)

        self._initialized = True
        print("[QueueManager] 队列管理器初始化完成")

    def put_to_worker(self, data: Any, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        向 ws_to_worker 队列放入数据（WebSocket调用）

        Args:
            data: 要发送的数据
            block: 是否阻塞等待
            timeout: 阻塞超时时间

        Returns:
            bool: 是否成功放入
        """
        try:
            self.ws_to_worker.put(data, block=block, timeout=timeout)
            return True
        except queue.Full:
            print("[QueueManager] ws_to_worker 队列已满")
            return False

    def get_for_worker(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """
        从 ws_to_worker 队列获取数据（Worker调用）

        Args:
            block: 是否阻塞等待
            timeout: 阻塞超时时间

        Returns:
            获取的数据，超时时返回None
        """
        try:
            return self.ws_to_worker.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def put_to_ws(self, data: Any, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        向 worker_to_ws 队列放入数据（Worker调用）

        Args:
            data: 要发送的数据
            block: 是否阻塞等待
            timeout: 阻塞超时时间

        Returns:
            bool: 是否成功放入
        """
        try:
            self.worker_to_ws.put(data, block=block, timeout=timeout)
            return True
        except queue.Full:
            print("[QueueManager] worker_to_ws 队列已满")
            return False

    def get_for_ws(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """
        从 worker_to_ws 队列获取数据（WebSocket调用）

        Args:
            block: 是否阻塞等待
            timeout: 阻塞超时时间

        Returns:
            获取的数据，超时时返回None
        """
        try:
            return self.worker_to_ws.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def task_done_for_worker(self):
        """标记 ws_to_worker 队列的一个任务已完成"""
        self.ws_to_worker.task_done()

    def task_done_for_ws(self):
        """标记 worker_to_ws 队列的一个任务已完成"""
        self.worker_to_ws.task_done()

    def get_stats(self) -> dict:
        """获取队列统计信息"""
        return {
            "ws_to_worker_size": self.ws_to_worker.qsize(),
            "worker_to_ws_size": self.worker_to_ws.qsize(),
            "ws_to_worker_empty": self.ws_to_worker.empty(),
            "worker_to_ws_empty": self.worker_to_ws.empty(),
            "ws_to_worker_full": self.ws_to_worker.full(),
            "worker_to_ws_full": self.worker_to_ws.full(),
        }


# 便捷函数：获取队列管理器实例
def get_queue_manager(maxsize: int = 0) -> QueueManager:
    """获取队列管理器单例"""
    return QueueManager(maxsize=maxsize)