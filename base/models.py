import traceback

import functools

import threading

from django.db import models
from django.utils import timezone

from caidao_tools.django.abstract import (
    抽象定时任务,
)
from commons.external_api import push_task_data, push_sys_info
from commons.utils import filter_records_by_time

from helper_jfp import JobFilePersistence

from adb_tools.tool_xpath import 基本任务列表, SteadyDevice

import json

import datetime

import tool_date
import tool_time

from base.management.commands.tasks import TASKS
from helper_thread_pool import THREAD_POOL

from tool_enc import StrSecret

import time

import pandas
# Create your models here.
from tool_sys_info import get_termux_sys_info


class 定时任务(抽象定时任务):
    设备相关 = models.BooleanField(default=True)
    网络任务 = models.CharField(null=True, blank=True, max_length=255)
    数据 = models.JSONField(default=dict, blank=True, null=True)
    队列名称 = models.CharField(max_length=50, null=True, blank=True)
    知识库 = models.BinaryField(null=True)
    上一次推送时间 = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["激活", "优先级", "update_time"]),
        ]

    缓存 = {}

    # IP_PORT = None
    IP_PORT = None

    TOKEN = (
        StrSecret(b"QPvcOCN78U0vb9f7z-vOz-n3V5eiKzbhyUYSLogyS9o=")
        .decrypt_from_base64(
            "Z0FBQUFBQm9VU2JNTy02U1hUOXBRUnItZlhJU1JHUVZPVEpWcUxaS0hSWjJRYlpwVzVqamt3NnkwY3dfMUVjd3lNQ1gxR0hkSlNDOUJnbF9XYTZfSkI4UU1sQmNRa0VoS0lkb0poRm90LVlXUFBYSjJtRnM3Z3JzQ0thVXdvdVlxTFNVZW8xYzNLWEo="
        )
        .decode()
    )

    @classmethod
    def 当前设备(cls):
        return SteadyDevice.from_ip_port(
                    定时任务.IP_PORT,
                )

    @classmethod
    @functools.lru_cache(maxsize=None)
    def 当前设备串口号(cls):
        device = cls.当前设备()
        if device is not None:
            return device.adb.serialno


    def save(self, *args, **kwargs):
        # 先调用父类的save方法，确保update_time有值
        super().save(*args, **kwargs)

        # try:
        #     # 解析数据字段
        #     data_dict = self.数据 or {}
        #     data_records = data_dict.get("数据记录", [])

        #     # 调用独立的筛选函数
        #     newer_records = filter_records_by_time(
        #         data_records=data_records,
        #         update_time=self.上一次推送时间,
        #     )

        #     self.上一次推送时间 = timezone.now()
        #     super().save(update_fields=['上一次推送时间'], *args, **kwargs)

        #     if newer_records:
        #         post_data = {
        #             'name': self.名称,
        #             'data_list': newer_records,
        #             # 'device_id': '1234',
        #             'device_id': self.当前设备串口号(),
        #         }
        #         # print(post_data)

        #         future = THREAD_POOL.submit(push_task_data, post_data)

        #         def task_callback(fut):
        #             try:
        #                 fut.result()  # 触发异常
        #             except Exception as e:
        #                 print(f"推送任务执行失败: {e}", exc_info=True)

        #         future.add_done_callback(task_callback)

        #     # push_task_data(post_data)
        #     # 打印结果
        #     print("===== 使用Pandas筛选出的晚于update_time的记录 =====")
        #     print(len(newer_records))
        #     # print(newer_records)

        # except Exception as e:
        #     traceback.print_exc()
        #     print(f"处理数据出错: {e}")


    @classmethod
    def 从网络加载数据(cls, url):
        name = url.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
        data = JobFilePersistence.from_job_name(name, cls.TOKEN).read()
        return data

    @classmethod
    def 导入网络定时任务(cls, url, 强制更新=False):
        for data in cls.从网络加载数据(url):
            data = data.get("meta_flow")
            data['设定时间'] = tool_date.北京时间字符串转UTC(data.get("设定时间"))
            data["begin_time"] = tool_date.北京时间字符串转UTC(data.get("begin_time"))
            data["end_time"] = tool_date.北京时间字符串转UTC(data.get("end_time"))
            if not 强制更新:
                cls.objects.get_or_create(名称=data.get("名称"), defaults=data)
            else:
                cls.objects.update_or_create(名称=data.get("名称"), defaults=data)


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

    # @property
    # def 当前设备(self):
    #     if self.设备相关:
    #         return SteadyDevice.from_ip_port(
    #                     定时任务.IP_PORT,
    #                     refresh_init=False,
    #                     need_screen=False,
    #                     need_xml=True,
    #                 )

    # @property
    # def 当前设备串口号(self):
    #     device = self.当前设备
    #     if device is not None:
    #         return self.当前设备.serialno

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

    @classmethod
    def 心跳上传(cls, **kwargs):
        data = {
            # 'device_id': '1234',
            'device_id': cls.当前设备串口号(),
            'sys_info':  get_termux_sys_info()
        }
        try:
            push_sys_info(data)
        except:
            traceback.print_exc()


    def 用户配置(self, user=None):
        # print('数据', self.数据)
        data = self.数据.get('user_config', dict())
        if user:
            data = data.get(user, dict())
        else:
            data = data.get('global', dict())
        data['roles'] = self.数据.get('roles', list())
        # data['has_knowledge_base_content'] = True if data.pop('knowledge_base_content', '') else False
        return data

    def 保存用户配置(self, key, value, friend=None):
        self.数据.setdefault('user_config', dict())
        if friend:
            self.数据['user_config'].setdefault(friend, dict())
            self.数据['user_config'][friend][key] = value
        else:
            self.数据['user_config'].setdefault('global', dict())
            self.数据['user_config']['global'][key] = value
        self.save(update_fields=["数据"])