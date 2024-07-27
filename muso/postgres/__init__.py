# -*- coding: UTF-8 -*-

import abc
import dataclasses
import functools
import inspect
import typing

import orjson
from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import Row
from psycopg.sql import SQL
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool

set_json_loads(orjson.loads)
set_json_dumps(orjson.dumps)

_NAMED_POOL_DICT: dict[str, AsyncConnectionPool] = dict()

type ConfigureFunc = typing.Callable[
    [AsyncConnection], typing.Awaitable | None]


async def init(
        *, name: str, dsn: str, pool_size: int = 16, open_timeout: int = 15,
        configure_funcs: typing.Sequence[ConfigureFunc] = None,
) -> None:
    if name in _NAMED_POOL_DICT:
        raise ValueError(f'Pool "{name}" already exists')
    if pool_size < 1:
        raise ValueError('Pool size should be greater than 0')
    minsize, maxsize = pool_size, pool_size
    if minsize > 4:
        minsize = 4
    kwargs = dict(autocommit=False)
    init_kwargs = dict()
    if configure_funcs:
        async def _configure(conn: AsyncConnection):
            for func in configure_funcs:
                if inspect.iscoroutinefunction(func):
                    await func(conn)
                else:
                    func(conn)

        init_kwargs['configure'] = _configure
    pool = AsyncConnectionPool(
        conninfo=dsn, min_size=minsize, max_size=maxsize, open=False,
        name=name, kwargs=kwargs, **init_kwargs)
    await pool.open(wait=True, timeout=open_timeout)
    _NAMED_POOL_DICT[name] = pool


async def close_all():
    for _, pool in _NAMED_POOL_DICT.items():
        await pool.close()
    _NAMED_POOL_DICT.clear()


def with_postgres(*, name: str, transaction: bool = False):
    def wrapper(func):
        argspec = inspect.getfullargspec(func)
        if all(map(lambda x: 'cursor' not in x,
                   (argspec.args, argspec.kwonlyargs))):
            raise SyntaxError('`cursor` is a required argument')

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            if name not in _NAMED_POOL_DICT:
                raise SyntaxError(f'Pool "{name}" not found')
            if 'cursor' in kwargs:
                raise SyntaxError('`cursor` is a reserved argument')
            async with _NAMED_POOL_DICT[name].connection() as conn:
                async with conn.cursor() as cursor:
                    kwargs['cursor'] = cursor
                    if transaction:
                        async with conn.transaction():
                            result = await func(*args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
            return result

        return wrapped

    return wrapper


class MusoSQLHelper:

    def __init__(self, base_model: type | None = None):
        try:
            assert dataclasses.is_dataclass(base_model) or base_model is None
        except AssertionError:
            raise SyntaxError(
                f'Base model "{base_model}" should be a dataclass or None')
        self._base_model = base_model

    def _gen_fields(self, dataclass: type) -> tuple[list[str], list[str]]:
        if self._base_model and issubclass(dataclass, self._base_model):
            default_fields = [
                i.strip('_')
                for i in inspect.get_annotations(self._base_model).keys()]
        else:
            default_fields = list()
        custom_fields = [
            i.strip('_') for i in inspect.get_annotations(dataclass).keys()]
        return default_fields, custom_fields

    def gen_select_base(self, *, dataclass: type, table_name: str) -> str:
        default_fields, custom_fields = self._gen_fields(dataclass)
        return (f'SELECT {", ".join(default_fields + custom_fields)} '
                f'FROM {table_name}')

    def gen_get(self, *, dataclass: type, table_name: str) -> SQL:
        default_fields, custom_fields = self._gen_fields(dataclass)
        return self.make_sql(sql_str=(
            f'SELECT {", ".join(default_fields + custom_fields)} '
            f'FROM {table_name} WHERE id=%s'))

    def gen_insert(self, *, dataclass: type, table_name: str) -> SQL:
        _, custom_fields = self._gen_fields(dataclass)
        return self.make_sql(sql_str=(
            f'INSERT INTO {table_name} ({", ".join(custom_fields)}) '
            f'VALUES ({", ".join(["%s"] * len(custom_fields))})'))

    def gen_insert_returning(
            self, *, dataclass: type, table_name: str) -> SQL:
        default_fields, custom_fields = self._gen_fields(dataclass)
        return self.make_sql(sql_str=(
            f'INSERT INTO {table_name} ({", ".join(custom_fields)}) '
            f'VALUES ({", ".join(["%s"] * len(custom_fields))}) '
            f'RETURNING {", ".join(default_fields + custom_fields)}'))

    def gen_remove(self, *, table_name: str) -> SQL:
        return self.make_sql(sql_str=(
            f'UPDATE {table_name} SET removed=%s, updated_at=NOW() '
            f'WHERE id=%s AND removed=%s'))

    @staticmethod
    def make_sql(*, sql_str: str) -> SQL:
        return SQL(sql_str.strip())     # noqa


@dataclasses.dataclass(slots=True, kw_only=True)
class BaseInsertModel(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def as_sql_params(self) -> tuple:
        ...


type DefaultCursorAnnotation = AsyncCursor[AsyncConnection['Row'], 'Row']


class BaseDataFetcher[_T](metaclass=abc.ABCMeta):
    _MODEL_CLASS: type[_T]

    _TABLE_NAME: str
    _SELECT_BASE: str

    _sql_get: SQL

    @classmethod
    async def get(
            cls, *, cursor: DefaultCursorAnnotation, id_: int,
    ) -> _T | None:
        await cursor.execute(query=cls._sql_get, params=(id_,))
        result: Row | None = await cursor.fetchone()
        return cls._MODEL_CLASS(*result) if result else None

    _sql_remove: SQL

    @classmethod
    async def remove(
            cls, *, cursor: DefaultCursorAnnotation, id_: int,
    ) -> None:
        await cursor.execute(query=cls._sql_remove, params=(True, id_, False))
