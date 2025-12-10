from django.db import models
from django.utils import timezone

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

from tool_enc import StrSecret

import time

import pandas
# Create your models here.
class 定时任务(抽象定时任务):
    设备相关 = models.BooleanField(default=True)
    网络任务 = models.CharField(null=True, blank=True, max_length=255)
    数据 = models.JSONField(default=dict, blank=True, null=True)
    队列名称 = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["激活", "优先级", "update_time"]),
        ]

    缓存 = {}

    IP_PORT = None

    TOKEN = (
        StrSecret(b"QPvcOCN78U0vb9f7z-vOz-n3V5eiKzbhyUYSLogyS9o=")
        .decrypt_from_base64(
            "Z0FBQUFBQm9VU2JNTy02U1hUOXBRUnItZlhJU1JHUVZPVEpWcUxaS0hSWjJRYlpwVzVqamt3NnkwY3dfMUVjd3lNQ1gxR0hkSlNDOUJnbF9XYTZfSkI4UU1sQmNRa0VoS0lkb0poRm90LVlXUFBYSjJtRnM3Z3JzQ0thVXdvdVlxTFNVZW8xYzNLWEo="
        )
        .decode()
    )

    # def 写入数据记录字典(self, d: dict):
    #     records = self.数据.setdefault("数据记录", [])
    #     d.update({"时间": int(time.time())})
    #     records.append(d)
    #     self.save()

    # @property
    # def df_数据记录(self):
    #     df = pandas.DataFrame(self.数据.get("数据记录", []))
    #     return df if df.empty else df.sort_values(by="时间")

    
    
    # def 变更间隔秒数(self, 每小时最多运行次数: int = 8, 两次运行最小间隔秒数=10 * 60, 间隔秒数=None):
    #     from douyin.tool_dy_score import 计算下一次运行等待秒数

    #     if 间隔秒数 is not None:
    #         self.间隔秒 = 间隔秒数
    #     else:
    #         self.间隔秒 = 计算下一次运行等待秒数(
    #             df=self.df_数据记录,
    #             两次运行最小间隔秒数=两次运行最小间隔秒数,
    #             每小时最多运行次数=每小时最多运行次数,
    #         )
    #     self.save()


    @classmethod
    def 从网络加载数据(cls, url):
        name = url.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
        data = JobFilePersistence.from_job_name(name, cls.TOKEN).read()
        return data

    @classmethod
    def 导入网络定时任务(cls, url):
        for data in cls.从网络加载数据(url):
            data = data.get("meta_flow")
            data['设定时间'] = tool_date.北京时间字符串转UTC(data.get("设定时间"))
            data["begin_time"] = tool_date.北京时间字符串转UTC(data.get("begin_time"))
            data["end_time"] = tool_date.北京时间字符串转UTC(data.get("end_time"))
            cls.objects.get_or_create(名称=data.get("名称"), defaults=data)


    @property
    def 远程执行流程数据(self):
        if self.网络任务:
            if self.id not in self.缓存:
                self.缓存[self.id] = JobFilePersistence.from_job_name(
                    self.网络任务, self.TOKEN
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
        return 基本任务列表(self.远程执行流程数据, self.device_pointed, 持久对象=self)

    def 加载配置执行(self):
        return self.远程流程.执行任务()

    # @classmethod
    # def 导入定时任务(cls, fpath="/home/yka-003/workspace/my_robot/main_robot.json"):
    #     print(cls.objects.filter().delete())
    #     with open(fpath, "r", encoding="utf-8") as fp:
    #         data_list = json.load(fp)
    #     for item in data_list:
    #         item.pop("id")
    #         # item.pop('update_time')

    #         if item.get("update_time"):
    #             dt = datetime.datetime.strptime(
    #                 item["update_time"], "%Y-%m-%d %H:%M:%S"
    #             )
    #             # timezone.make_aware(dt, timezone=shanghai_tz)
    #             item["update_time"] = tool_time.TIME_ZONE_SHANGHAI.localize(dt)
    #         if item.get("设定时间"):
    #             dt = datetime.datetime.strptime(item["设定时间"], "%Y-%m-%d %H:%M:%S")
    #             item["设定时间"] = tool_time.TIME_ZONE_SHANGHAI.localize(dt)

    #         cls.objects.create(**item)

    @classmethod
    def 从配置表导入定时任务(cls, 强制覆盖=False):
        if 强制覆盖:
            cls.objects.all().delete()

        for x in TASKS:
            x["设定时间"] = tool_date.北京时间字符串转UTC(x.get("设定时间"))
            # print(x)
            name = x.get("名称")
            qs = cls.objects.filter(名称=name)
            if qs.exists():
                if 强制覆盖:
                    qs.update(**x)
            else:
                cls.objects.create(**x)

    @classmethod
    def 动态初始化(cls, **kwargs):
        if tool_date.是否在时间段内("23:00:00", "08:00:00"):
            cls.objects.filter(名称__in=["微信_微信运动同步"]).exclude(
                间隔秒=60 * 10
            ).update(间隔秒=60 * 10)
        else:
            cls.objects.filter(名称__in=["微信_微信运动同步"]).exclude(
                间隔秒=60 * 30
            ).update(间隔秒=60 * 30)
