import zoneinfo

import pandas as pd
from datetime import datetime
from django.utils import timezone  # 引入Django时区工具

def api_ret_data(data=None, default_code=2000):
    return {'code': default_code, 'msg': 'ok', 'data': data or {}}


def format_field(field):
    return None if field == "undefined" else field


# def _filter_records_by_time(data_records: list, update_time: datetime, time_key: str = '时间') -> list:
#     """
#     从数据记录列表中筛选出时间戳晚于指定update_time的记录
#
#     参数:
#         data_records: 数据记录列表，每个元素是包含时间戳的字典
#         update_time: 对比的基准时间，datetime对象（naive datetime，无时区）
#         time_key: 时间戳字段的key值，默认为'时间'
#
#     返回:
#         符合条件的记录列表
#
#     Doctest示例:
#     >>> from datetime import datetime
#     >>> # 1. 基础功能测试：使用UTC时间戳，避免时区干扰
#     >>> # 时间戳对应关系（UTC时间）：
#     >>> # 1710000000 = 2024-03-09 04:00:00
#     >>> # 1710000030 = 2024-03-09 04:00:30（基准时间）
#     >>> # 1710000060 = 2024-03-09 04:01:00（晚于基准）
#     >>> # 1709999940 = 2024-03-09 03:59:00（早于基准）
#     >>> test_records = [
#     ...     {"内容": "记录1", "时间": 1710000000},
#     ...     {"内容": "记录2", "时间": 1710000060},
#     ...     {"内容": "记录3", "时间": 1709999940}
#     ... ]
#     >>> # 强制使用UTC时区生成基准时间，避免本地时区干扰
#     >>> test_update_time = datetime.utcfromtimestamp(1710000030)
#     >>> result = filter_records_by_time(test_records, test_update_time)
#     >>> len(result)
#     1
#     >>> result[0]["内容"]
#     '记录2'
#
#     >>> # 2. 自定义time_key测试
#     >>> test_records_custom = [
#     ...     {"内容": "记录A", "时间戳": 1710000000},
#     ...     {"内容": "记录B", "时间戳": 1710000060}
#     ... ]
#     >>> result_custom = filter_records_by_time(test_records_custom, test_update_time, time_key='时间戳')
#     >>> len(result_custom)
#     1
#     >>> result_custom[0]["内容"]
#     '记录B'
#
#     >>> # 3. 边界场景：空列表输入
#     >>> filter_records_by_time([], test_update_time)
#     []
#
#     >>> # 4. 边界场景：非列表输入（如字典）
#     >>> filter_records_by_time({"错误": "数据"}, test_update_time)
#     []
#
#     >>> # 5. 边界场景：缺少指定的time_key字段
#     >>> test_records_no_key = [{"内容": "记录1"}, {"内容": "记录2"}]
#     >>> filter_records_by_time(test_records_no_key, test_update_time)
#     []
#
#     >>> # 6. 边界场景：时间字段值无效（非数字/空值）
#     >>> test_records_invalid = [
#     ...     {"内容": "记录1", "时间": "不是数字"},
#     ...     {"内容": "记录2", "时间": None},
#     ...     {"内容": "记录3", "时间": True},
#     ...     {"内容": "记录4", "时间": 1710000060}
#     ... ]
#     >>> result_invalid = filter_records_by_time(test_records_invalid, test_update_time)
#     >>> len(result_invalid)
#     1
#     >>> result_invalid[0]["内容"]
#     '记录4'
#
#     >>> # 7. 边界场景：时间戳为负数（历史时间）
#     >>> test_records_negative = [
#     ...     {"内容": "历史记录", "时间": -1000000},
#     ...     {"内容": "新记录", "时间": 1710000060}
#     ... ]
#     >>> result_negative = filter_records_by_time(test_records_negative, test_update_time)
#     >>> len(result_negative)
#     1
#
#     """
#     # 处理空列表/非列表输入
#     if not isinstance(data_records, list) or len(data_records) == 0:
#         return []
#
#     try:
#         # 转换为DataFrame（重置索引，避免索引异常）
#         df = pd.DataFrame(data_records).reset_index(drop=True)
#
#         # 检查时间key是否存在
#         if time_key not in df.columns:
#             return []
#
#         # 数据清洗：过滤掉时间字段为空/非数字/布尔值的记录
#         # 先重置索引，避免筛选后索引不连续导致的问题
#         df_clean = df[
#             df[time_key].notna() &
#             df[time_key].apply(lambda x: isinstance(x, (int, float)) and not isinstance(x, bool))
#             ].reset_index(drop=True)
#
#         # 空DataFrame直接返回
#         if df_clean.empty:
#             return []
#
#         # 关键修复：分步转换时间戳，避免时区相关的索引问题
#         # 1. 先转换为UTC时间（带时区）
#         df_clean["_converted_time_utc"] = pd.to_datetime(df_clean[time_key], unit='s', utc=True)
#         # 2. 转换为本地时区的naive datetime（移除时区信息）
#         df_clean["_converted_time"] = df_clean["_converted_time_utc"].dt.tz_convert(None)
#
#         # 基准时间转换为Timestamp（确保无时区）
#         update_time_ts = pd.Timestamp(update_time).tz_localize(None)
#
#         # 筛选符合条件的记录（使用.values避免索引依赖）
#         mask = df_clean["_converted_time"].values > update_time_ts
#         filtered_df = df_clean.loc[mask].reset_index(drop=True)
#
#         # 移除临时列，转换回字典列表
#         result = filtered_df.drop(
#             columns=["_converted_time_utc", "_converted_time"],
#             errors='ignore'
#         ).to_dict('records')
#
#         return result
#
#     except Exception as e:
#         # 捕获异常，返回空列表避免程序中断
#         print(f"筛选记录时出错: {e}")
#         return []


def filter_records_by_time(data_records: list, update_time: datetime, time_key: str = '时间') -> list:
    """
    从数据记录列表中筛选出时间戳晚于指定update_time的记录（纯列表循环实现）

    参数:
        data_records: 数据记录列表，每个元素是包含时间戳的字典
        update_time: 对比的基准时间，datetime对象（支持带时区/无时区）
        time_key: 时间戳字段的key值，默认为'时间'

    返回:
        符合条件的记录列表

    Doctest示例:
    >>> from datetime import datetime
    >>> import pytz  # 需要安装pytz: pip install pytz
    >>> # 1. 基础功能测试（带时区对比）
    >>> test_records = [
    ...     {"内容": "记录1", "时间": 1710000000},  # 2024-03-09 04:00:00 UTC
    ...     {"内容": "记录2", "时间": 1710000060},  # 2024-03-09 04:01:00 UTC
    ...     {"内容": "记录3", "时间": 1709999940}   # 2024-03-09 03:59:00 UTC
    ... ]
    >>> # 生成带时区的基准时间（模拟Django的update_time）
    >>> utc_tz = pytz.UTC
    >>> test_update_time = utc_tz.localize(datetime.utcfromtimestamp(1710000030))
    >>> result = filter_records_by_time(test_records, test_update_time)
    >>> len(result)
    1
    >>> result[0]["内容"]
    '记录2'

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
    """
    # 存储符合条件的记录
    newer_records = []

    # 基础校验：非列表或空列表直接返回
    if not isinstance(data_records, list) or len(data_records) == 0:
        return newer_records

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
            naive_utc_time = datetime.utcfromtimestamp(timestamp)
            # 步骤2：给naive时间添加UTC时区，使其成为offset-aware
            record_time = timezone.make_aware(naive_utc_time, timezone=timezone.utc)

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

    x = filter_records_by_time([{
                                "截屏": "https://file.j1.sale/api/file/tmp/2026-01-07/d223feb0-eb77-11f0-82e9-0242ac120005.jpg",
                                "回复": "回复 @💞爱财爱己໑ຼ₀26💕", "类型": "月亮正在充电回复自己视频的评论",
                                "原始": "太厉害了吧！政策给力，有想法又肯干还能得到支持，这就是诚信经营、努力付出的好结果呀，为老同学开心～",
                                "修正": "太厉害了吧！政策给力，有想法又肯干还能得到支持，这就是诚信经营、努力付出的好结果呀，为老同学开心！", "合法": True,
                                "时间": 1767756051}, {
                                "截屏": "https://file.j1.sale/api/file/tmp/2026-01-07/ec663fcc-eb77-11f0-99a5-0242ac120005.jpg",
                                "回复": "回复 @咘&訁", "类型": "月亮正在充电回复自己视频的评论",
                                "原始": "这些生活小美好也太治愈啦！和家人相伴、静心阅读，慢慢经营生活的感觉超棒～ 生活和商业一样，用心对待才会收获满满呀～",
                                "修正": "这些生活小美好也太治愈啦！和家人相伴、静心阅读，慢慢经营生活的感觉超棒～ 生活和商业一样，用心对待才会收获满满呀!", "合法": True,
                                "时间": 1767756089}],
                           datetime(2026, 1, 7, 11, 20, 35, tzinfo=zoneinfo.ZoneInfo(key='Asia/Shanghai')))
    print(x)