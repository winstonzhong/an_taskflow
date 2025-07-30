from django.contrib import admin

# Register your models here.
import pandas

from django.utils.safestring import mark_safe
from base.models import (
    定时任务,
)
from caidao_tools.django.base_admin import 抽象定时任务Admin
from urllib.parse import urlencode

from django.db.models import F
# Register your models here.


# @admin.register(手机设备)
# class 手机设备Admin(BaseAdmin):
#     pass


# @admin.register(会话名称)
# class 会话名称Admin(BaseAdmin):
#     def get_actions(self, request):
#         return admin.ModelAdmin.get_actions(self, request)


@admin.register(定时任务)
class 定时任务Admin(抽象定时任务Admin):
    readonly_fields = (
        "update_time",
        "间隔秒",
    )
    list_display = [
        "id",
        "group_name",
        "优先级",
        "名称",
        "执行函数",
        "任务描述视图",
        "update_time",
        "begin_time",
        "end_time",
        # "手机设备",
        "激活",
        "输出调试信息",
        "设备相关",
    ]

    list_filter = ["group_name","激活"]
    
    list_editable = ('优先级',)

    actions = ("clone_task", "反转输出调试信息", "切换激活状态")

    
    
    def clone_task(self, request, queryset):
        for task in queryset:
            task.clone()
    clone_task.short_description = "克隆定时任务"

    def 反转输出调试信息(self, request, queryset):
        queryset.update(输出调试信息=(F('输出调试信息')+1) % 2)

    def 切换激活状态(self, request, queryset):
        queryset.update(激活=(F('激活') + 1) % 2)

    def 任务描述视图(self, obj):
        desc = obj.任务描述 or ""
        desc = desc.replace("\n", "<br/>")

        # url = obj.获取完整任务数据下载链接()
        url = f"{obj.任务服务url}?{urlencode(obj.任务下载参数)}"
        return mark_safe(
            f"""<div>描述：{desc}</div>
                            <div>任务下载参数: {obj.任务下载参数}</div>
                            <div><a href="{url}" target="_blank">{obj.任务服务url or '-'}</a></div>
                         """
        )
