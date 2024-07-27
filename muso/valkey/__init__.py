# -*- coding: UTF-8 -*-
import functools
import inspect

from valkey.asyncio import BlockingConnectionPool, StrictValkey

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
    _NAMED_POOL_DICT[name] = pool


async def close_all():
    for _, pool in _NAMED_POOL_DICT.items():
        await pool.aclose()
    _NAMED_POOL_DICT.clear()


type ValkeyAnnotation = StrictValkey


def with_valkey(*, name: str):
    def decorator(func):
        argspec = inspect.getfullargspec(func)
        if all(map(lambda x: 'valkey' not in x,
                   (argspec.args, argspec.kwonlyargs))):
            raise SyntaxError('`valkey` is a required argument')

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            pool = _NAMED_POOL_DICT.get(name)
            if not pool:
                raise SyntaxError(f'Pool {name} not found')
            if 'valkey' in kwargs:
                raise SyntaxError('`valkey` is a reserved argument')
            async with StrictValkey(connection_pool=pool) as valkey:
                kwargs['valkey'] = valkey
                result = await func(*args, **kwargs)
            return result

        return wrapper

    return decorator
