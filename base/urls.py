from django.urls import path

from .views import (
    页面数据视图,
    页面操作视图,
    用户配置视图,
    用户知识库视图,
)



urlpatterns = [
    path("page_data", 页面数据视图.as_view()),
    path("operation", 页面操作视图.as_view()),
    path("user_config", 用户配置视图.as_view()),
    path("user_knowledge", 用户知识库视图.as_view()),


]
