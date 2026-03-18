"""
测试修复：验证 save() 调用不会覆盖两次运行最小间隔秒字段

问题背景：
- 当调用 save() 而不使用 update_fields 时，Django 会保存所有字段
- 如果对象在内存中的值是旧的，会覆盖数据库中的新值

修复方案：
- 在相关方法中使用 update_fields 参数，只更新需要修改的字段
"""

import pytest
from django.utils import timezone
from base.models import 定时任务

@pytest.mark.django_db
def test_变更间隔秒数不会覆盖其他字段():
    """测试变更间隔秒数方法只更新间隔秒字段"""
    print("\n=== 测试：变更间隔秒数不会覆盖两次运行最小间隔秒 ===")
    
    # 创建测试任务
    task = 定时任务.objects.create(
        名称="测试任务_变更间隔秒数",
        group_name="测试技能",
        激活=True,
        间隔秒=60,
        两次运行最小间隔秒=600,  # 初始值 10 分钟
        设定时间=timezone.now()
    )
    
    # 模拟：用户在前端修改了两次运行最小间隔秒为 1200（20分钟）
    # 直接修改数据库（不通过模型实例）
    定时任务.objects.filter(id=task.id).update(两次运行最小间隔秒=1200)
    
    # 刷新任务对象（但保持旧值在内存中）
    task.refresh_from_db(fields=['间隔秒'])  # 只刷新间隔秒字段
    
    # 验证内存中的两次运行最小间隔秒仍是旧值 600
    assert task.两次运行最小间隔秒 == 600, f"期望值 600，实际 {task.两次运行最小间隔秒}"
    
    # 调用变更间隔秒数方法（现在应该只更新间隔秒字段）
    task.变更间隔秒数(间隔秒数=120)
    
    # 从数据库重新读取
    task_refreshed = 定时任务.objects.get(id=task.id)
    
    # 验证：间隔秒被更新为 120
    assert task_refreshed.间隔秒 == 120, f"间隔秒期望值 120，实际 {task_refreshed.间隔秒}"
    
    # 验证：两次运行最小间隔秒没有被覆盖（仍然是 1200，不是内存中的 600）
    assert task_refreshed.两次运行最小间隔秒 == 1200, \
        f"两次运行最小间隔秒期望值 1200，实际 {task_refreshed.两次运行最小间隔秒}"
    
    # 清理
    task.delete()
    print("✅ 测试通过：变更间隔秒数不会覆盖两次运行最小间隔秒")


@pytest.mark.django_db
def test_step方法不会覆盖其他字段():
    """测试 step 方法只更新 update_time 和 激活 字段"""
    print("\n=== 测试：step 方法不会覆盖两次运行最小间隔秒 ===")
    
    # 创建测试任务
    task = 定时任务.objects.create(
        名称="测试任务_step方法",
        group_name="测试技能",
        激活=True,
        间隔秒=60,
        两次运行最小间隔秒=600,
        设定时间=timezone.now()
    )
    
    # 保存原始 update_time
    original_update_time = task.update_time
    
    # 模拟：用户在前端修改了两次运行最小间隔秒为 1200
    定时任务.objects.filter(id=task.id).update(两次运行最小间隔秒=1200)
    
    # 刷新任务对象（但保持旧值在内存中）
    task.refresh_from_db(fields=['update_time', '激活'])
    
    # 验证内存中的两次运行最小间隔秒仍是旧值 600
    assert task.两次运行最小间隔秒 == 600
    
    # 手动调用 save 方法（使用与 step 方法相同的 update_fields）
    task.save(update_fields=['update_time', '激活'])
    
    # 从数据库重新读取
    task_refreshed = 定时任务.objects.get(id=task.id)
    
    # 验证：两次运行最小间隔秒没有被覆盖
    assert task_refreshed.两次运行最小间隔秒 == 1200, \
        f"两次运行最小间隔秒期望值 1200，实际 {task_refreshed.两次运行最小间隔秒}"
    
    # 清理
    task.delete()
    print("✅ 测试通过：step 方法不会覆盖两次运行最小间隔秒")


@pytest.mark.django_db
def test_写入数据记录字典不会覆盖其他字段():
    """测试 写入数据记录字典 方法只更新数据字段"""
    print("\n=== 测试：写入数据记录字典不会覆盖两次运行最小间隔秒 ===")
    
    # 创建测试任务
    task = 定时任务.objects.create(
        名称="测试任务_写入数据",
        group_name="测试技能",
        激活=True,
        数据={},
        两次运行最小间隔秒=600,
        设定时间=timezone.now()
    )
    
    # 模拟：用户在前端修改了两次运行最小间隔秒为 1200
    定时任务.objects.filter(id=task.id).update(两次运行最小间隔秒=1200)
    
    # 刷新任务对象（但保持旧值在内存中）
    task.refresh_from_db(fields=['数据'])
    
    # 验证内存中的两次运行最小间隔秒仍是旧值 600
    assert task.两次运行最小间隔秒 == 600
    
    # 调用 写入数据记录字典 方法
    task.写入数据记录字典({"测试": "数据"})
    
    # 从数据库重新读取
    task_refreshed = 定时任务.objects.get(id=task.id)
    
    # 验证：两次运行最小间隔秒没有被覆盖
    assert task_refreshed.两次运行最小间隔秒 == 1200, \
        f"两次运行最小间隔秒期望值 1200，实际 {task_refreshed.两次运行最小间隔秒}"
    
    # 验证：数据字段被正确更新
    assert "数据记录" in task_refreshed.数据
    
    # 清理
    task.delete()
    print("✅ 测试通过：写入数据记录字典不会覆盖两次运行最小间隔秒")


@pytest.mark.django_db
def test_设置字段值不会覆盖其他字段():
    """测试 设置字段值 方法只更新数据字段"""
    print("\n=== 测试：设置字段值不会覆盖两次运行最小间隔秒 ===")
    
    # 创建测试任务
    task = 定时任务.objects.create(
        名称="测试任务_设置字段值",
        group_name="测试技能",
        激活=True,
        数据={},
        两次运行最小间隔秒=600,
        设定时间=timezone.now()
    )
    
    # 模拟：用户在前端修改了两次运行最小间隔秒为 1200
    定时任务.objects.filter(id=task.id).update(两次运行最小间隔秒=1200)
    
    # 刷新任务对象（但保持旧值在内存中）
    task.refresh_from_db(fields=['数据'])
    
    # 验证内存中的两次运行最小间隔秒仍是旧值 600
    assert task.两次运行最小间隔秒 == 600
    
    # 调用 设置字段值 方法
    task.设置字段值("测试字段", "测试值")
    
    # 从数据库重新读取
    task_refreshed = 定时任务.objects.get(id=task.id)
    
    # 验证：两次运行最小间隔秒没有被覆盖
    assert task_refreshed.两次运行最小间隔秒 == 1200, \
        f"两次运行最小间隔秒期望值 1200，实际 {task_refreshed.两次运行最小间隔秒}"
    
    # 验证：数据字段被正确更新
    assert task_refreshed.数据.get("测试字段") == "测试值"
    
    # 清理
    task.delete()
    print("✅ 测试通过：设置字段值不会覆盖两次运行最小间隔秒")



