# -*- coding: UTF-8 -*-

import asyncio
import functools
import inspect
import traceback
import typing
from collections import UserString

from marshmallow import Schema, fields
from marshmallow.exceptions import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from muso.auth import AuthBase
from muso.errors import BizError
from muso.request import MusoRequest
from muso.response import ORJSONResponse
from muso.schema import BaseSchema, EmptyResponseSchema


class RouteGroup:

    def __init__(self, *, prefix: str, tag: str, description: str = ''):
        self.prefix: str = prefix
        self.tag: str = tag
        self.description: str = description
        self.route_list: list[Route] = []

    def _register(
            self, *, uri: str, method: str, headers: Schema | None,
            query_args: Schema | None, form_data: Schema | None,
            json_body: Schema | None, response: Schema | None,
            response_wrap: bool, auth: AuthBase | None,
            is_streaming_response: bool, summary: str | UserString,
            **kwargs,
    ) -> typing.Callable:

        def decorator(endpoint_function):
            _parameters = inspect.signature(obj=endpoint_function).parameters
            _contains_request = bool('request' in _parameters.keys())
            _contains_current_user = bool('current_user' in _parameters.keys())
            _is_coroutine_function = asyncio.iscoroutinefunction(
                endpoint_function)
            if response:
                if response_wrap:
                    _wrapped_response_schema_cls = BaseSchema.from_dict(
                        fields=dict(
                            code=fields.Integer(required=True),
                            msg=fields.String(required=True, allow_none=True),
                            data=fields.Nested(
                                nested=response, allow_none=True),
                        ),
                        name=f'Wrapped{response.__class__.__name__}',
                    )
                    _wrapped_response = _wrapped_response_schema_cls()
                else:
                    _wrapped_response = response
            else:
                _wrapped_response = EmptyResponseSchema()

            @functools.wraps(endpoint_function)
            async def wrapper(request: StarletteRequest):
                muso_request = MusoRequest(
                    starlette_request=request,
                    query_args_schema=query_args,
                    form_data_schema=form_data,
                    json_body_schema=json_body,
                )
                arguments = dict()
                if _contains_request:
                    arguments['request'] = muso_request

                try:
                    auth_to_current_user = None
                    if auth:
                        auth_to_current_user = auth(request=muso_request)
                        if asyncio.iscoroutine(auth_to_current_user):
                            auth_to_current_user = await auth_to_current_user
                    if _contains_current_user:
                        arguments['current_user'] = auth_to_current_user

                    if _is_coroutine_function:
                        result = await endpoint_function(**arguments)
                    else:
                        result = await run_in_threadpool(
                            func=endpoint_function, **arguments)
                except BizError as e:
                    return ORJSONResponse(
                        content=dict(code=e.code, msg=e.msg, data=None),
                        status_code=e.http_status,
                    )
                except ValidationError:
                    return ORJSONResponse(
                        content=dict(
                            code=1001,
                            msg='Data Structure Validation Error',
                            data=None,
                        ),
                        status_code=400,
                    )
                except:  # noqa
                    traceback.print_exc()
                    return ORJSONResponse(
                        content=dict(
                            code=1000,
                            msg='Internal Server Error',
                            data=None,
                        ),
                        status_code=500,
                    )
                if isinstance(result, StarletteResponse):
                    return result
                if not response_wrap:
                    return ORJSONResponse(
                        content=_wrapped_response.dump(obj=result))
                return ORJSONResponse(
                    content=_wrapped_response.dump(
                        obj=dict(code=0, msg='', data=result)))

            self.route_list.append(
                Route(
                    path=f'{self.prefix}{uri}', method=method,
                    endpoint=wrapper,
                    headers_schema=headers, query_args_schema=query_args,
                    form_data_schema=form_data, json_body_schema=json_body,
                    response_schema=_wrapped_response,
                    auth=auth,
                    is_streaming_response=is_streaming_response,
                    summary=summary,
                    **kwargs,
                ),
            )
            return wrapper

        return decorator

    def get(
            self, *, uri: str,
            headers: Schema | None = None,
            query_args: Schema | None = None,
            response: Schema | None = None,
            response_wrap: bool = True,
            auth: AuthBase | None = None,
            is_streaming_response: bool = False,
            summary: str | UserString = '',
            **kwargs,
    ) -> typing.Callable:
        return self._register(
            uri=uri, method='GET', headers=headers, query_args=query_args,
            form_data=None, json_body=None, response=response,
            response_wrap=response_wrap, auth=auth,
            is_streaming_response=is_streaming_response, summary=summary,
            **kwargs)

    def post(
            self, *, uri: str,
            headers: Schema | None = None,
            query_args: Schema | None = None,
            form_data: Schema | None = None,
            json_body: Schema | None = None,
            response: Schema | None = None,
            response_wrap: bool = True,
            auth: AuthBase | None = None,
            is_streaming_response: bool = False,
            summary: str | UserString = '',
            **kwargs,
    ) -> typing.Callable:
        if form_data and json_body:
            raise SyntaxError(
                'form_data and json_body cannot be used together')
        return self._register(
            uri=uri, method='POST', headers=headers, query_args=query_args,
            form_data=form_data, json_body=json_body, response=response,
            response_wrap=response_wrap, auth=auth,
            is_streaming_response=is_streaming_response, summary=summary,
            **kwargs)

    def put(
            self, *, uri: str,
            headers: Schema | None = None,
            query_args: Schema | None = None,
            form_data: Schema | None = None,
            json_body: Schema | None = None,
            response: Schema | None = None,
            response_wrap: bool = True,
            auth: AuthBase | None = None,
            is_streaming_response: bool = False,
            summary: str | UserString = '',
            **kwargs,
    ) -> typing.Callable:
        if form_data and json_body:
            raise SyntaxError(
                'form_data and json_body cannot be used together')
        return self._register(
            uri=uri, method='PUT', headers=headers, query_args=query_args,
            form_data=form_data, json_body=json_body, response=response,
            response_wrap=response_wrap, auth=auth,
            is_streaming_response=is_streaming_response,
            summary=summary, **kwargs)

    def delete(
            self, *, uri: str,
            headers: Schema | None = None,
            query_args: Schema | None = None,
            response: Schema | None = None,
            response_wrap: bool = True,
            auth: AuthBase | None = None,
            is_streaming_response: bool = False,
            summary: str | UserString = '',
            **kwargs,
    ) -> typing.Callable:
        return self._register(
            uri=uri, method='DELETE', headers=headers, query_args=query_args,
            form_data=None, json_body=None, response=response,
            response_wrap=response_wrap, auth=auth,
            is_streaming_response=is_streaming_response, summary=summary,
            **kwargs,
        )


class Route:

    def __init__(
            self, *, path: str, method: str, endpoint: typing.Callable,
            headers_schema: Schema,
            query_args_schema: Schema | None,
            form_data_schema: Schema | None,
            json_body_schema: Schema | None,
            response_schema: Schema | None,
            auth: AuthBase | None,
            is_streaming_response: bool = False,
            summary: str | UserString,
            **kwargs,
    ):
        self.path = path
        self.method = method
        self.endpoint = endpoint
        self.headers_schema = headers_schema
        self.query_args_schema = query_args_schema
        self.form_data_schema = form_data_schema
        self.json_body_schema = json_body_schema
        self.response_schema = response_schema
        self.auth = auth
        self.is_streaming_response = is_streaming_response
        self.summary = summary
        self.kwargs = kwargs or dict()

    def __getattr__(self, item):
        return self.kwargs.get(item, None)
