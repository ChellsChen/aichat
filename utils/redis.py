from django.core.cache import cache


class RedisUtil:
    def set(self, key, value, timeout=None):
        """
        设置键值对
        :param key: 键
        :param value: 值
        :param timeout: 过期时间（秒）
        :return: 成功返回True，失败返回False
        """
        return cache.set(key, value, timeout=timeout)

    def get(self, key):
        """
        获取键对应的值
        :param key: 键
        :return: 值或None
        """
        return cache.get(key)

    def delete(self, *keys):
        """
        删除一个或多个键
        :param keys: 键列表
        :return: 删除的键的数量
        """
        return cache.delete(*keys)

    def exists(self, key):
        """
        检查键是否存在
        :param key: 键
        :return: 存在返回True，不存在返回False
        """
        return cache.has_key(key)

    def keys(self, pattern='*'):
        """
        获取所有符合给定模式的键
        :param pattern: 模式
        :return: 键列表
        """
        # 注意：django-redis不直接支持keys命令，可以使用scan_iter
        return cache._client.scan_iter(pattern)

    def hset(self, name, key, value):
        """
        设置哈希表中的字段值
        :param name: 哈希表名
        :param key: 字段名
        :param value: 字段值
        :return: 成功返回True，如果字段已经存在并被更新则返回False
        """
        return cache.hset(name, key, value)

    def hget(self, name, key):
        """
        获取哈希表中的字段值
        :param name: 哈希表名
        :param key: 字段名
        :return: 字段值或None
        """
        return cache.hget(name, key)

    def hgetall(self, name):
        """
        获取哈希表中的所有字段和值
        :param name: 哈希表名
        :return: 字典
        """
        return cache.hgetall(name)

    def lpush(self, key, *values):
        """
        将一个或多个值插入到列表头部
        :param key: 列表名
        :param values: 值列表
        :return: 列表长度
        """
        return cache.lpush(key, *values)

    def lpop(self, key):
        """
        移除并返回列表的第一个元素
        :param key: 列表名
        :return: 元素或None
        """
        return cache.lpop(key)

    def rpush(self, key, *values):
        """
        将一个或多个值插入到列表尾部
        :param key: 列表名
        :param values: 值列表
        :return: 列表长度
        """
        return cache.rpush(key, *values)

    def rpop(self, key):
        """
        移除并返回列表的最后一个元素
        :param key: 列表名
        :return: 元素或None
        """
        return cache.rpop(key)

    def sadd(self, key, *members):
        """
        向集合添加一个或多个成员
        :param key: 集合名
        :param members: 成员列表
        :return: 添加成功的成员数量
        """
        return cache.sadd(key, *members)

    def smembers(self, key):
        """
        获取集合中的所有成员
        :param key: 集合名
        :return: 成员集合
        """
        return cache.smembers(key)

    def zadd(self, key, mapping):
        """
        向有序集合添加一个或多个成员
        :param key: 有序集合名
        :param mapping: 字典，键为成员，值为分数
        :return: 添加成功的成员数量
        """
        return cache.zadd(key, mapping)

    def zrange(self, key, start, end, withscores=False):
        """
        获取有序集合中指定范围的成员
        :param key: 有序集合名
        :param start: 起始索引
        :param end: 结束索引
        :param withscores: 是否返回分数
        :return: 成员列表或成员和分数的元组列表
        """
        return cache.zrange(key, start, end, withscores=withscores)

    def zscore(self, key, member):
        """
        获取有序集合中成员的分数
        :param key: 有序集合名
        :param member: 成员
        :return: 分数或None
        """
        return cache.zscore(key, member)
