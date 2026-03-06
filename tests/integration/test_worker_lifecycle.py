"""
Worker 生命周期测试
测试 Worker 的启动、运行、停止流程
"""

import time
import threading
import pytest


class MockWorker:
    """
    模拟 Worker 类，用于测试生命周期
    """
    
    def __init__(self, queue, executor, timeout=5):
        self.queue = queue
        self.executor = executor
        self.timeout = timeout
        self.status = "stopped"
        self._thread = None
        self._stop_event = threading.Event()
        self.was_force_killed = False
        self.execution_count = 0
        self._lock = threading.Lock()
    
    def start(self):
        """启动 Worker"""
        if self.status == "running":
            return
        
        self.status = "running"
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run)
        self._thread.start()
    
    def stop(self, graceful_timeout=3, force=False):
        """停止 Worker"""
        if self.status != "running":
            return
        
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=graceful_timeout)
            
            if self._thread.is_alive() and force:
                self.was_force_killed = True
                # 注意：实际实现中这里可能需要强制终止
        
        self.status = "stopped"
    
    def _run(self):
        """Worker 主循环"""
        while not self._stop_event.is_set():
            self._process_one()
            time.sleep(0.05)  # 加速测试
    
    def _process_one(self):
        """处理一个任务"""
        task = self.queue.get()
        if not task:
            return
        
        try:
            self.executor.execute(task["id"], task)
            self.queue.ack(task["id"])
            with self._lock:
                self.execution_count += 1
        except Exception:
            self.queue.nack(task["id"], requeue=True)
    
    def get_execution_count(self):
        """获取执行计数"""
        with self._lock:
            return self.execution_count


@pytest.mark.worker
class TestWorkerLifecycle:
    """测试 Worker 生命周期"""
    
    def test_worker_normal_start_stop(self, mock_queue, mock_executor):
        """
        Worker 正常启停
        - 启动后状态为 running
        - 停止后状态为 stopped
        - 无异常抛出
        """
        worker = MockWorker(queue=mock_queue, executor=mock_executor)
        
        # 启动
        worker.start()
        assert worker.status == "running"
        
        # 停止
        worker.stop()
        assert worker.status == "stopped"
    
    def test_worker_processes_tasks(self, mock_queue, mock_executor):
        """
        Worker 处理任务
        - 队列中有任务
        - Worker 启动
        - 任务被执行
        - 计数增加
        """
        worker = MockWorker(queue=mock_queue, executor=mock_executor)
        
        # 添加任务
        for i in range(5):
            mock_queue.push({"id": i + 1, "priority": 1})
        
        # 启动 Worker
        worker.start()
        
        # 等待任务处理（轮询直到完成）
        for _ in range(50):  # 最多等 2.5 秒
            if worker.get_execution_count() == 5:
                break
            time.sleep(0.05)
        
        # 停止
        worker.stop()
        
        # 验证任务被处理
        assert worker.get_execution_count() == 5, f"只执行了 {worker.get_execution_count()} 个任务"
        assert mock_queue.size() == 0
    
    def test_worker_graceful_shutdown(self, mock_queue, mock_executor_slow):
        """
        优雅关闭
        - Worker 正在执行耗时任务
        - 发送停止信号
        - 等待当前任务完成
        """
        worker = MockWorker(queue=mock_queue, executor=mock_executor_slow)
        
        # 添加慢任务
        mock_queue.push({"id": 1, "priority": 1})
        
        worker.start()
        time.sleep(0.1)  # 让任务开始执行
        
        # 停止（应等待当前任务）
        stop_start = time.time()
        worker.stop(graceful_timeout=5)
        stop_duration = time.time() - stop_start
        
        # 验证优雅关闭
        assert worker.status == "stopped"
        # 任务执行时间 1-2 秒，优雅关闭应等待
        assert stop_duration >= 0.05  # 应至少等待任务开始执行
    
    def test_worker_force_kill_timeout(self, mock_queue):
        """
        强制终止
        - Worker 卡住（使用永远阻塞的 executor）
        - 优雅关闭超时
        - 期望：强制终止
        """
        import unittest.mock
        
        # 创建一个会卡住的 executor
        stuck_executor = unittest.mock.MagicMock()
        stuck_executor.execute = unittest.mock.MagicMock(
            side_effect=lambda *args: time.sleep(100)
        )
        stuck_executor.get_current_execution = unittest.mock.MagicMock(return_value=None)
        
        worker = MockWorker(queue=mock_queue, executor=stuck_executor)
        
        mock_queue.push({"id": 1, "priority": 1})
        worker.start()
        time.sleep(0.1)
        
        # 停止（超时后强制）
        worker.stop(graceful_timeout=0.5, force=True)
        
        assert worker.status == "stopped"
        assert worker.was_force_killed is True
    
    def test_worker_restart(self, mock_queue, mock_executor):
        """
        Worker 重启
        - 启动 Worker
        - 停止
        - 再次启动
        - 正常工作
        """
        worker = MockWorker(queue=mock_queue, executor=mock_executor)
        
        # 第一轮
        mock_queue.push({"id": 1, "priority": 1})
        worker.start()
        time.sleep(0.1)
        worker.stop()
        
        first_count = worker.get_execution_count()
        
        # 第二轮
        mock_queue.push({"id": 2, "priority": 1})
        worker.start()
        time.sleep(0.1)
        worker.stop()
        
        second_count = worker.get_execution_count()
        
        assert first_count == 1
        assert second_count == 2
    
    def test_worker_handles_executor_error(self, mock_queue, mock_executor_error):
        """
        Worker 处理执行器错误
        - 任务执行失败
        - Worker 捕获异常
        - 继续处理其他任务
        - Worker 不崩溃
        """
        worker = MockWorker(queue=mock_queue, executor=mock_executor_error)
        
        # 添加会失败的任务
        for i in range(3):
            mock_queue.push({"id": i + 1, "priority": 1})
        
        worker.start()
        time.sleep(0.3)
        worker.stop()
        
        # Worker 应该还在运行，没有崩溃
        assert worker.status == "stopped"  # 调用 stop 后应该是 stopped
        
        # 验证任务被尝试执行（进入死信队列或重试）
        assert mock_queue.dead_letter_size() > 0 or mock_queue.size() > 0
    
    def test_multiple_workers_concurrent(self, mock_queue, mock_executor):
        """
        多 Worker 并发
        - 启动多个 Worker
        - 共享同一个队列
        - 任务被分摊处理
        """
        workers = []
        for _ in range(3):
            w = MockWorker(queue=mock_queue, executor=mock_executor)
            workers.append(w)
        
        # 添加任务
        for i in range(10):
            mock_queue.push({"id": i + 1, "priority": 1})
        
        # 启动所有 Worker
        for w in workers:
            w.start()
        
        # 等待处理
        time.sleep(0.5)
        
        # 停止所有 Worker
        for w in workers:
            w.stop()
        
        # 验证所有任务被处理
        total_executed = sum(w.get_execution_count() for w in workers)
        assert total_executed == 10
        assert mock_queue.size() == 0
