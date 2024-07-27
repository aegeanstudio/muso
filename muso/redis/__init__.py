# -*- coding: UTF-8 -*-
import functools
import inspect

from redis.asyncio import BlockingConnectionPool, StrictRedis

_NAMED_POOL_DICT: dict[str, BlockingConnectionPool] = dict()


async def init(
        *, name: str, url: str, max_connections: int = 16, timeout: int = 10,
) -> None:
    if name in _NAMED_POOL_DICT:
        raise ValueError(f'Pool "{name}" already exists')
    if max_connections < 1:
        raise ValueError('Pool size should be greater than 0')
    pool = BlockingConnectionPool.from_url(
        url=url, max_connections=max_connections, timeout=timeout, protocol=3)
    connection = await pool.get_connection('')
    await pool.release(connection)
    _NAMED_POOL_DICT[name] = pool


async def close_all():
    for _, pool in _NAMED_POOL_DICT.items():
        await pool.aclose()
    _NAMED_POOL_DICT.clear()


type RedisAnnotation = StrictRedis


def with_redis(*, name: str):
    def decorator(func):
        argspec = inspect.getfullargspec(func)
        if all(map(lambda x: 'redis' not in x,
                   (argspec.args, argspec.kwonlyargs))):
            raise SyntaxError('`redis` is a required argument')

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            pool = _NAMED_POOL_DICT.get(name)
            if not pool:
                raise SyntaxError(f'Pool {name} not found')
            if 'redis' in kwargs:
                raise SyntaxError('`redis` is a reserved argument')
            async with StrictRedis(connection_pool=pool) as redis:
                kwargs['redis'] = redis
                result = await func(*args, **kwargs)
            return result

        return wrapper

    return decorator
