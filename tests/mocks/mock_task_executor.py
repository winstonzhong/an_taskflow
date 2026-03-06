"""
Mock 任务执行器
完全替代真实的 ADB 任务执行，只模拟执行结果
"""

import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "待执行"
    RUNNING = "执行中"
    SUCCESS = "成功"
    FAILED = "失败"
    TIMEOUT = "超时"


class TaskExecutorError(Exception):
    """任务执行异常"""
    pass


class TaskTimeoutError(TaskExecutorError):
    """任务超时异常"""
    pass


@dataclass
class ExecutionRecord:
    """执行记录"""
    task_id: int
    started_at: float
    ended_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    duration: float = 0.0
    error: Optional[str] = None


class MockTaskExecutor:
    """
    Mock 任务执行器
    
    完全替代真实的 ADB 任务执行，只模拟执行结果和时间
    """
    
    SCENARIOS = {
        "success": {"duration_range": (0.1, 0.5), "success_rate": 1.0},
        "slow": {"duration_range": (1.0, 2.0), "success_rate": 1.0},
        "timeout": {"duration_range": (10.0, 10.0), "success_rate": 0.0, "timeout": True},
        "error": {"duration_range": (0.1, 0.3), "success_rate": 0.0},
        "flaky": {"duration_range": (0.1, 0.5), "success_rate": 0.5},
    }
    
    def __init__(self, scenario: str = "success"):
        self.scenario = scenario
        self.execution_history: List[ExecutionRecord] = []
        self.current_execution: Optional[ExecutionRecord] = None
        self._lock = threading.Lock()
        
    def execute(self, task_id: int, task_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        模拟执行任务
        
        Args:
            task_id: 任务 ID
            task_config: 任务配置（被忽略，仅用于保持接口一致）
            
        Returns:
            {"status": "success", "duration": float}
            
        Raises:
            TaskTimeoutError: 模拟超时场景
            TaskExecutorError: 模拟执行失败场景
        """
        import random
        
        config = self.SCENARIOS.get(self.scenario, self.SCENARIOS["success"])
        
        record = ExecutionRecord(
            task_id=task_id,
            started_at=time.time()
        )
        
        with self._lock:
            self.current_execution = record
            
        try:
            # 模拟执行耗时
            duration = random.uniform(*config["duration_range"])
            
            # 检查是否超时
            if config.get("timeout", False):
                time.sleep(min(duration, 0.1))  # 测试时加速
                record.status = TaskStatus.TIMEOUT
                raise TaskTimeoutError(f"Task {task_id} execution timeout")
            
            time.sleep(min(duration, 0.1))  # 测试时加速
            
            # 检查成功率
            success = random.random() < config["success_rate"]
            
            record.ended_at = time.time()
            record.duration = record.ended_at - record.started_at
            
            if success:
                record.status = TaskStatus.SUCCESS
                result = {"status": "success", "duration": record.duration}
            else:
                record.status = TaskStatus.FAILED
                record.error = "Simulated execution failure"
                raise TaskExecutorError(f"Task {task_id} execution failed")
                
        finally:
            with self._lock:
                self.execution_history.append(record)
                self.current_execution = None
                
        return result
    
    def get_history(self) -> List[ExecutionRecord]:
        """获取执行历史"""
        with self._lock:
            return self.execution_history.copy()
    
    def get_current_execution(self) -> Optional[ExecutionRecord]:
        """获取当前正在执行的记录"""
        return self.current_execution
    
    def clear_history(self):
        """清空执行历史"""
        with self._lock:
            self.execution_history.clear()
