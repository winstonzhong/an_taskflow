"""
pytest 全局配置和 Fixtures
"""

import os
import sys
import django

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'an_taskflow.settings_test')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'caidao'))

django.setup()

import pytest
from tests.mocks.mock_task_executor import MockTaskExecutor
from tests.mocks.mock_queue import MockQueue
from tests.mocks.mock_device import MockDevice


@pytest.fixture
def mock_executor():
    """Mock 任务执行器固件"""
    return MockTaskExecutor()


@pytest.fixture
def mock_queue():
    """Mock 队列固件"""
    return MockQueue()


@pytest.fixture
def mock_device():
    """Mock 设备固件"""
    return MockDevice()


@pytest.fixture
def mock_executor_slow():
    """慢速 Mock 执行器（用于超时测试）"""
    return MockTaskExecutor(scenario="slow")


@pytest.fixture
def mock_executor_error():
    """总是失败的 Mock 执行器（用于重试测试）"""
    return MockTaskExecutor(scenario="error")


@pytest.fixture
def mock_executor_timeout():
    """超时的 Mock 执行器（用于超时测试）"""
    return MockTaskExecutor(scenario="timeout")
