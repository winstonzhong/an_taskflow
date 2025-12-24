from .constants import *

class MsgException(Exception):
    default_msg = '{}'

    def __init__(self, msg=''):
        self.msg = self.default_msg.format(msg)


class MsgCodeException(MsgException):
    code = API_RET_CODE_ERROR

    def __init__(self, msg='', code=None):
        super(MsgCodeException, self).__init__(msg=msg)
        self.code = code or self.code


class ParamsError(MsgCodeException):
    code = API_RET_CODE_PARAMS_ERROR

    default_msg = '参数错误:{}'


class RecordNotExistedError(MsgCodeException):
    code = API_RET_CODE_RECORD_NOT_EXISTED_ERROR

    default_msg = '数据记录不存在:{}'

