"""
技能配置保存测试
测试 save_skill_config 接口的批量更新功能
"""

import json
import unittest
import pytest
from django.test import Client
from django.utils import timezone
from base.models import 定时任务


@pytest.mark.django_db
class TestSkillConfigSave:
    """
    测试技能配置保存接口
    验证批量更新同 group_name 下所有任务的配置
    """
    
    def setup_method(self):
        """测试前准备"""
        self.client = Client()
        self.skill_name = "测试技能"
        
    def test_save_config_updates_all_tasks_in_group(self):
        """
        测试保存配置时更新所有同 group_name 的任务
        
        场景：
        - 创建3个相同 group_name 的任务
        - 调用 save_skill_config 保存配置
        - 验证所有任务的配置都被更新
        """
        # 准备：创建3个同 group_name 的任务
        task1 = 定时任务.objects.create(
            名称="任务1",
            group_name=self.skill_name,
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        task2 = 定时任务.objects.create(
            名称="任务2",
            group_name=self.skill_name,
            激活=True,
            配置={"旧配置": "value"},  # 已有配置
            设定时间=timezone.now()
        )
        task3 = 定时任务.objects.create(
            名称="任务3",
            group_name=self.skill_name,
            激活=True,
            配置=None,  # 空配置
            设定时间=timezone.now()
        )
        
        # 新配置数据
        new_config = {
            "keys": [
                {
                    "name": "测试配置项",
                    "type": "text",
                    "current_value": "测试值",
                    "history": []
                }
            ]
        }
        
        # 执行：调用保存接口
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": self.skill_name,
                "config": new_config
            }),
            content_type='application/json'
        )
        
        # 验证：响应成功
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['code'] == 2000
        assert data['message'] == "保存成功"
        
        # 验证：所有任务的配置都被更新
        task1.refresh_from_db()
        task2.refresh_from_db()
        task3.refresh_from_db()
        
        # 保存后配置会被转换为数据库存储格式（平铺字典）
        # 注意：空 history 不会被存储
        expected_stored_config = {
            "测试配置项": "测试值"
        }
        assert task1.配置 == expected_stored_config
        assert task2.配置 == expected_stored_config
        assert task3.配置 == expected_stored_config
        
        print(f"✅ 成功更新 {self.skill_name} 下所有任务的配置")
    
    def test_save_config_with_old_format(self):
        """
        测试使用旧格式保存配置
        
        场景：
        - 使用旧格式（不包含 keys 字段）
        - 验证配置正确保存到所有任务
        """
        # 准备：创建2个任务
        task1 = 定时任务.objects.create(
            名称="旧格式任务1",
            group_name="旧格式技能",
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        task2 = 定时任务.objects.create(
            名称="旧格式任务2",
            group_name="旧格式技能",
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        
        # 旧格式配置
        old_config = {
            "回复设置": {"模板": "你好"},
            "高级选项": {"延迟": 1}
        }
        
        # 执行
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": "旧格式技能",
                "config": old_config
            }),
            content_type='application/json'
        )
        
        # 验证
        assert response.status_code == 200
        
        task1.refresh_from_db()
        task2.refresh_from_db()
        
        assert task1.配置 == old_config
        assert task2.配置 == old_config
        
        print("✅ 旧格式配置保存成功")
    
    def test_save_config_only_affects_same_group(self):
        """
        测试保存配置只影响相同 group_name 的任务
        
        场景：
        - 创建不同 group_name 的任务
        - 验证只有目标 group 的任务被更新
        """
        # 准备：创建不同 group 的任务
        target_task = 定时任务.objects.create(
            名称="目标组任务",
            group_name="目标组",
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        other_task = 定时任务.objects.create(
            名称="其他组任务",
            group_name="其他组",
            激活=True,
            配置={"不应": "被修改"},
            设定时间=timezone.now()
        )
        
        config = {"测试": "配置"}
        
        # 执行：只更新目标组
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": "目标组",
                "config": config
            }),
            content_type='application/json'
        )
        
        # 验证
        assert response.status_code == 200
        
        target_task.refresh_from_db()
        other_task.refresh_from_db()
        
        assert target_task.配置 == config
        assert other_task.配置 == {"不应": "被修改"}  # 未被修改
        
        print("✅ 配置只影响目标 group_name 的任务")
    
    def test_save_config_missing_skill_name(self):
        """
        测试缺少 skill_name 参数的错误处理
        """
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "config": {"key": "value"}
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['code'] == 4000
        assert "skill_name" in data['message']
        
        print("✅ 缺少 skill_name 参数正确返回错误")
    
    def test_save_config_skill_not_exist(self):
        """
        测试技能不存在的情况
        """
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": "不存在的技能",
                "config": {"key": "value"}
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 404
        data = json.loads(response.content)
        assert data['code'] == 4004
        
        print("✅ 技能不存在正确返回404")
    
    def test_save_config_invalid_json(self):
        """
        测试无效的 JSON 请求体
        """
        response = self.client.post(
            '/base/skill_config/save',
            data="不是有效的JSON",
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['code'] == 4000
        
        print("✅ 无效JSON正确返回错误")

    def test_save_model_field_config(self):
        """
        【新增】测试保存模型字段配置（如 两次运行最小间隔秒）
        
        场景：
        - 保存包含 两次运行最小间隔秒 的配置
        - 验证 两次运行最小间隔秒 被保存到模型字段，而不是配置 JSON
        """
        # 准备：创建任务，设置初始两次运行最小间隔秒
        task = 定时任务.objects.create(
            名称="模型字段测试任务",
            group_name="模型字段测试技能",
            激活=True,
            两次运行最小间隔秒=300,  # 初始值 5 分钟
            配置={},
            设定时间=timezone.now()
        )
        
        # 新配置，包含两次运行最小间隔秒
        config_with_interval = {
            "keys": [
                {
                    "name": "普通配置项",
                    "type": "text",
                    "current_value": "普通值",
                    "history": []
                },
                {
                    "name": "两次运行最小间隔秒",
                    "type": "text",
                    "current_value": 600,  # 10 分钟
                    "history": [],
                    "_is_model_field": True
                }
            ]
        }
        
        # 执行：保存配置
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": "模型字段测试技能",
                "config": config_with_interval
            }),
            content_type='application/json'
        )
        
        # 验证：响应成功
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['code'] == 2000
        
        # 验证：两次运行最小间隔秒被更新到模型字段
        task.refresh_from_db()
        assert task.两次运行最小间隔秒 == 600  # 验证模型字段被更新
        
        # 验证：普通配置项保存到配置 JSON
        assert task.配置 == {"普通配置项": "普通值"}
        
        print("✅ 模型字段（两次运行最小间隔秒）保存成功")

    def test_save_config_query_last_record(self):
        """
        【新增】测试保存配置时查询最后一条记录
        
        场景：
        - 创建多条同 group_name 的任务
        - 验证保存时使用最后一条记录的配置作为 original_config
        """
        # 准备：创建多条任务，第一条有内置配置项
        task1 = 定时任务.objects.create(
            名称="第一条任务",
            group_name="最后记录测试",
            激活=True,
            配置={
                "视频评论提示词_pdd_rights": "pdd提示词",
                "普通配置": "值1"
            },
            设定时间=timezone.now()
        )
        task2 = 定时任务.objects.create(
            名称="第二条任务（最后）",
            group_name="最后记录测试",
            激活=True,
            配置={
                "视频评论提示词_3d_modeling": "3d提示词",
                "普通配置": "值2"
            },
            设定时间=timezone.now()
        )
        
        # 新配置
        new_config = {
            "keys": [
                {
                    "name": "新配置",
                    "type": "text",
                    "current_value": "新值",
                    "history": []
                }
            ]
        }
        
        # 执行
        response = self.client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": "最后记录测试",
                "config": new_config
            }),
            content_type='application/json'
        )
        
        # 验证
        assert response.status_code == 200
        
        task1.refresh_from_db()
        task2.refresh_from_db()
        
        # 所有任务的配置都被更新（保留内置配置项）
        assert task1.配置["新配置"] == "新值"
        assert task2.配置["新配置"] == "新值"
        
        print("✅ 最后记录查询测试通过")


@pytest.mark.django_db
class TestSkillConfigIntegration:
    """
    集成测试：完整的配置保存和读取流程
    """
    
    def test_save_and_get_config_consistency(self):
        """
        测试保存后读取配置的一致性
        
        场景：
        - 保存配置到多个任务
        - 通过 get_skill_config 读取
        - 验证读取的配置与保存的一致
        """
        client = Client()
        skill_name = "一致性测试技能"
        
        # 准备：创建多个任务
        定时任务.objects.create(
            名称="一致性任务1",
            group_name=skill_name,
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        定时任务.objects.create(
            名称="一致性任务2",
            group_name=skill_name,
            激活=True,
            配置={},
            设定时间=timezone.now()
        )
        
        # 保存配置
        config_to_save = {
            "keys": [
                {
                    "name": "API密钥",
                    "type": "text",
                    "current_value": "sk-123456",
                    "history": []
                },
                {
                    "name": "延迟设置",
                    "type": "object",  # 注意：使用 "object" 而不是 "kv"
                    "current_value": {"最小": 1, "最大": 5},
                    "history": []
                }
            ]
        }
        
        save_response = client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": skill_name,
                "config": config_to_save
            }),
            content_type='application/json'
        )
        
        assert save_response.status_code == 200
        
        # 读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        
        # 验证读取的配置与保存的一致
        assert data['code'] == 2000
        retrieved_config = data['data']['config']
        
        # 【修改】现在会额外返回模型字段配置（如 两次运行最小间隔秒）
        # 所以 keys 数量 = 保存的 keys + 模型字段
        assert len(retrieved_config['keys']) >= 2
        
        # 找到非模型字段的 keys
        normal_keys = [k for k in retrieved_config['keys'] if not k.get('_is_model_field')]
        assert len(normal_keys) == 2
        assert normal_keys[0]['name'] == "API密钥"
        assert normal_keys[0]['current_value'] == "sk-123456"
        assert normal_keys[1]['type'] == "object"
        
        # 验证模型字段也被返回
        model_keys = [k for k in retrieved_config['keys'] if k.get('_is_model_field')]
        assert len(model_keys) >= 1  # 至少包含 两次运行最小间隔秒
        interval_key = next((k for k in model_keys if k['name'] == '两次运行最小间隔秒'), None)
        assert interval_key is not None
        # 两次运行最小间隔秒的值直接从模型字段读取（使用默认值 600）
        assert interval_key['current_value'] == 600  # 默认值 10*60
        
        print("✅ 保存和读取配置一致性测试通过")

    def test_get_config_uses_last_record(self):
        """
        【新增】测试读取配置时使用最后一条记录
        
        场景：
        - 创建多条同 group_name 的任务
        - 验证读取时使用最后一条记录
        """
        client = Client()
        skill_name = "最后记录读取测试"
        
        # 准备：创建多条任务
        定时任务.objects.create(
            名称="第一条任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=300,
            配置={"配置": "第一条"},
            设定时间=timezone.now()
        )
        last_task = 定时任务.objects.create(
            名称="最后一条任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=600,
            配置={"配置": "最后一条"},
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证：使用最后一条记录
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        # 验证返回的模型字段是最后一条任务的值
        model_keys = [k for k in data['data']['config']['keys'] if k.get('_is_model_field')]
        interval_key = next((k for k in model_keys if k['name'] == '两次运行最小间隔秒'), None)
        assert interval_key is not None
        assert interval_key['current_value'] == 600  # 最后一条任务的值
        
        print("✅ 读取配置使用最后记录测试通过")


@pytest.mark.django_db
class TestSkillConfigHistoryFormat:
    """
    【新增】历史记录格式测试
    测试后端历史记录格式适配
    """
    
    def test_history_format_with_created_at(self):
        """
        测试历史记录格式使用 created_at 字段
        
        场景：
        - 后端历史记录使用 created_at 而不是 timestamp
        - 验证前端能正确显示时间
        """
        client = Client()
        skill_name = "历史记录格式测试"
        
        # 准备：创建任务，配置中包含历史记录（使用后端格式）
        定时任务.objects.create(
            名称="历史记录任务",
            group_name=skill_name,
            激活=True,
            配置={
                "目标视频描述": "当前值",
                "目标视频描述_历史": [
                    {
                        "id": "hist_001",
                        "name": "历史_001",
                        "created_at": "2024-01-15T10:30:00Z",
                        "目标视频描述": "历史值1"
                    },
                    {
                        "id": "hist_002", 
                        "name": "历史_002",
                        "created_at": "2024-01-16T14:20:00Z",
                        "目标视频描述": "历史值2"
                    }
                ]
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 找到目标视频描述 key
        target_key = next((k for k in keys if k['name'] == '目标视频描述'), None)
        assert target_key is not None
        
        # 验证历史记录被正确解析
        assert len(target_key['history']) == 2
        
        # 验证历史记录格式（前端适配后的格式）
        history_item = target_key['history'][0]
        assert 'created_at' in history_item or 'timestamp' in history_item
        
        print("✅ 历史记录格式适配测试通过")


@pytest.mark.django_db
class TestSkillConfigBuiltinFilter:
    """
    【新增】内置配置项过滤测试
    测试带下划线的内置配置项被正确过滤
    """
    
    def test_builtin_config_filtered(self):
        """
        测试内置配置项（带下划线）被过滤，不展示在前端
        
        场景：
        - 配置中包含带下划线的内置配置项
        - 验证这些配置项不会返回给前端
        """
        client = Client()
        skill_name = "内置配置过滤测试"
        
        # 准备：创建任务，配置中包含内置配置项
        定时任务.objects.create(
            名称="过滤测试任务",
            group_name=skill_name,
            激活=True,
            配置={
                "普通配置": "应该显示",
                "视频评论提示词_pdd_rights": "不应该显示",
                "视频评论提示词_3d_modeling": "不应该显示",
                "sys_prompt_cls": "不应该显示",
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证普通配置显示
        normal_keys = [k for k in keys if not k.get('_is_model_field')]
        key_names = [k['name'] for k in normal_keys]
        assert "普通配置" in key_names
        
        # 验证内置配置项（带下划线但非 _历史/_描述）不显示
        assert "视频评论提示词_pdd_rights" not in key_names
        assert "视频评论提示词_3d_modeling" not in key_names
        assert "sys_prompt_cls" not in key_names
        
        print("✅ 内置配置项过滤测试通过")
    
    def test_metadata_config_shown(self):
        """
        测试元数据配置（_历史、_描述）作为普通配置项的属性展示
        
        场景：
        - 配置中包含 _历史、_描述
        - 验证这些作为对应配置项的 history 和 description 展示
        """
        client = Client()
        skill_name = "元数据配置测试"
        
        # 准备：创建任务，配置中包含元数据
        定时任务.objects.create(
            名称="元数据任务",
            group_name=skill_name,
            激活=True,
            配置={
                "目标视频描述": "当前值",
                "目标视频描述_描述": "这是描述",
                "目标视频描述_历史": [
                    {"id": "h1", "created_at": "2024-01-01", "目标视频描述": "历史值"}
                ]
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 找到目标视频描述 key
        target_key = next((k for k in keys if k['name'] == '目标视频描述'), None)
        assert target_key is not None
        
        # 验证描述和历史被正确关联
        assert target_key['description'] == "这是描述"
        assert len(target_key['history']) == 1
        
        # 验证 _历史、_描述 不作为独立 key 展示
        key_names = [k['name'] for k in keys]
        assert "目标视频描述_描述" not in key_names
        assert "目标视频描述_历史" not in key_names
        
        print("✅ 元数据配置展示测试通过")


@pytest.mark.django_db
class TestSkillConfigDuplicateHandling:
    """
    【新增】重复配置处理测试
    测试 JSON 配置和 MODEL_CONFIG_FIELDS 重名时的处理逻辑
    """
    
    def test_model_field_overrides_json_config(self):
        """
        测试模型字段优先于 JSON 配置
        
        场景：
        - JSON 配置中有 "两次运行最小间隔秒" 这个 key
        - MODEL_CONFIG_FIELDS 也有 "两次运行最小间隔秒"
        - 验证只展示模型字段的值，JSON 中的被忽略
        """
        client = Client()
        skill_name = "重复配置处理测试"
        
        # 准备：创建任务，JSON 配置中有 "两次运行最小间隔秒"，同时模型字段也有值
        task = 定时任务.objects.create(
            名称="重复配置任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=600,  # 模型字段值
            配置={
                "两次运行最小间隔秒": 300,  # JSON 配置值（应该被忽略）
                "普通配置": "应该显示"
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证只返回一个 "两次运行最小间隔秒"（模型字段的）
        interval_keys = [k for k in keys if k['name'] == '两次运行最小间隔秒']
        assert len(interval_keys) == 1
        
        # 验证返回的是模型字段的值（600），而不是 JSON 中的值（300）
        assert interval_keys[0]['current_value'] == 600
        assert interval_keys[0].get('_is_model_field') == True
        
        # 验证普通配置正常显示
        normal_keys = [k for k in keys if k['name'] == '普通配置']
        assert len(normal_keys) == 1
        assert normal_keys[0]['current_value'] == '应该显示'
        
        print("✅ 模型字段优先于 JSON 配置测试通过")
    
    def test_save_with_duplicate_config_name(self):
        """
        测试保存时正确处理重名配置
        
        场景：
        - 前端传来的配置包含 "两次运行最小间隔秒"
        - 验证保存时正确区分 JSON 配置和模型字段
        """
        client = Client()
        skill_name = "保存重复配置测试"
        
        # 准备：创建任务
        task = 定时任务.objects.create(
            名称="保存测试任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=300,
            配置={"旧配置": "旧值"},
            设定时间=timezone.now()
        )
        
        # 新配置，包含两次运行最小间隔秒（标记为模型字段）
        config_with_interval = {
            "keys": [
                {
                    "name": "普通配置",
                    "type": "text",
                    "current_value": "普通值",
                    "history": []
                },
                {
                    "name": "两次运行最小间隔秒",
                    "type": "text",
                    "current_value": 900,  # 15 分钟
                    "history": [],
                    "_is_model_field": True  # 标记为模型字段
                }
            ]
        }
        
        # 执行：保存配置
        response = client.post(
            '/base/skill_config/save',
            data=json.dumps({
                "skill_name": skill_name,
                "config": config_with_interval
            }),
            content_type='application/json'
        )
        
        # 验证
        assert response.status_code == 200
        
        task.refresh_from_db()
        
        # 验证模型字段被更新
        assert task.两次运行最小间隔秒 == 900
        
        # 验证 JSON 配置中没有 "两次运行最小间隔秒"（因为被提取出来保存到模型字段了）
        assert "两次运行最小间隔秒" not in task.配置
        assert task.配置 == {"普通配置": "普通值"}
        
        print("✅ 保存时正确处理重名配置测试通过")
    
    def test_legacy_name_filtered(self):
        """
        【新增】测试旧名称配置被正确过滤
        
        场景：
        - 数据库中 JSON 配置使用旧名称 "两次运行最小间隔秒数"
        - MODEL_CONFIG_FIELDS 使用新名称 "两次运行最小间隔秒"
        - 验证只显示新名称的配置，旧名称被过滤掉
        """
        client = Client()
        skill_name = "旧名称过滤测试"
        
        # 准备：创建任务，JSON 配置中使用旧名称
        task = 定时任务.objects.create(
            名称="旧名称任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=600,  # 模型字段值
            配置={
                "两次运行最小间隔秒数": 300,  # 【旧名称】应该被过滤
                "普通配置": "应该显示"
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证只返回一个 "两次运行最小间隔秒"（新名称）
        interval_keys = [k for k in keys if k['name'] == '两次运行最小间隔秒']
        assert len(interval_keys) == 1
        
        # 验证返回的是模型字段的值（600）
        assert interval_keys[0]['current_value'] == 600
        
        # 验证旧名称 "两次运行最小间隔秒数" 没有出现在结果中
        legacy_keys = [k for k in keys if k['name'] == '两次运行最小间隔秒数']
        assert len(legacy_keys) == 0, f"旧名称不应该出现在结果中，但发现了: {legacy_keys}"
        
        # 验证普通配置正常显示
        normal_keys = [k for k in keys if k['name'] == '普通配置']
        assert len(normal_keys) == 1
        assert normal_keys[0]['current_value'] == '应该显示'
        
        print("✅ 旧名称配置正确过滤测试通过")
    
    def test_legacy_name_fallback(self):
        """
        【新增】测试旧名称配置作为回退值
        
        场景：
        - 模型字段值为 0（无效）
        - JSON 配置使用旧名称 "两次运行最小间隔秒数"
        - 验证从旧名称的 JSON 配置中回退读取值
        """
        client = Client()
        skill_name = "旧名称回退测试"
        
        # 准备：创建任务，模型字段为 0，JSON 使用旧名称
        task = 定时任务.objects.create(
            名称="旧名称回退任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=0,  # 模型字段无效
            配置={
                "两次运行最小间隔秒数": 550,  # 【旧名称】应该作为回退值
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证返回的是旧名称 JSON 中的值（550）
        interval_key = next((k for k in keys if k['name'] == '两次运行最小间隔秒'), None)
        assert interval_key is not None
        assert interval_key['current_value'] == 550
        
        print("✅ 旧名称配置作为回退值测试通过")


@pytest.mark.django_db
class TestModelFieldFallback:
    """
    【新增】测试模型字段值为空/0时的回退机制
    
    场景：
    - 模型字段值为 None 或 0 时，应该从 JSON 配置中回退读取
    - 这样可以支持"清空"模型字段后回退到默认值
    """
    
    def test_model_field_zero_fallback_to_json(self):
        """
        测试模型字段为 0 时从 JSON 回退
        """
        client = Client()
        skill_name = "模型字段0回退测试"
        
        # 准备：创建任务，模型字段为 0，JSON 配置中有值
        task = 定时任务.objects.create(
            名称="Zero回退任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=0,  # 模型字段为 0
            配置={
                "两次运行最小间隔秒": 550,  # JSON 配置值（应该被使用）
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证返回的是 JSON 中的值（550），因为模型字段为 0
        interval_key = next((k for k in keys if k['name'] == '两次运行最小间隔秒'), None)
        assert interval_key is not None
        assert interval_key['current_value'] == 550
        
        print("✅ 模型字段 0 回退到 JSON 配置测试通过")
    
    def test_model_field_effective_value_no_fallback(self):
        """
        测试模型字段有有效值时不回退
        """
        client = Client()
        skill_name = "模型字段有效值测试"
        
        # 准备：创建任务，模型字段有有效值
        task = 定时任务.objects.create(
            名称="有效值任务",
            group_name=skill_name,
            激活=True,
            两次运行最小间隔秒=750,  # 模型字段有有效值
            配置={
                "两次运行最小间隔秒": 250,  # JSON 配置值（应该被忽略）
            },
            设定时间=timezone.now()
        )
        
        # 执行：读取配置
        get_response = client.get(f'/base/skill_config?skill_name={skill_name}')
        
        # 验证
        assert get_response.status_code == 200
        data = json.loads(get_response.content)
        assert data['code'] == 2000
        
        config = data['data']['config']
        keys = config['keys']
        
        # 验证返回的是模型字段的值（750），而不是 JSON 中的值
        interval_key = next((k for k in keys if k['name'] == '两次运行最小间隔秒'), None)
        assert interval_key is not None
        assert interval_key['current_value'] == 750
        
        # 验证 JSON 中的同名配置被过滤掉（不会出现在 keys 中两次）
        interval_keys = [k for k in keys if k['name'] == '两次运行最小间隔秒']
        assert len(interval_keys) == 1
        
        print("✅ 模型字段有效值不回退测试通过")
