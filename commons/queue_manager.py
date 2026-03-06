"""
数据队列管理模块
负责管理 WebSocket Server 与 Worker 之间的双向通信队列
支持线程队列和进程队列
"""

import queue
from typing import Any, Optional
import threading
from multiprocessing import Queue as ProcessQueue


class QueueManager:
    """
    队列管理器单例类
    管理核心队列：
    - ws_to_worker: WebSocket -> Worker (前端请求发送到后端处理)
    - worker_to_ws: Worker -> WebSocket (后端结果返回到前端)
    - process_queues: 主进程与子进程间的通信队列
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

        # WebSocket -> Worker 队列：存储前端发送的请求（线程间）
        self.ws_to_worker: queue.Queue = queue.Queue(maxsize=maxsize)

        # Worker -> WebSocket 队列：存储Worker处理的结果（线程间）
        self.worker_to_ws: queue.Queue = queue.Queue(maxsize=maxsize)
        
        # 进程间通信队列：用于主进程向子进程发送命令
        self.process_command_queues: dict[str, ProcessQueue] = {}
        
        # 进程间共享数据：用于子进程向主进程上报状态
        # 注意：Manager 对象在首次创建时会启动一个服务进程
        self._manager = None
        self.shared_data = None

        self._initialized = True
        print("[QueueManager] 队列管理器初始化完成")
    
    def get_manager(self):
        """
        获取 Manager 对象（用于进程间共享数据）
        延迟初始化，避免过早启动服务进程
        """
        if self._manager is None:
            from multiprocessing import Manager
            self._manager = Manager()
            self.shared_data = self._manager.dict()
            print("[QueueManager] Manager 初始化完成")
        return self._manager
    
    def create_process_queue(self, robot_id: str) -> ProcessQueue:
        """
        为指定机器人创建进程间通信队列
        
        Args:
            robot_id: 机器人ID
            
        Returns:
            ProcessQueue: 进程队列
        """
        if robot_id in self.process_command_queues:
            return self.process_command_queues[robot_id]
        
        q = ProcessQueue()
        self.process_command_queues[robot_id] = q
        return q
    
    def get_process_queue(self, robot_id: str) -> Optional[ProcessQueue]:
        """
        获取指定机器人的进程队列
        
        Args:
            robot_id: 机器人ID
            
        Returns:
            ProcessQueue 或 None
        """
        return self.process_command_queues.get(robot_id)
    
    def remove_process_queue(self, robot_id: str):
        """
        移除指定机器人的进程队列
        
        Args:
            robot_id: 机器人ID
        """
        if robot_id in self.process_command_queues:
            # 清空队列
            q = self.process_command_queues[robot_id]
            while not q.empty():
                try:
                    q.get_nowait()
                except:
                    break
            del self.process_command_queues[robot_id]

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
            "process_queues_count": len(self.process_command_queues),
        }


# 便捷函数：获取队列管理器实例
def get_queue_manager(maxsize: int = 0) -> QueueManager:
    """获取队列管理器单例"""
    return QueueManager(maxsize=maxsize)
