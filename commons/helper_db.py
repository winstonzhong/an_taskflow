import sqlite3
from tenacity import (
    retry,
    stop_after_attempt,  # 重试次数上限
    wait_exponential,  # 指数退避（避免高频重试加剧锁竞争）
    retry_if_exception_type,  # 只对指定异常重试
    before_sleep_log,  # 重试前打印日志（便于排查）
)
import logging
from asgiref.sync import sync_to_async
from django.db import OperationalError

# 配置日志（可选，便于查看重试过程）
logger = logging.getLogger(__name__)


# --------------------------
# 第一步：定义SQLite并发重试装饰器（同步函数用）


# 第二步：应用到你的同步数据库函数
# --------------------------
# 你的原始同步函数（带多个查询/写入）
# @retry_sqlite_concurrency(max_attempts=5, initial_wait=0.1)  # 加上重试装饰器
# def sync_db_operation(your_params):
#     """包含多个SQLite查询/写入的同步函数"""
#     # 示例操作（替换为你的实际逻辑）
#     from your_app.models import YourModel
#
#     # 查询操作
#     obj = YourModel.objects.get(id=your_params["id"])
#     # 写入操作
#     obj.field = your_params["new_value"]
#     obj.save()
#     # 批量写入
#     YourModel.objects.bulk_create([...])
#     return obj

# --------------------------
# 第三步：转换为异步函数（结合sync_to_async）
# --------------------------
# 转换为异步函数（保留重试逻辑）
# async_db_operation = sync_to_async(sync_db_operation)

# --------------------------
def retry_db_concurrency(max_attempts=3, initial_wait=0.1):
    """
    装饰器：处理SQLite并发导致的锁/死锁异常，带指数退避重试
    :param max_attempts: 最大重试次数
    :param initial_wait: 初始重试等待时间（秒），指数递增
    """

    def decorator(func):
        # 只对SQLite的锁异常重试
        @retry(
            # 重试停止条件：最多max_attempts次
            stop=stop_after_attempt(max_attempts),
            # 重试等待策略：指数退避（0.1s → 0.2s → 0.4s → ... 最大10s）
            wait=wait_exponential(multiplier=1, min=initial_wait, max=10),
            # 只重试SQLite的锁异常（Django封装的OperationalError + 原生sqlite3.OperationalError）
            retry=retry_if_exception_type((OperationalError, sqlite3.OperationalError)),
            # 重试前打印日志（级别WARNING）
            before_sleep=before_sleep_log(logger, logging.WARNING),
            # 重命名装饰后的函数（便于调试）
            reraise=True,  # 最终重试失败时，重新抛出原异常
        )
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (OperationalError, sqlite3.OperationalError) as e:
                # 过滤只重试“锁相关”的异常（避免对其他OperationalError重试）
                error_msg = str(e).lower()
                if "locked" in error_msg or "deadlock" in error_msg:
                    logger.warning(f"SQLite并发锁冲突：{e}，即将重试...")
                    raise  # 抛出异常，触发重试
                else:
                    raise  # 非锁异常，不重试，直接抛出

        return wrapper

    return decorator
