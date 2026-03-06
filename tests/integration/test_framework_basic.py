"""
基础测试 - 验证测试框架是否正常工作
"""

import pytest
from tests.mocks.mock_task_executor import MockTaskExecutor, TaskStatus
from tests.mocks.mock_queue import MockQueue
from tests.mocks.mock_device import MockDevice


class TestMockComponents:
    """测试 Mock 组件基本功能"""
    
    def test_mock_executor_success(self):
        """测试 Mock 执行器 - 成功场景"""
        executor = MockTaskExecutor(scenario="success")
        result = executor.execute(task_id=1)
        
        assert result["status"] == "success"
        assert "duration" in result
        assert len(executor.get_history()) == 1
        
        record = executor.get_history()[0]
        assert record.task_id == 1
        assert record.status == TaskStatus.SUCCESS
    
    def test_mock_executor_error(self):
        """测试 Mock 执行器 - 失败场景"""
        executor = MockTaskExecutor(scenario="error")
        
        from tests.mocks.mock_task_executor import TaskExecutorError
        with pytest.raises(TaskExecutorError):
            executor.execute(task_id=2)
        
        assert len(executor.get_history()) == 1
        record = executor.get_history()[0]
        assert record.status == TaskStatus.FAILED
    
    def test_mock_queue_basic(self):
        """测试 Mock 队列 - 基本操作"""
        queue = MockQueue()
        
        # 入队
        queue.push({"id": 1, "priority": 5, "name": "低优先级"})
        queue.push({"id": 2, "priority": 1, "name": "高优先级"})
        
        assert queue.size() == 2
        
        # 出队（按优先级）
        task = queue.get()
        assert task["id"] == 2  # 高优先级先出
        assert queue.processing_size() == 1
        
        # 确认完成
        queue.ack(task["id"])
        assert queue.processing_size() == 0
    
    def test_mock_queue_nack_requeue(self):
        """测试 Mock 队列 - 失败重试"""
        queue = MockQueue()
        
        queue.push({"id": 1, "priority": 1})
        task = queue.get()
        
        # 失败并重新入队
        queue.nack(task["id"], requeue=True, max_retries=3)
        
        assert queue.size() == 1
        assert queue.get_retry_count(task["id"]) == 1
    
    def test_mock_queue_dead_letter(self):
        """测试 Mock 队列 - 死信队列"""
        queue = MockQueue()
        
        queue.push({"id": 1, "priority": 1})
        task = queue.get()
        
        # 重试 3 次后进入死信队列
        for _ in range(3):
            queue.nack(task["id"], requeue=True, max_retries=3)
            task = queue.get()
        
        # 第 4 次进入死信队列
        queue.nack(task["id"], requeue=True, max_retries=3)
        
        assert queue.dead_letter_size() == 1
        assert queue.size() == 0
    
    def test_mock_device(self):
        """测试 Mock 设备"""
        device = MockDevice(device_id="test_001")
        
        assert device.check_health() is True
        assert device.allocate() is True
        assert device.allocate() is False  # 已被分配
        
        device.release()
        assert device.allocate() is True
        
        device.disconnect()
        assert device.check_health() is False


class TestFixtures:
    """测试 Fixtures 是否正常工作"""
    
    def test_fixture_mock_executor(self, mock_executor):
        """验证 mock_executor fixture"""
        result = mock_executor.execute(task_id=100)
        assert result["status"] == "success"
    
    def test_fixture_mock_queue(self, mock_queue):
        """验证 mock_queue fixture"""
        mock_queue.push({"id": 1, "priority": 1})
        assert mock_queue.size() == 1
    
    def test_fixture_mock_device(self, mock_device):
        """验证 mock_device fixture"""
        assert mock_device.device_id == "mock_device_001"


class TestDjangoIntegration:
    """测试 Django 集成"""
    
    @pytest.mark.django_db
    def test_database_access(self):
        """验证可以访问 Django 数据库"""
        from base.models import 定时任务
        from django.utils import timezone
        
        # 创建一条记录（包含必需字段）
        task = 定时任务.objects.create(
            名称="测试任务",
            激活=True,
            优先级=1,
            设定时间=timezone.now()
        )
        
        assert task.id is not None
        assert task.名称 == "测试任务"
        
        # 查询验证
        fetched = 定时任务.objects.get(id=task.id)
        assert fetched.名称 == "测试任务"
