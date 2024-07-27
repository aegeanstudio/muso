# -*- coding: UTF-8 -*-

import functools
import inspect

from aiomysql import DictCursor, Pool, create_pool

_NAMED_POOL_DICT: dict[str, Pool] = dict()


async def init(
        *, name: str, charset: str = 'utf8mb4', pool_size: int = 16, **kwargs,
) -> None:
    if name in _NAMED_POOL_DICT:
        raise ValueError(f'Pool "{name}" already exists')
    if pool_size < 1:
        raise ValueError('Pool size should be greater than 0')
    minsize, maxsize = pool_size, pool_size
    if minsize > 4:
        minsize = 4
    _NAMED_POOL_DICT[name] = await create_pool(
        minsize=minsize, maxsize=maxsize, charset=charset, **kwargs)


async def close_all():
    for _, pool in _NAMED_POOL_DICT.items():
        pool.close()
        await pool.wait_closed()
    _NAMED_POOL_DICT.clear()


def with_mysql(*, name: str, transaction: bool = False,
               dict_cursor: bool = False):
    def decorator(f):
        argspec = inspect.getfullargspec(f)
        if all(map(lambda x: 'cursor' not in x,
                   (argspec.args, argspec.kwonlyargs))):
            raise SyntaxError('`cursor` is a required argument')

        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            pool = _NAMED_POOL_DICT.get(name)
            if not pool:
                raise SyntaxError(f'Pool {name} not found')
            if 'cursor' in kwargs:
                raise SyntaxError('`cursor` is a reserved argument')
            async with pool.acquire() as connection:
                if transaction:
                    await connection.begin()
                cursor_coro = (connection.cursor(DictCursor)
                               if dict_cursor else connection.cursor())
                try:
                    async with cursor_coro as cursor:
                        kwargs['cursor'] = cursor
                        result = await f(*args, **kwargs)
                    await connection.commit()
                except Exception as e:
                    await connection.rollback()
                    raise e
                return result

        return wrapper

    return decorator
