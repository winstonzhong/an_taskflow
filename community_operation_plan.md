# 🤖 都包代班儿 - 社区化运营功能模块执行计划 (Final v3 - daiban app)

> 确认版本 - 所有后端改动迁移到 daiban app
> 更新时间: 2024-01-xx

---

## 📋 项目结构说明

### 现有 App 分工

| App | 职责 | 说明 |
|-----|------|------|
| **base** | 本地任务执行 | 定时任务、设备控制、WebSocket |
| **daiban** | 用户/技能/订单管理 | 用户套餐、技能发布、支付订单 |

### 改动范围调整

**原 plan**：在 base app 中新增模型和 API  
**新 plan**：所有后端改动在 **daiban app** 中实现

---

## 🗄️ 数据库模型设计（daiban app）

### 1. 技能反馈表 (SkillFeedback)

**文件**: `daiban/models.py`（追加）

```python
class SkillFeedback(models.Model):
    """技能反馈（点赞/想要/评分/评论）"""
    FEEDBACK_TYPES = [
        ('like', '点赞'),
        ('want', '想要'),
        ('rating', '评分'),
        ('comment', '评论'),
    ]
    
    skill_name = models.CharField(max_length=100, verbose_name='技能名称')
    用户 = models.ForeignKey("都包用户", on_delete=models.CASCADE, verbose_name='用户')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, verbose_name='反馈类型')
    rating = models.IntegerField(null=True, blank=True, verbose_name='评分(1-5星)')
    content = models.TextField(blank=True, null=True, verbose_name='评论内容')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'daiban_skill_feedback'
        unique_together = ['skill_name', '用户', 'feedback_type']
        indexes = [
            models.Index(fields=['skill_name', 'feedback_type']),
            models.Index(fields=['用户']),
        ]
```

### 2. 用户反馈表 (UserFeedback)

**文件**: `daiban/models.py`（追加）

```python
class UserFeedback(models.Model):
    """用户反馈（功能建议/问题反馈）"""
    FEEDBACK_TYPES = [
        ('want_feature', '想要的功能'),
        ('skill_idea', '技能开发建议'),
        ('bug', '问题反馈'),
        ('other', '其他建议'),
    ]
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('rejected', '已拒绝'),
    ]
    
    用户 = models.ForeignKey("都包用户", on_delete=models.CASCADE, verbose_name='用户')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, verbose_name='反馈类型')
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='详细内容')
    contact = models.CharField(max_length=100, blank=True, null=True, verbose_name='联系方式')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='处理状态')
    admin_reply = models.TextField(blank=True, null=True, verbose_name='管理员回复')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'daiban_user_feedback'
        ordering = ['-create_time']
```

### 3. 技能热度统计表 (SkillStats)

**文件**: `daiban/models.py`（追加）

```python
class SkillStats(models.Model):
    """技能热度统计"""
    skill_name = models.CharField(max_length=100, primary_key=True, verbose_name='技能名称')
    like_count = models.IntegerField(default=0, verbose_name='点赞数')
    want_count = models.IntegerField(default=0, verbose_name='想要数')
    rating_count = models.IntegerField(default=0, verbose_name='评价数')
    rating_sum = models.IntegerField(default=0, verbose_name='评分总和')
    use_count = models.IntegerField(default=0, verbose_name='使用次数')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'daiban_skill_stats'
    
    @property
    def hot_score(self):
        """热度分 = 点赞*2 + 想要*1"""
        return self.like_count * 2 + self.want_count
    
    @property
    def avg_rating(self):
        if self.rating_count == 0:
            return 0
        return round(self.rating_sum / self.rating_count, 1)
```

### 4. 现有模型复用

| 功能 | 现有模型 | 说明 |
|------|----------|------|
| 用户信息 | `都包用户` | 已有套餐、到期时间字段 |
| 技能数据 | `都包技能` | 已有技能名称、配置字段 |
| 用户设备 | `都包用户设备` | 已有 SN 关联 |

---

## 🔌 API 接口设计（daiban app）

### URL 路由（daiban/urls.py）

```python
# 追加到 daiban/urls.py
urlpatterns += [
    # 技能市场相关
    path("skills/market_list", views.技能市场列表视图.as_view()),
    path("skills/detail/<str:skill_name>", views.技能详情视图.as_view()),
    path("skills/feedback", views.技能反馈视图.as_view()),
    path("skills/add_to_queue", views.添加到执行队列视图.as_view()),
    path("skills/comments/<str:skill_name>", views.技能评价列表视图.as_view()),
    
    # 用户反馈相关
    path("user/feedback", views.用户反馈提交视图.as_view()),
    path("user/feedback_list", views.用户反馈列表视图.as_view()),
    
    # 个人中心相关
    path("user/plan", views.用户套餐信息视图.as_view()),
    path("user/device_name", views.设备名称修改视图.as_view()),
]
```

### 视图实现（daiban/views.py 追加）

```python
# ==================== 技能市场相关视图 ====================

class 技能市场列表视图(APIView):
    """技能市场列表（支持筛选、排序、搜索）"""
    def get(self, request):
        # 从都包技能表获取已发布技能
        # 关联 SkillStats 获取热度数据
        # 返回技能列表
        pass

class 技能详情视图(APIView):
    """技能详情"""
    def get(self, request, skill_name):
        # 获取技能详细信息
        # 关联 SkillFeedback 获取评价
        # 返回详情数据
        pass

class 技能反馈视图(APIView):
    """提交技能反馈（点赞/想要/评分/评论）"""
    def post(self, request):
        # 创建 SkillFeedback 记录
        # 更新 SkillStats 统计
        pass

class 添加到执行队列视图(APIView):
    """添加技能到执行队列（直接启用）"""
    def post(self, request):
        # 通过某种方式通知 base app 启用技能
        # 或创建执行记录
        pass

class 技能评价列表视图(APIView):
    """获取技能评价列表"""
    def get(self, request, skill_name):
        # 获取 SkillFeedback 中 comment 类型的记录
        pass


# ==================== 用户反馈相关视图 ====================

class 用户反馈提交视图(APIView):
    """提交用户反馈"""
    def post(self, request):
        # 创建 UserFeedback 记录
        pass

class 用户反馈列表视图(APIView):
    """获取用户反馈列表"""
    def get(self, request):
        # 根据 user_sn 获取反馈列表
        pass


# ==================== 个人中心相关视图 ====================

class 用户套餐信息视图(APIView):
    """获取用户套餐信息"""
    def get(self, request):
        # 从都包用户表获取套餐、到期时间
        # 返回套餐信息
        pass

class 设备名称修改视图(APIView):
    """修改设备名称"""
    def post(self, request):
        # 更新都包用户设备表
        pass
```

---

## 🖼️ 前端页面（base app）

前端页面保留在 **base app** 中（因为是本地控制界面）：

| 页面 | 位置 | 说明 |
|------|------|------|
| 控制页 | `templates/control.html` | 左侧列表增强 |
| 技能市场 | `templates/skill_market.html` | 新增页面 |
| 个人中心 | `templates/profile.html` | 新增页面 |

前端调用 **daiban app** 的 API：

```javascript
// 前端 API 调用示例
const API_BASE = '/daiban';  // 统一前缀

// 获取技能列表
fetch(`${API_BASE}/skills/market_list?category=wechat`)

// 提交反馈
fetch(`${API_BASE}/skills/feedback`, {
    method: 'POST',
    body: JSON.stringify({skill_name, feedback_type})
})

// 获取用户套餐
fetch(`${API_BASE}/user/plan?sn=${sn}`)
```

---

## 📁 文件变更清单

### daiban app（后端）

```
daiban/
├── models.py              # 追加 SkillFeedback, UserFeedback, SkillStats
├── views.py               # 追加技能市场/反馈/个人中心视图
├── urls.py                # 追加 API 路由
└── admin.py               # 追加 Admin 配置（可选）
```

### base app（前端）

```
base/
├── views.py               # 追加页面渲染视图（skill_market, profile）
├── urls.py                # 追加页面路由
└── 无需新增模型

templates/
├── control.html           # 修改：左侧列表增强
├── skill_market.html      # 新增：技能市场页面
└── profile.html           # 新增：个人中心页面
```

---

## 📅 更新后的实施计划

### 第一阶段：daiban app 后端开发（3天）

**Day 1: 模型创建**
- [ ] 在 `daiban/models.py` 追加 SkillFeedback 模型
- [ ] 在 `daiban/models.py` 追加 UserFeedback 模型
- [ ] 在 `daiban/models.py` 追加 SkillStats 模型
- [ ] 生成并执行迁移文件

**Day 2: API 开发 - 技能市场**
- [ ] `技能市场列表视图` - 技能列表（筛选/排序/搜索）
- [ ] `技能详情视图` - 技能详情
- [ ] `技能反馈视图` - 点赞/想要/评分/评论
- [ ] `添加到执行队列视图` - 启用技能

**Day 3: API 开发 - 用户相关**
- [ ] `用户反馈提交视图` - 提交反馈
- [ ] `用户反馈列表视图` - 我的反馈
- [ ] `用户套餐信息视图` - 套餐信息（复用都包用户表）
- [ ] `设备名称修改视图` - 修改设备名
- [ ] API 测试

### 第二阶段：base app 前端开发（4天）

**Day 4-5: 控制页增强**
- [ ] 左侧技能列表 UI 改造
- [ ] 配置弹窗（左右分栏式）
- [ ] 自动保存功能

**Day 6: 技能市场页面**
- [ ] 技能列表页面
- [ ] 技能详情弹窗
- [ ] 互动功能（点赞/想要/添加到执行）

**Day 7: 个人中心与反馈**
- [ ] 个人中心页面
- [ ] 反馈提交弹窗
- [ ] 我的反馈列表

### 第三阶段：联调与优化（2天）

**Day 8-9: 联调测试**
- [ ] 前后端联调
- [ ] 数据一致性检查
- [ ] 性能优化

**总计：9天**

---

## 🔗 base 与 daiban 的交互

### 问题：base 如何获取 daiban 的数据？

**方案：通过 API 调用（推荐）**

```python
# base/views.py 中调用 daiban 的 API
import requests

def get_skill_market_list(request):
    # 内部调用 daiban API
    response = requests.get(
        'http://localhost:8001/daiban/skills/market_list',
        params=request.GET
    )
    return JsonResponse(response.json())
```

**或者：直接导入 daiban 的模型**

```python
# base/views.py
from daiban.models import SkillStats, SkillFeedback, UserFeedback, 都包用户

def get_skill_hot_score(skill_name):
    # 直接查询 daiban 的模型
    stats = SkillStats.objects.filter(skill_name=skill_name).first()
    return stats.hot_score if stats else 0

def get_user_feedbacks(user):
    # 通过外键关联查询用户的反馈
    return UserFeedback.objects.filter(用户=user).order_by('-create_time')

def get_skill_feedbacks(skill_name):
    # 查询技能的所有反馈（包含用户信息）
    return SkillFeedback.objects.filter(skill_name=skill_name).select_related('用户')
```

**推荐：直接导入模型方式**（更简单，无需 HTTP 调用）

---

## ✅ 最终确认清单

| 确认项 | 状态 | 说明 |
|--------|------|------|
| 后端改动位置 | ✅ | 全部在 **daiban app** |
| 前端页面位置 | ✅ | 在 **base app** 的 templates |
| base/daiban 交互 | ✅ | base 直接导入 daiban 的模型 |
| 配置弹窗结构 | ✅ | 两层 JSON，左侧分类，右侧配置项 |
| 自动保存 | ✅ | onchange 触发，无保存按钮 |
| 套餐信息来源 | ✅ | 复用 **都包用户** 表 |
| 购买链接 | ✅ | https://coco.j1.sale/pages/daiban/packages.html |

---

**是否立即开始开发？请回复「开始」确认！**
