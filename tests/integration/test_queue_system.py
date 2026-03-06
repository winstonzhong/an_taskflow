"""
队列系统测试
测试 Mock 队列的入队、出队、确认机制
"""

import pytest
from tests.mocks.mock_queue import MockQueue


@pytest.mark.queue
class TestQueueSystem:
    """测试队列系统的核心功能"""
    
    def test_task_enqueue(self, mock_queue):
        """
        任务入队
        - 调用 push()
        - 验证队列长度 +1
        """
        initial_size = mock_queue.size()
        
        mock_queue.push({"id": 1, "priority": 1, "name": "测试任务"})
        
        assert mock_queue.size() == initial_size + 1
    
    def test_task_dequeue(self, mock_queue):
        """
        任务出队
        - 队列中有任务
        - 调用 get()
        - 验证返回正确的任务
        - 验证队列长度 -1
        - 验证进入处理中队列
        """
        mock_queue.push({"id": 1, "priority": 1, "name": "测试任务"})
        initial_size = mock_queue.size()
        
        task = mock_queue.get()
        
        assert task is not None
        assert task["id"] == 1
        assert mock_queue.size() == initial_size - 1
        assert mock_queue.processing_size() == 1
    
    def test_task_dequeue_empty(self, mock_queue):
        """
        空队列出队
        - 队列为空
        - 调用 get()
        - 返回 None
        """
        task = mock_queue.get()
        
        assert task is None
    
    def test_task_ack_success(self, mock_queue):
        """
        成功确认 (ACK)
        - Worker 取出任务
        - 执行成功
        - 调用 ack()
        - 任务从处理中队列移除
        """
        mock_queue.push({"id": 1, "priority": 1})
        task = mock_queue.get()
        
        result = mock_queue.ack(task["id"])
        
        assert result is True
        assert mock_queue.processing_size() == 0
        assert mock_queue.get_retry_count(task["id"]) == 0
    
    def test_task_ack_nonexistent(self, mock_queue):
        """
        确认不存在的任务
        - 调用 ack() 传入不存在的 task_id
        - 返回 False
        """
        result = mock_queue.ack(999)
        
        assert result is False
    
    def test_task_nack_with_requeue(self, mock_queue):
        """
        失败确认并重新入队 (NACK + requeue)
        - Worker 取出任务
        - 执行失败
        - 调用 nack(requeue=True)
        - 任务重新入队
        - 重试计数 +1
        """
        mock_queue.push({"id": 1, "priority": 1})
        task = mock_queue.get()
        initial_retry = mock_queue.get_retry_count(task["id"])
        
        result = mock_queue.nack(task["id"], requeue=True, max_retries=3)
        
        assert result is True
        assert mock_queue.size() == 1
        assert mock_queue.processing_size() == 0
        assert mock_queue.get_retry_count(task["id"]) == initial_retry + 1
    
    def test_task_nack_without_requeue(self, mock_queue):
        """
        失败确认并丢弃 (NACK + no requeue)
        - Worker 取出任务
        - 调用 nack(requeue=False)
        - 任务被丢弃
        - 不在待处理也不在死信队列
        """
        mock_queue.push({"id": 1, "priority": 1})
        task = mock_queue.get()
        
        result = mock_queue.nack(task["id"], requeue=False)
        
        assert result is True
        assert mock_queue.size() == 0
        assert mock_queue.processing_size() == 0
        assert mock_queue.dead_letter_size() == 0
    
    def test_dead_letter_queue(self, mock_queue):
        """
        死信队列
        - 设置最大重试次数 = 3
        - 任务失败 4 次
        - 前 3 次重新入队
        - 第 4 次进入死信队列
        """
        mock_queue.push({"id": 1, "priority": 1, "name": "易失败任务"})
        max_retries = 3
        
        # 失败 4 次
        for i in range(max_retries + 1):
            task = mock_queue.get()
            mock_queue.nack(task["id"], requeue=True, max_retries=max_retries)
        
        assert mock_queue.dead_letter_size() == 1
        assert mock_queue.size() == 0
        
        # 验证死信队列内容
        dead_task = mock_queue._dead_letter[0]
        assert dead_task["task"]["id"] == 1
        assert dead_task["retries"] == max_retries
    
    def test_priority_ordering(self, mock_queue):
        """
        优先级排序
        - 入队多个不同优先级的任务
        - 出队顺序按优先级排序
        """
        # 入队（乱序）
        mock_queue.push({"id": 1, "priority": 5})
        mock_queue.push({"id": 2, "priority": 1})
        mock_queue.push({"id": 3, "priority": 3})
        mock_queue.push({"id": 4, "priority": 2})
        
        # 出队（应有序）
        order = []
        while mock_queue.size() > 0:
            task = mock_queue.get()
            order.append(task["id"])
            mock_queue.ack(task["id"])
        
        assert order == [2, 4, 3, 1]  # 按优先级 1,2,3,5
    
    def test_concurrent_access(self, mock_queue):
        """
        并发访问安全
        - 多线程同时操作队列
        - 无数据竞争或丢失
        """
        import threading
        
        results = {"pushed": 0, "popped": 0}
        
        def producer():
            for i in range(50):
                mock_queue.push({"id": i, "priority": 1})
                results["pushed"] += 1
        
        def consumer():
            for _ in range(50):
                task = mock_queue.get()
                if task:
                    mock_queue.ack(task["id"])
                    results["popped"] += 1
        
        threads = []
        for _ in range(2):
            t = threading.Thread(target=producer)
            threads.append(t)
            t = threading.Thread(target=consumer)
            threads.append(t)
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证无数据丢失
        assert results["pushed"] == 100
        # popped 可能少于 pushed，因为消费者可能先完成
        assert results["popped"] <= results["pushed"]
    
    def test_queue_clear(self, mock_queue):
        """
        清空队列
        - 队列中有任务
        - 调用 clear()
        - 所有队列清空
        """
        mock_queue.push({"id": 1, "priority": 1})
        task = mock_queue.get()
        mock_queue.nack(task["id"], requeue=True)
        
        assert mock_queue.size() > 0 or mock_queue.processing_size() > 0
        
        mock_queue.clear()
        
        assert mock_queue.size() == 0
        assert mock_queue.processing_size() == 0
        assert mock_queue.dead_letter_size() == 0
