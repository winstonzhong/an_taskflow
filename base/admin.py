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

from django.urls.conf import path

from django.http.response import HttpResponseRedirect, HttpResponse

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
        "队列名称",
        "优先级",
        "间隔秒",
        "名称",
        # "执行函数",
        # "任务描述视图",
        "update_time",
        "begin_time",
        "end_time",
        # "手机设备",
        "激活",
        "输出调试信息",
        "设备相关",
        "数据记录看板",
    ]

    list_filter = ["group_name", "激活"]

    list_editable = ("优先级", "队列名称", "group_name")

    actions = ("clone_task", "反转输出调试信息", "切换激活状态", "组成一组")

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("data_records/", self.show_data_records),
        ]
        print(my_urls)
        return my_urls + urls

    def show_data_records(self, request):
        obj = 定时任务.objects.get(id=request.GET.get("id"))

        df = obj.df_数据记录

        df["时间"] = (
            pandas.to_datetime(
                df["时间"],  # 原始Unix时间戳（秒级）
                unit="s",  # 时间戳单位：秒（time.time()默认）
                utc=True,  # 先锚定到UTC（必须！否则基准错误）
            )
            .dt.tz_convert("Asia/Shanghai")  # 直接转换为北京时间时区
            .dt.strftime("%Y-%m-%d %H:%M:%S")
        )

        return HttpResponse(df.iloc[::-1].to_html())

    def 组成一组(self, request, queryset):
        名称 = queryset.order_by("id").first().group_name
        queryset.update(group_name=名称)

    组成一组.short_description = "将选中项组成一组"

    def clone_task(self, request, queryset):
        for task in queryset:
            task.clone()

    clone_task.short_description = "克隆定时任务"

    def 反转输出调试信息(self, request, queryset):
        queryset.update(输出调试信息=(F("输出调试信息") + 1) % 2)

    def 切换激活状态(self, request, queryset):
        queryset.update(激活=(F("激活") + 1) % 2)

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

    def 数据记录看板(self, obj):
        url = f"/admin/base/定时任务/data_records/?id={obj.id}"
        return (
            mark_safe("""<a href="%s" target="_blank">数据记录看板</a>""" % url)
            if obj.数据.get("数据记录")
            else None
        )
