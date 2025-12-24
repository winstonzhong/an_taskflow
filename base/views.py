from django.http import JsonResponse
from rest_framework.views import APIView

from base.models import 定时任务
from commons.constants import API_RET_CODE_PARAMS_ERROR, API_RET_CODE_RECORD_NOT_EXISTED_ERROR
from commons.exceptions import RecordNotExistedError
from commons.helper_cache import 获取页面数据, 插入操作数据, 更新知识库
from commons.utils import api_ret_data, format_field
from tool_img import bin_to_base64url


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
