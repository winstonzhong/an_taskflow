"""
Mock 队列（内存实现）
模拟 Redis/RabbitMQ 的队列行为
"""

import time
import threading
from typing import Dict, List, Optional, Any


class MockQueue:
    """
    Mock 队列（内存实现）
    
    模拟 Redis/RabbitMQ 的队列行为
    """
    
    def __init__(self):
        self._pending: List[Dict] = []           # 待处理队列
        self._processing: Dict[str, Dict] = {}   # 处理中队列（按 task_id）
        self._dead_letter: List[Dict] = []       # 死信队列
        self._retry_count: Dict[int, int] = {}   # 重试计数
        self._lock = threading.Lock()
        
    def push(self, task: Dict) -> bool:
        """
        任务入队
        
        Args:
            task: {"id": int, "priority": int, ...}
            
        Returns:
            bool: 是否成功入队
        """
        with self._lock:
            self._pending.append(task)
            # 按优先级排序
            self._pending.sort(key=lambda x: x.get("priority", 999))
            return True
    
    def get(self, timeout: float = None) -> Optional[Dict]:
        """
        任务出队
        
        Args:
            timeout: 超时时间（本实现忽略，立即返回）
            
        Returns:
            任务字典，或 None（队列为空）
        """
        with self._lock:
            if not self._pending:
                return None
            
            task = self._pending.pop(0)
            task_id = task.get("id")
            
            # 移入处理中队列
            self._processing[task_id] = {
                "task": task,
                "started_at": time.time(),
            }
            
            return task
    
    def ack(self, task_id: int) -> bool:
        """
        确认任务完成
        
        Args:
            task_id: 任务 ID
            
        Returns:
            bool: 是否成功确认
        """
        with self._lock:
            if task_id in self._processing:
                del self._processing[task_id]
                # 清理重试计数
                if task_id in self._retry_count:
                    del self._retry_count[task_id]
                return True
            return False
    
    def nack(self, task_id: int, requeue: bool = True, max_retries: int = 3) -> bool:
        """
        否定确认（任务失败）
        
        Args:
            task_id: 任务 ID
            requeue: 是否重新入队
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否成功处理
        """
        with self._lock:
            if task_id not in self._processing:
                return False
            
            task_info = self._processing.pop(task_id)
            task = task_info["task"]
            
            if requeue:
                # 检查重试次数
                current_retries = self._retry_count.get(task_id, 0)
                
                if current_retries < max_retries:
                    self._retry_count[task_id] = current_retries + 1
                    self._pending.append(task)
                    self._pending.sort(key=lambda x: x.get("priority", 999))
                    return True
                else:
                    # 超过重试次数，进入死信队列
                    self._dead_letter.append({
                        "task": task,
                        "failed_at": time.time(),
                        "retries": current_retries
                    })
                    del self._retry_count[task_id]
                    return False
            else:
                # 不重试，直接丢弃
                if task_id in self._retry_count:
                    del self._retry_count[task_id]
                return True
    
    def size(self) -> int:
        """获取待处理队列长度"""
        with self._lock:
            return len(self._pending)
    
    def processing_size(self) -> int:
        """获取处理中队列长度"""
        with self._lock:
            return len(self._processing)
    
    def dead_letter_size(self) -> int:
        """获取死信队列长度"""
        with self._lock:
            return len(self._dead_letter)
    
    def get_retry_count(self, task_id: int) -> int:
        """获取任务重试次数"""
        return self._retry_count.get(task_id, 0)
    
    def clear(self):
        """清空所有队列"""
        with self._lock:
            self._pending.clear()
            self._processing.clear()
            self._dead_letter.clear()
            self._retry_count.clear()
