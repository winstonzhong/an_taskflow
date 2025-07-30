from django.db import models

from caidao_tools.django.abstract import (
    抽象定时任务,
)

from helper_jfp import JobFilePersistence

# import helper_hash
# import tool_env
# from adb_tools.helper_adb import BaseAdb
# import tool_wx

# import config_reader
# from tool_foods import transform_food_data
from adb_tools.tool_xpath import 基本任务列表


# Create your models here.
class 定时任务(抽象定时任务):
    设备相关 = models.BooleanField(default=True)
    网络任务 = models.CharField(null=True, blank=True, max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["激活", "优先级", "update_time"]),
        ]

    缓存 = {}

    IP_PORT = None

    @property
    def 远程执行流程数据(self):
        if self.网络任务:
            if self.id not in self.缓存:
                self.缓存[self.id] = JobFilePersistence.from_job_name(
                    self.网络任务,
                    'xn_c3nOp0ZTq'
                ).read()
            return self.缓存.get(self.id)

    @property
    def device_pointed(self):
        if self.IP_PORT:
            return {
                "is_windows": False,
                "ip_port": self.IP_PORT,
                "title": None,
                "clsname": None,
            }

    @property
    def 远程流程(self):
        return 基本任务列表(self.远程执行流程数据, self.device_pointed)

    def 加载配置执行(self):
        b = self.远程流程
        print(b, b.jobs)
        return self.远程流程.执行任务()