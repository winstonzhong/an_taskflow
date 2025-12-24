from django.core.cache import cache


页面数据_key = 'page_data'
操作_key = 'operation_data'
知识库_key = 'knowledge_base'
CACHE_TIMEOUT = 10



def cache_pop(key, default=None):
    """
    模拟缓存的pop操作（非原子）
    :param key: 缓存键
    :param default: 缓存不存在时返回的默认值
    :return: 缓存对应的值（不存在返回default）
    """
    # 1. 获取缓存值
    value = cache.get(key, default)
    # 2. 删除缓存键
    if value is not default:  # 仅当缓存存在时才删除
        cache.delete(key)
    return value


def 获取页面数据():
    return cache.get(页面数据_key)
    # return cache_pop(页面数据_key, dict())


def 设置页面数据(data):
    cache.set(页面数据_key, data, CACHE_TIMEOUT)


def 获取操作列表():
    return cache.get(操作_key) or dict()


def 插入操作数据(data):
    cache.set(操作_key, data)


def 更新知识库(bin_data):
    cache.set(知识库_key, bin_data)


def 获取知识库():
    return cache.get(知识库_key)