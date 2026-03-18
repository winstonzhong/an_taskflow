import json
import time
import traceback

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from base.models import 定时任务, 配置表
from commons.constants import API_RET_CODE_PARAMS_ERROR, API_RET_CODE_RECORD_NOT_EXISTED_ERROR
from commons.exceptions import RecordNotExistedError
from commons.helper_cache import 获取页面数据, 插入操作数据, 更新知识库
from commons.utils import api_ret_data, format_field
from tool_img import bin_to_base64url


def _convert_to_keys_format(config):
    """
    将数据库存储格式转换为前端需要的 keys 格式
    
    规则：
    - 无下划线的 key → 普通配置项，展示
    - 以 _历史 结尾 → 作为对应 key 的 history 字段
    - 以 _描述 结尾 → 作为对应 key 的 description 字段
    - 其他带下划线的 → 内置配置项，不展示
    
    Args:
        config: 数据库中存储的配置字典
        
    Returns:
        dict: {"keys": [...]} 格式
    """
    if not isinstance(config, dict):
        return {"keys": []}
    
    # 收集所有元数据
    metadata = {}  # {base_key: {"history": [...], "description": "..."}}
    base_keys = []
    
    for key in config.keys():
        if "_" not in key:
            # 普通配置项（无下划线）
            base_keys.append(key)
        elif key.endswith("_历史"):
            base_key = key[:-3]  # 去掉 "_历史"
            metadata.setdefault(base_key, {})["history"] = config[key]
        elif key.endswith("_描述"):
            base_key = key[:-3]  # 去掉 "_描述"
            metadata.setdefault(base_key, {})["description"] = config[key]
        # 其他带下划线的（内置配置项）直接忽略，不展示
    
    # 构建 keys 列表（只包含普通配置项）
    keys = []
    for idx, key in enumerate(base_keys):
        value = config[key]
        meta = metadata.get(key, {})
        is_object = isinstance(value, dict)
        
        keys.append({
            "id": f"key_{idx}_{int(time.time() * 1000)}",
            "name": key,
            "description": meta.get("description", ""),
            "type": "object" if is_object else "text",
            "current_value": value,
            "history": meta.get("history", [])
        })
    
    return {"keys": keys}


def _convert_from_keys_format(keys_config, original_config=None):
    """
    将前端 keys 格式转换为数据库存储格式
    
    Args:
        keys_config: 前端传来的 {"keys": [...]} 格式
        original_config: 原始配置（用于保留内置配置项）
        
    Returns:
        dict: 存储到数据库的配置字典
    """
    # 如果提供了原始配置，保留其中的内置配置项（带下划线的）
    new_config = {}
    if original_config and isinstance(original_config, dict):
        for key, value in original_config.items():
            if "_" in key and not key.endswith("_历史") and not key.endswith("_描述"):
                # 保留内置配置项（如 视频评论提示词_pdd_rights）
                new_config[key] = value
    
    # 写入新的普通配置项和元数据
    for key in keys_config.get("keys", []):
        name = key["name"]
        # 存储主值
        new_config[name] = key["current_value"]
        
        # 存储描述（如果有）
        if key.get("description"):
            new_config[f"{name}_描述"] = key["description"]
        
        # 存储历史（如果有）
        if key.get("history"):
            new_config[f"{name}_历史"] = key["history"]
    
    return new_config


def _convert_to_keys_format_with_merge(db_config, filtered_config):
    """
    将过滤后的配置转换为前端需要的 keys 格式，同时提取历史和描述
    
    Args:
        db_config: 数据库中存储的配置（用于提取历史和描述等元数据，可能为空）
        filtered_config: 过滤后的配置（从 基本任务.config 过滤内置配置项后的结果，包含历史和描述）
        
    Returns:
        dict: {"keys": [...]} 格式
    """
    if not isinstance(db_config, dict):
        db_config = {}
    
    # 【修改】从 filtered_config 中收集元数据（历史和描述）
    # 因为历史和描述可能在 基本任务.config 中（远程 paras + 本地配置合并后的结果）
    metadata = {}
    for key in filtered_config.keys():
        if key.endswith("_历史"):
            base_key = key[:-3]  # 去掉 "_历史"
            metadata.setdefault(base_key, {})["history"] = filtered_config[key]
        elif key.endswith("_描述"):
            base_key = key[:-3]  # 去掉 "_描述"
            metadata.setdefault(base_key, {})["description"] = filtered_config[key]
    
    # 【补充】也从 db_config 中收集（本地配置的元数据优先级更高）
    for key in db_config.keys():
        if key.endswith("_历史"):
            base_key = key[:-3]
            metadata.setdefault(base_key, {})["history"] = db_config[key]
        elif key.endswith("_描述"):
            base_key = key[:-3]
            metadata.setdefault(base_key, {})["description"] = db_config[key]
    
    # 使用 filtered_config 的值（已过滤内置配置项，排除元数据 key）
    keys = []
    for idx, (key, value) in enumerate(filtered_config.items()):
        # 跳过元数据 key
        if key.endswith("_历史") or key.endswith("_描述"):
            continue
        
        meta = metadata.get(key, {})
        is_object = isinstance(value, dict)
        
        keys.append({
            "id": f"key_{idx}_{int(time.time() * 1000)}",
            "name": key,
            "description": meta.get("description", ""),
            "type": "object" if is_object else "text",
            "current_value": value,
            "history": meta.get("history", [])
        })
    
    return {"keys": keys}


def 获取记录(func):
    """独立装饰器：无需依赖任何类，可复用"""

    def wrapper(self, request, *args, **kwargs):  # 注意：第一个参数是视图实例self
        # 业务逻辑：获取记录（如需动态参数，可后续优化为带参装饰器）
        obj = 定时任务.objects.filter(名称='微信自动机器人_xml').first()
        if not obj:  # 完善None判断
            ret_data = api_ret_data()
            ret_data['code'] = API_RET_CODE_RECORD_NOT_EXISTED_ERROR
            ret_data['msg'] = '任务记录不存在'
            return JsonResponse(ret_data)

        # 方案一：关键字参数传递obj
        return func(self, request, *args, obj=obj, **kwargs)

    return wrapper


def get_mock_img_data():
    with open('/mnt/d/tmp/wx_list.jpg', 'rb') as f:
        img = f.read()
    page_data = {"img_data": img,
                 "status": "ready",  # running/ready
                 "page_name": "session_list",
                 "is_show_edit": False,
                 "is_in_wx": True,
                 }
    return page_data

def get_mock_img_data2():
    with open('/mnt/d/tmp/wx_detail.jpg', 'rb') as f:
        img = f.read()
    page_data = {"img_data": img,
                 "status": "ready",  # running/ready
                 "page_name": "session_detail",
                 "is_show_edit": False,
                 'prompt': '这是提示词',
                 'reply': '这是回复',
                 "is_in_wx": True,
                 'friend': '张三',
                 }
    return page_data

def get_mock_config_data():
    ret_data = {
          "roles": [
            {
              "name": "职场助手",
              "description": "设定为职场助手角色，熟悉办公软件操作，能够解答工作相关问题，性格耐心细致，回复语言简洁专业，背景为5年行政工作经验的职场人士。"
            },
            {
              "name": "技术支持",
              "description": "设定为技术支持角色，熟悉各类软件和硬件问题排查，能够提供清晰的技术指导，语言通俗易懂，背景为10年IT技术支持经验。"
            },
            {
              "name": "客服专员",
              "description": "设定为客服专员角色，擅长沟通协调，服务态度热情友好，能够有效解决客户问题和投诉，背景为8年客户服务经验。"
            }
          ],
          "selected_role": "职场助手",
          "is_default_manual_reply": False,
          "manual_reply_prompts": "示例：1. 消息中包含敏感词汇（如：转账、密码、验证码等）；2. 对方发送的消息长度超过500字；3. 涉及金钱交易、个人信息提供等内容；4. 连续发送3条及以上催促回复的消息。",
          "knowledge_base_content": "xx"
        }
    ret_data.pop("knowledge_base_content", "")

    return ret_data


class 页面数据视图(APIView):

    @获取记录
    def get(self, request, *args, obj=None, **kwargs):
        page_data = 获取页面数据()
        # page_data = get_mock_img_data2()
        if page_data:
            page_data['img_data'] = bin_to_base64url(page_data['img_data'])
            page_data['config'] = obj.用户配置(page_data.get('friend'))
        # print('page_data', page_data)
        ret_data = api_ret_data(page_data)
        return JsonResponse(ret_data)


class 页面操作视图(APIView):

    def post(self, request):
        data = request.data
        ret_data = api_ret_data()
        if not data.get('operation_type'):
            ret_data['code'] = API_RET_CODE_PARAMS_ERROR
            ret_data['msg'] = '参数错误'
            return JsonResponse(ret_data)
        # print('data', data)
        插入操作数据(data)
        return JsonResponse(ret_data)


class 用户配置视图(APIView):

    @获取记录
    def get(self, request, *args, obj=None, **kwargs):

        配置数据 = obj.用户配置
        # 配置数据 = get_mock_config_data()
        ret_data = api_ret_data(配置数据)
        return JsonResponse(ret_data)

    @获取记录
    def post(self, request, *args, obj=None, **kwargs):
        ret_data = api_ret_data()

        data = request.data or dict()
        # print('data', data)

        key = data.get('key')
        value = data.get('value')
        friend = data.get('friend')
        if not key:
            ret_data['code'] = API_RET_CODE_PARAMS_ERROR
            ret_data['msg'] = '参数错误'
            return JsonResponse(ret_data)
        obj.保存用户配置(key, value, friend=friend)
        return JsonResponse(ret_data)

class 更新sn(APIView):

    def post(self, request):
        data = request.data
        sn = data.get('sn')
        配置表.更新sn(sn)
        ret_data = api_ret_data()
        return JsonResponse(ret_data)

class 用户知识库视图(APIView):

    @获取记录
    def post(self, request, *args, obj=None, **kwargs):
        ret_data = api_ret_data()
        # print('files', dir(request.FILES))

        # 1. 获取上传的文件
        if 'file' not in request.FILES:
            return JsonResponse({
                'code': 4000,
                'msg': '请选择要上传的文件'
            }, status=400)
        uploaded_file = request.FILES['file']
        # print('name', uploaded_file.name)
        # 2. 读取文件二进制内容（分块读取，兼容大文件）
        file_binary_data = b""
        for chunk in uploaded_file.chunks():
            file_binary_data += chunk

        obj.知识库 = file_binary_data
        obj.保存用户配置('knowledge_base_fname', uploaded_file.name)
        obj.save()


        # op_data = {
        #     'operation_type': 'knownledge_base',
        #     'data': {'bin': file_binary_data}
        # }
        # 插入操作数据(op_data)

        更新知识库(file_binary_data)

        return JsonResponse(ret_data)


def 控制页面(request):
    if request.method == 'GET':
        return render(request, 'control.html',
                      )


class 技能视图(APIView):

    def get(self, request):
        ret_data = api_ret_data()
        force_fetch = request.GET.get('force_fetch')
        user_key = request.GET.get('user_key')
        
        # 分页参数
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))

        print('force_fetch', force_fetch)
        if force_fetch:
            try:
                定时任务.从远端导入定时任务(user_key)
            except:
                traceback.print_exc()
        
        技能列表 = 定时任务.获取所有技能()
        
        # 分页处理
        total = len(技能列表)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_list = 技能列表[start_index:end_index]
        
        ret_data['data'] = paginated_list
        ret_data['pagination'] = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'has_more': end_index < total
        }
        return JsonResponse(ret_data)


# ==================== 新增：技能配置相关接口 ====================

@require_http_methods(["GET"])
def get_skill_config(request):
    """
    读取技能配置（新版 - 支持三栏式配置编辑器格式）
    
    GET /base/skill_config?skill_name=微信自动回复
    
    Parameters:
        - skill_name: 技能名称（对应 group_name 字段）
    
    Response:
    {
        "code": 2000,
        "data": {
            "skill_name": "微信自动回复",
            "config": {
                "keys": [
                    {
                        "id": "key_xxx",
                        "name": "回复模板",
                        "description": "自动回复的文本模板",
                        "type": "text",
                        "current_value": "你好，{nickname}...",
                        "history": []
                    },
                    {
                        "id": "key_xxx",
                        "name": "关键词回复",
                        "description": "关键词触发的回复",
                        "type": "object",
                        "current_value": {"你好": "您好"},
                        "history": [
                            {
                                "id": "hist_xxx",
                                "timestamp": "2026-02-28...",
                                "preview": "预览内容",
                                "value": {...}
                            }
                        ]
                    }
                ]
            }
        }
    }
    """
    skill_name = request.GET.get('skill_name')
    
    if not skill_name:
        return JsonResponse({
            "code": 4000,
            "message": "缺少 skill_name 参数"
        }, status=400)
    
    # 查询 group_name 匹配的记录（取最后一条）
    task = 定时任务.objects.filter(group_name=skill_name).last()
    
    if task:
        # 【修改】从基本任务.config 读取全量配置（已合并远程 paras + 本地配置）
        full_config = {}
        try:
            # 获取远程流程
            远程流程 = task.远程流程
            # 获取主任务的 config（已合并的全量配置，包括内置配置项）
            if 远程流程.jobs:
                主任务 = 远程流程.jobs[-1]
                full_config = dict(主任务.config)  # PropDict 转普通 dict
        except Exception as e:
            print(f"[get_skill_config] 获取远程配置失败: {e}")
        
        # 【新增】如果无法从远程流程获取配置，降级到从 task.配置 读取
        if not full_config and task.配置:
            # 使用 task.配置作为数据源（兼容测试场景）
            if "keys" in task.配置:
                # 已经是前端格式，直接返回
                return JsonResponse({
                    "code": 2000,
                    "data": {
                        "skill_name": skill_name,
                        "config": task.配置
                    }
                })
            else:
                # 数据库存储格式，转换为前端格式
                full_config = dict(task.配置)
        
        # 【新增】过滤内置配置项（只在前端展示时过滤）
        # 只展示：无下划线的普通配置项 + 元数据（_历史、_描述）
        filtered_config = {}
        for key, value in full_config.items():
            # 无下划线的普通配置项 → 展示
            if "_" not in key:
                filtered_config[key] = value
            # 以 _历史/_描述 结尾的元数据 → 展示（作为对应 key 的属性）
            elif key.endswith("_历史") or key.endswith("_描述"):
                filtered_config[key] = value
            # 其他带下划线的内置配置项 → 不展示（如 视频评论提示词_pdd_rights）
        
        # 【修改】过滤掉与 MODEL_CONFIG_FIELDS 重名的配置项（模型字段优先）
        model_field_names = set(定时任务.MODEL_CONFIG_FIELDS.keys())
        filtered_config = {
            k: v for k, v in filtered_config.items() 
            if k not in model_field_names and not k.endswith("_历史") and not k.endswith("_描述")
        }
        # 保留元数据（历史和描述）
        for k, v in full_config.items():
            if (k.endswith("_历史") or k.endswith("_描述")) and k.replace("_历史", "").replace("_描述", "") not in model_field_names:
                filtered_config[k] = v
        
        # 转换为前端格式（使用 task.配置 中的元数据）
        converted_config = _convert_to_keys_format_with_merge(task.配置, filtered_config)
        
        # 【新增】注入模型字段配置（如 两次运行最小间隔秒数）
        # 这些字段存储在模型字段中，但前端展示为普通配置项
        # 注意：MODEL_CONFIG_FIELDS 中的字段会覆盖 JSON 中的同名配置
        for config_name, field_info in 定时任务.MODEL_CONFIG_FIELDS.items():
            field_name = field_info['field']
            field_type = field_info.get('type', str)
            
            # 直接从模型字段读取值（None 也直接传递，让前端处理）
            current_value = getattr(task, field_name, None)
            
            # 根据类型转换（如果不是 None）
            if current_value is not None and field_type == int:
                current_value = int(current_value)
            elif current_value is not None and field_type == bool:
                current_value = bool(current_value)
            
            # 添加到配置中
            converted_config['keys'].append({
                "id": f"key_model_{config_name}",
                "name": config_name,
                "description": f"{config_name}（模型字段）",
                "type": "text" if field_type in [int, str] else "object",
                "current_value": current_value,
                "history": [],
                "_is_model_field": True  # 标记为模型字段，保存时特殊处理
            })
        
        return JsonResponse({
            "code": 2000,
            "data": {
                "skill_name": skill_name,
                "config": converted_config
            }
        })
    
    # 数据库中无数据，返回空配置
    return JsonResponse({
        "code": 2000,
        "data": {
            "skill_name": skill_name,
            "config": {
                "keys": []
            }
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def save_skill_config(request):
    """
    保存技能配置（新版 - 支持三栏式配置编辑器格式）
    
    POST /base/skill_config/save
    
    Request Body:
    {
        "skill_name": "微信自动回复",
        "config": {
            "keys": [
                {
                    "id": "key_xxx",
                    "name": "回复模板",
                    "description": "",
                    "type": "text",
                    "current_value": "...",
                    "history": [...]
                }
            ]
        }
    }
    
    也支持旧格式保存（后端自动转换）:
    {
        "skill_name": "微信自动回复",
        "config": {
            "回复设置": {...},
            "高级选项": {...}
        }
    }
    
    Response:
    {
        "code": 2000,
        "message": "保存成功"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            "code": 4000,
            "message": "请求体必须是有效的JSON"
        }, status=400)
    
    skill_name = data.get('skill_name')
    config = data.get('config', {})
    
    if not skill_name:
        return JsonResponse({
            "code": 4000,
            "message": "缺少 skill_name 参数"
        }, status=400)
    
    # 查询所有 group_name 匹配的记录
    tasks = 定时任务.objects.filter(group_name=skill_name).order_by('id')
    
    if not tasks.exists():
        return JsonResponse({
            "code": 4004,
            "message": "技能不存在"
        }, status=404)
    
    # 【新增】提取模型字段配置（如 两次运行最小间隔秒数）
    model_field_updates = {}
    if 'keys' in config:
        # 遍历所有 key，提取模型字段
        keys_to_keep = []
        for key in config['keys']:
            key_name = key.get('name', '')
            if key_name in 定时任务.MODEL_CONFIG_FIELDS:
                # 这是模型字段，提取值用于更新模型
                field_info = 定时任务.MODEL_CONFIG_FIELDS[key_name]
                field_name = field_info['field']
                field_type = field_info.get('type', str)
                current_value = key.get('current_value')
                
                # 类型转换
                if current_value is not None:
                    try:
                        if field_type == int:
                            current_value = int(current_value)
                        elif field_type == bool:
                            current_value = bool(current_value)
                        model_field_updates[field_name] = current_value
                    except (ValueError, TypeError) as e:
                        print(f"[save_skill_config] 字段 {field_name} 值转换失败: {e}")
            else:
                # 普通配置项，保留在 keys 中
                keys_to_keep.append(key)
        
        # 更新 config，移除模型字段
        config['keys'] = keys_to_keep
        
        # 获取第一条任务的原始配置（用于保留内置配置项）
        first_task = tasks.first()
        original_config = first_task.配置 if first_task else None
        
        # 转换为数据库存储格式
        config_to_save = _convert_from_keys_format(config, original_config)
    else:
        # 旧格式：直接保存
        config_to_save = config
    
    # 【修改】批量更新所有同 group_name 的定时任务的配置字段
    update_data = {"配置": config_to_save}
    
    # 【新增】如果有模型字段更新，一并更新
    if model_field_updates:
        update_data.update(model_field_updates)
        print(f"[save_skill_config] 同时更新模型字段: {list(model_field_updates.keys())}")
    
    update_count = tasks.update(**update_data)
    
    # 记录日志
    print(f"[save_skill_config] 已更新 {update_count} 条任务的配置，group_name={skill_name}")
    
    return JsonResponse({
        "code": 2000,
        "message": "保存成功"
    })


@require_http_methods(["GET"])
def skill_download_status(request):
    """
    查询技能下载状态
    
    根据技能名称查询"定时任务"表，判断技能是否已下载
    
    GET /base/skill/download_status?skill_name=微信自动回复
    
    Parameters:
        - skill_name: 技能名称（对应 group_name 字段）
    
    Response:
    {
        "code": 2000,
        "data": {
            "skill_name": "微信自动回复",
            "is_downloaded": true
        }
    }
    """
    skill_name = request.GET.get('skill_name')
    
    if not skill_name:
        return JsonResponse({
            "code": 4000,
            "message": "缺少 skill_name 参数"
        }, status=400)
    
    # 查询定时任务表（取最后一条）
    task = 定时任务.objects.filter(group_name=skill_name).last()
    
    is_downloaded = False
    if task and hasattr(task, '激活') and task.激活:
        is_downloaded = True
    
    return JsonResponse({
        "code": 2000,
        "data": {
            "skill_name": skill_name,
            "is_downloaded": is_downloaded
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
def install_skill(request):
    """
    安装/下载技能
    
    将技能保存到定时任务表
    
    POST /base/skill/install
    
    Request Body:
    {
        "skill_name": "微信自动回复",
        "skill_data": { ... }
    }
    
    Response:
    {
        "code": 2000,
        "message": "安装成功"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            "code": 4000,
            "message": "请求体必须是有效的JSON"
        }, status=400)
    
    skill_name = data.get('skill_name')
    user_key = data.get('user_key')
    
    if not skill_name or not user_key:
        return JsonResponse({
            "code": 4000,
            "message": "缺少必要参数"
        }, status=400)

    定时任务.从远端导入定时任务(user_key, skill_name)

    # 检查
    return JsonResponse({
        "code": 2000,
        "message": "安装成功"
    })


@csrf_exempt
@require_http_methods(["POST"])
def uninstall_skill(request):
    """
    卸载/删除技能
    
    从定时任务表中删除或禁用技能
    
    POST /base/skill/uninstall
    
    Request Body:
    {
        "skill_name": "微信自动回复"
    }
    
    Response:
    {
        "code": 2000,
        "message": "卸载成功"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            "code": 4000,
            "message": "请求体必须是有效的JSON"
        }, status=400)
    
    skill_name = data.get('skill_name')
    
    if not skill_name:
        return JsonResponse({
            "code": 4000,
            "message": "缺少 skill_name 参数"
        }, status=400)
    
    # 查询并删除或禁用
    tasks = 定时任务.objects.filter(group_name=skill_name)
    if tasks.exists():
        # 选择禁用而不是删除，保留配置
        tasks.update(激活=False)
    
    return JsonResponse({
        "code": 2000,
        "message": "卸载成功"
    })


@require_http_methods(["GET"])
def download_skills(request):
    """
    获取所有已下载的技能
    
    从定时任务表中获取所有已激活的技能（即已下载的技能）
    
    GET /base/skill/download_skills
    
    Response:
    {
        "code": 2000,
        "data": {
            "skills": ["微信自动回复", "抖音自动养号", ...]
        }
    }
    """
    try:
        # 调用定时任务模型的获取所有技能方法
        技能列表 = 定时任务.获取所有技能()
        
        # 提取技能名称列表
        skill_names = [skill.get('group_name') for skill in 技能列表 if skill.get('group_name')]
        
        return JsonResponse({
            "code": 2000,
            "data": {
                "skills": skill_names
            }
        })
    except Exception as e:
        return JsonResponse({
            "code": 5000,
            "message": f"获取已下载技能失败: {str(e)}"
        }, status=500)


# ==================== 新增：页面视图函数 ====================

def skill_square_page(request):
    """技能广场页面"""
    return render(request, 'skill_square.html')


def demand_square_page(request):
    """需求广场页面"""
    return render(request, 'demand_square.html')


def profile_page(request):
    """个人中心页面"""
    return render(request, 'profile.html')