import zoneinfo

import pandas as pd
import datetime
from django.utils import timezone  # 引入Django时区工具

def api_ret_data(data=None, default_code=2000):
    return {'code': default_code, 'msg': 'ok', 'data': data or {}}


def format_field(field):
    return None if field == "undefined" else field


def filter_records_by_time(data_records: list, update_time: datetime.datetime, time_key: str = '时间') -> list:
    """
    从数据记录列表中筛选出时间戳晚于指定update_time的记录（纯列表循环实现）

    参数:
        data_records: 数据记录列表，每个元素是包含时间戳的字典
        update_time: 对比的基准时间，datetime对象（支持带时区/无时区）
        time_key: 时间戳字段的key值，默认为'时间'

    返回:
        符合条件的记录列表

    Doctest示例:
    >>> import pytz  # 需要安装pytz: pip install pytz
    >>> # 1. 基础功能测试（带时区对比）
    >>> test_records = [
    ...     {"内容": "记录1", "时间": 1710000000},  # 2024-03-09 04:00:00 UTC
    ...     {"内容": "记录2", "时间": 1710000060},  # 2024-03-09 04:01:00 UTC
    ...     {"内容": "记录3", "时间": 1709999940}   # 2024-03-09 03:59:00 UTC
    ... ]
    >>> # 生成带时区的基准时间（模拟Django的update_time）
    >>> utc_tz = pytz.UTC
    >>> test_update_time = utc_tz.localize(datetime.datetime.utcfromtimestamp(1710000030))
    >>> result = filter_records_by_time(test_records, test_update_time)
    >>> len(result)
    1
    >>> result[0]["内容"]
    '记录2'

    >>> result = filter_records_by_time(test_records, None)
    >>> len(result)
    3
    >>> # 2. 自定义time_key测试
    >>> test_records_custom = [
    ...     {"内容": "记录A", "时间戳": 1710000000},
    ...     {"内容": "记录B", "时间戳": 1710000060}
    ... ]
    >>> result_custom = filter_records_by_time(test_records_custom, test_update_time, time_key='时间戳')
    >>> len(result_custom)
    1
    >>> result_custom[0]["内容"]
    '记录B'

    >>> # 3. 边界场景测试
    >>> filter_records_by_time([], test_update_time)
    []
    >>> filter_records_by_time({"错误": "数据"}, test_update_time)
    []
    >>> filter_records_by_time([{"内容": "记录1"}], test_update_time)
    []

    >>> data_list = [{'原始 评论': '这种串门团购分享的创作态度很值得学习，🌈大！之前拍这类同城内容，完播率慢慢涨到四成出头，互动也比之前热闹不少，越做越有感觉～', '修正评论': '这种串门 团购分享的创作态度很值得学习，🙌大！之前拍这类同城内容，完播率慢慢涨到四成出头，互动也比之前热闹不少，越做越有感觉。', '合法': True, '时间': 1768921874.8352716}]
    >>> filter_records_by_time(data_list, datetime.datetime(2026, 1, 21, 3, 2, 0, 85747, tzinfo=datetime.timezone.utc))
    []
    """
    # 存储符合条件的记录
    newer_records = []

    # print(type(update_time))

    # 基础校验：非列表或空列表直接返回
    if not isinstance(data_records, list) or len(data_records) == 0:
        return newer_records

    if not update_time:
        return data_records

    # 遍历每条记录
    for record in data_records:
        try:
            # 校验记录是否为字典，且包含指定的时间key
            if not isinstance(record, dict) or time_key not in record:
                continue

            # 获取时间戳并校验类型
            timestamp = record[time_key]
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
                continue  # 排除布尔值（True=1, False=0）

            # 核心修复：将时间戳转换为带UTC时区的datetime对象
            # 步骤1：生成UTC的naive datetime
            naive_utc_time = datetime.datetime.utcfromtimestamp(timestamp)
            # 步骤2：给naive时间添加UTC时区，使其成为offset-aware
            record_time = timezone.make_aware(naive_utc_time, timezone=datetime.timezone.utc)

            # 现在record_time和update_time都是offset-aware，可以安全对比
            if record_time > update_time:
                newer_records.append(record.copy())  # 拷贝避免原数据被修改

        except (ValueError, TypeError, OverflowError) as e:
            # 捕获时间戳转换异常（如负数、超大数、非数字等）
            print(f"处理单条记录出错: {e}, 记录内容: {record}")
            continue

    return newer_records




if __name__ == "__main__":
    import doctest
    # 运行单元测试，-v参数显示详细结果
    print(doctest.testmod(verbose=False, report=False))

    # x = filter_records_by_time([{
    #                             "截屏": "https://file.j1.sale/api/file/tmp/2026-01-07/d223feb0-eb77-11f0-82e9-0242ac120005.jpg",
    #                             "回复": "回复 @💞爱财爱己໑ຼ₀26💕", "类型": "月亮正在充电回复自己视频的评论",
    #                             "原始": "太厉害了吧！政策给力，有想法又肯干还能得到支持，这就是诚信经营、努力付出的好结果呀，为老同学开心～",
    #                             "修正": "太厉害了吧！政策给力，有想法又肯干还能得到支持，这就是诚信经营、努力付出的好结果呀，为老同学开心！", "合法": True,
    #                             "时间": 1767756051}, {
    #                             "截屏": "https://file.j1.sale/api/file/tmp/2026-01-07/ec663fcc-eb77-11f0-99a5-0242ac120005.jpg",
    #                             "回复": "回复 @咘&訁", "类型": "月亮正在充电回复自己视频的评论",
    #                             "原始": "这些生活小美好也太治愈啦！和家人相伴、静心阅读，慢慢经营生活的感觉超棒～ 生活和商业一样，用心对待才会收获满满呀～",
    #                             "修正": "这些生活小美好也太治愈啦！和家人相伴、静心阅读，慢慢经营生活的感觉超棒～ 生活和商业一样，用心对待才会收获满满呀!", "合法": True,
    #                             "时间": 1767756089}],
    #                        datetime(2026, 1, 7, 11, 20, 35, tzinfo=zoneinfo.ZoneInfo(key='Asia/Shanghai')))
    # print(x)