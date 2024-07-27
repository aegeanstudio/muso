# -*- coding: UTF-8 -*-
import dataclasses
import io
import typing
from collections import UserString

import orjson
from starlette.background import BackgroundTask
from starlette.responses import ContentStream, Response, StreamingResponse

type BaseTypeAnnotation = str | int | float | bool | None


@dataclasses.dataclass(slots=True, kw_only=True)
class _CustomDataType:
    type_class: type
    encoder: typing.Callable[[typing.Any], BaseTypeAnnotation]


_CUSTOM_DATA_TYPE_LIST = [_CustomDataType(type_class=UserString, encoder=str)]


def register_custom_data_types(
        *, type_class: type,
        encoder: typing.Callable[[typing.Any], BaseTypeAnnotation],
) -> None:
    for custom_data_type in _CUSTOM_DATA_TYPE_LIST:
        if custom_data_type.type_class == type_class:
            raise ValueError(f'Type class {type_class} already registered')
    _CUSTOM_DATA_TYPE_LIST.append(
        _CustomDataType(type_class=type_class, encoder=encoder))


def orjson_dumps_default(obj):
    for custom_data_type in _CUSTOM_DATA_TYPE_LIST:
        if isinstance(obj, custom_data_type.type_class):
            return custom_data_type.encoder(obj)
    raise TypeError(f'Object of type {type(obj)} is not JSON serializable')


class ORJSONResponse(Response):
    media_type = 'application/json'

    def render(self, content: typing.Any) -> bytes:
        return orjson.dumps(
            content, option=orjson.OPT_STRICT_INTEGER,
            default=orjson_dumps_default)


class StreamResponse(StreamingResponse):
    pass


async def _make_bytes_generator(
        *, content: bytes, chunk_size: int,
) -> typing.AsyncGenerator[bytes, None]:
    length = len(content)
    seek = 0
    while seek < length:
        yield content[seek:seek + chunk_size]
        seek += chunk_size


async def _make_bio_generator(
        *, content: io.BytesIO, chunk_size: int, content_close: bool,
) -> typing.AsyncGenerator[bytes, None]:
    content.seek(0)
    while True:
        chunk = content.read(chunk_size)
        if not chunk:
            break
        yield chunk
    if content_close:
        content.close()


class FileBytesResponse(StreamingResponse):

    def __init__(
            self,
            content: ContentStream | bytes,
            status_code: int = 200,
            headers: typing.Mapping[str, str] | None = None,
            media_type: str | None = None,
            background: BackgroundTask | None = None,
            chunk_size: int = 1024 * 1024,
            content_close: bool = True,
    ) -> None:
        super().__init__(
            content=content, status_code=status_code, headers=headers,
            media_type=media_type, background=background)
        if isinstance(content, bytes):
            self.headers['Content-Length'] = str(len(content))
            self.body_iterator = _make_bytes_generator(
                content=content, chunk_size=chunk_size)
        if isinstance(content, io.BytesIO):
            content.seek(0, io.SEEK_END)
            self.headers['Content-Length'] = str(content.tell())
            self.body_iterator = _make_bio_generator(
                content=content, chunk_size=chunk_size,
                content_close=content_close)
