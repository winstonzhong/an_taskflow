
def api_ret_data(data=None, default_code=2000):
    return {'code': default_code, 'msg': 'ok', 'data': data or {}}


def format_field(field):
    return None if field == "undefined" else field