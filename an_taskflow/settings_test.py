"""
测试环境配置
用于 pytest 运行集成测试
"""

from .settings import *

# 使用内存数据库，加速测试
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# 测试日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}

# 禁用 CSRF 验证（测试时不需要）
MIDDLEWARE = [
    m for m in MIDDLEWARE 
    if 'csrf' not in m.lower()
]

# 测试专用的 Mock 配置
TEST_CONFIG = {
    'MOCK_ADB': True,           # 使用 Mock ADB 设备
    'MOCK_QUEUE': True,         # 使用内存队列
    'MOCK_EXECUTOR': True,      # 使用 Mock 任务执行器
    'TASK_TIMEOUT': 5,          # 任务超时时间（秒）
    'WORKER_HEARTBEAT': 1,      # Worker 心跳间隔（秒）
    'GRACEFUL_TIMEOUT': 3,      # 优雅关闭超时（秒）
}

# 确保静态文件配置存在（避免测试警告）
if not hasattr(__import__('django.conf', fromlist=['settings']), 'STATIC_URL'):
    STATIC_URL = '/static/'
