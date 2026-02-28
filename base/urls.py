from django.urls import path

from .views import (
    页面数据视图,
    页面操作视图,
    用户配置视图,
    用户知识库视图,
    控制页面,
    更新sn,
    技能视图,
    # 新增接口
    get_skill_config,
    save_skill_config,
    skill_download_status,
    install_skill,
    uninstall_skill,
    download_skills,
    # 新增页面
    skill_square_page,
    demand_square_page,
    profile_page,
)



urlpatterns = [
    # 已有接口
    path("page_data", 页面数据视图.as_view()),
    path("operation", 页面操作视图.as_view()),
    path("user_config", 用户配置视图.as_view()),
    path("user_knowledge", 用户知识库视图.as_view()),
    path("update_sn", 更新sn.as_view()),
    path("skills", 技能视图.as_view()),
    
    # 新增：技能配置接口
    path("skill_config", get_skill_config, name='get_skill_config'),  # GET
    path("skill_config/save", save_skill_config, name='save_skill_config'),  # POST
    
    # 新增：技能下载相关接口
    path("skill/download_status", skill_download_status, name='skill_download_status'),
    path("skill/install", install_skill, name='install_skill'),
    path("skill/uninstall", uninstall_skill, name='uninstall_skill'),
    path("skill/download_skills", download_skills, name='download_skills'),
    
    # 页面路由
    path("control", 控制页面, name='control'),
    path("skill_square", skill_square_page, name='skill_square'),
    path("demand_square", demand_square_page, name='demand_square'),
    path("profile", profile_page, name='profile'),
]
