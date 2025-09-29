from django.db import models

from caidao_tools.django.abstract import (
    抽象定时任务,
)

from helper_jfp import JobFilePersistence

from adb_tools.tool_xpath import 基本任务列表

import json

import datetime

import tool_date
import tool_time

from base.management.commands.tasks import TASKS

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
        # b = self.远程流程
        # print(b, b.jobs)
        return self.远程流程.执行任务()
    
    @classmethod
    def 导入定时任务(cls, fpath='/home/yka-003/workspace/my_robot/main_robot.json'):
        print(cls.objects.filter().delete())
        with open(fpath, 'r', encoding='utf-8') as fp:
            data_list = json.load(fp)
        for item in data_list:
            item.pop('id')
            # item.pop('update_time')

            if item.get('update_time'):
                dt = datetime.datetime.strptime(item['update_time'], '%Y-%m-%d %H:%M:%S')
                # timezone.make_aware(dt, timezone=shanghai_tz)
                item['update_time'] = tool_time.TIME_ZONE_SHANGHAI.localize(dt)
            if item.get('设定时间'):
                dt = datetime.datetime.strptime(item['设定时间'], '%Y-%m-%d %H:%M:%S')
                item['设定时间'] = tool_time.TIME_ZONE_SHANGHAI.localize(dt)

            cls.objects.create(**item)

    @classmethod
    def 从配置表导入定时任务(cls, 强制覆盖=False):
        for x in TASKS:
            x['设定时间'] = tool_date.北京时间字符串转UTC(x.get('设定时间'))
            # print(x)
            name = x.get("名称")
            qs = cls.objects.filter(名称=name)
            if qs.exists():
                if 强制覆盖:
                    qs.update(**x)
            else:
                cls.objects.create(**x)