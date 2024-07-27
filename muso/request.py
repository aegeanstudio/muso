# -*- coding: UTF-8 -*-

import orjson
from marshmallow import Schema
from starlette.requests import Request as StarletteRequest


class MusoRequest:

    def __init__(
            self,
            starlette_request: StarletteRequest,
            query_args_schema: Schema | None = None,
            form_data_schema: Schema | None = None,
            json_body_schema: Schema | None = None,
    ):
        self._starlette_request = starlette_request

        self._query_args_schema: Schema | None = query_args_schema
        self._form_data_schema: Schema | None = form_data_schema
        self._json_body_schema: Schema | None = json_body_schema

        self._cached_query_args: dict | None = None
        self._cached_form_data: dict | None = None
        self._cached_json_body: dict | None = None

    async def query_args(self) -> dict:
        if self._cached_query_args is None:
            self._cached_query_args = self._query_args_schema.load(
                self._starlette_request.query_params) or dict()
        return self._cached_query_args

    async def form_data(self) -> dict:
        if self._cached_form_data is None:
            form_data = await self._starlette_request.form()
            self._cached_form_data = self._form_data_schema.load(
                form_data) or dict()
        return self._cached_form_data

    async def json_body(self) -> dict:
        if not hasattr(self._starlette_request, '_json'):
            body = await self._starlette_request.body()
            json_result = orjson.loads(body)
            self._starlette_request._json = json_result    # noqa
            self._cached_json_body = self._json_body_schema.load(json_result)
        return self._cached_json_body

    def __getattr__(self, item):
        return getattr(self._starlette_request, item)
