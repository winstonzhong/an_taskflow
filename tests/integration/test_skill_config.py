"""
技能配置保存测试
测试 save_skill_config 接口的批量更新功能
"""

import json
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
        
        assert task1.配置 == new_config
        assert task2.配置 == new_config
        assert task3.配置 == new_config
        
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
                    "type": "kv",
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
        
        assert len(retrieved_config['keys']) == 2
        assert retrieved_config['keys'][0]['name'] == "API密钥"
        assert retrieved_config['keys'][0]['current_value'] == "sk-123456"
        assert retrieved_config['keys'][1]['type'] == "kv"
        
        print("✅ 保存和读取配置一致性测试通过")
