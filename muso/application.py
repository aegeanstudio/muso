# -*- coding: UTF-8 -*-
import typing

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from starlette.datastructures import State, URLPath
from starlette.middleware import Middleware, P, _MiddlewareFactory  # noqa
from starlette.middleware.cors import ALL_METHODS, CORSMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Router
from starlette.types import ASGIApp, ExceptionHandler, Receive, Scope, Send

from muso.response import ORJSONResponse
from muso.route import RouteGroup
from muso.schema import StarletteFileField


class Muso:

    def __init__(
            self, *, name: str, version: str, description: str,
            debug: bool = False, openapi: bool = True,
    ) -> None:
        self.name = name
        self.version = version
        self.description = description
        self.debug = debug
        self.openapi = openapi
        self.state = State()
        self.on_startup_func_list: list[typing.Callable[[], None]] = []
        self.on_shutdown_func_list: list[typing.Callable[[], None]] = []
        self.route_group_list: list[RouteGroup] = []
        self.router: Router | None = None
        self.exception_handlers: dict[typing.Any, ExceptionHandler] = dict()
        self.user_middleware: list[Middleware] = []
        self.plugins: list[typing.Callable[[Muso], None]] = []
        self.middleware_stack: ASGIApp | None = None

    def add_route_group(self, route_group: RouteGroup) -> None:
        if self.middleware_stack is not None:
            raise RuntimeError(
                'Cannot add route group after an application has started')
        self.route_group_list.append(route_group)

    def _apispec(self):
        marshmallow_plugin = MarshmallowPlugin()
        spec = APISpec(
            title=self.name, version=self.version, openapi_version='3.1.0',
            plugins=[marshmallow_plugin],
            info=dict(description=self.description))
        marshmallow_plugin.converter.add_attribute_function(
            func=_file_field_to_properties)
        security_schemes = spec.components.security_schemes

        for route_group in self.route_group_list:
            spec.tag(tag=dict(name=route_group.tag,
                              description=route_group.description))
            for route in route_group.route_list:
                if route.auth:
                    for auth_mark in route.auth.auth_marks:
                        if auth_mark.key not in security_schemes:
                            spec.components.security_scheme(
                                component_id=auth_mark.key,
                                component=auth_mark.as_dict)

                method = route.method.lower()
                operations = {route.method.lower(): dict(
                    tags=[route_group.tag],
                    summary=route.summary,
                    description=(route.endpoint.__doc__ or '').strip(),
                )}
                if route.auth:
                    operations[method]['security'] = [
                        {auth_mark.key: []}
                        for auth_mark in route.auth.auth_marks]
                if route.query_args_schema:
                    operations[method]['parameters'] = [
                        {'in': 'query', 'schema': route.query_args_schema}]
                if route.form_data_schema:
                    fds = route.form_data_schema
                    operations[method]['requestBody'] = dict(content=dict())
                    exist_file_upload = any(
                        isinstance(field, StarletteFileField)
                        for field in fds.fields.values())
                    if exist_file_upload:
                        operations[method]['requestBody']['content'] = {
                            'multipart/form-data': dict(
                                schema=fds,
                                # encoding={
                                #     field.data_key: {
                                #         'contentType': ', '.join(
                                #             field.content_type_list)}
                                #     for field in fds.fields.values()
                                #     if isinstance(field, StarletteFileField)}
                            )}
                    else:
                        operations[method]['requestBody']['content'] = {
                            'application/x-www-form-urlencoded': dict(
                                schema=route.form_data_schema),
                        }
                if route.json_body_schema:
                    operations[method]['requestBody'] = dict(
                        content={'application/json': dict(
                            schema=route.json_body_schema)})
                if route.is_streaming_response:
                    pass
                else:
                    if not route.response_schema:
                        data_spec = dict(
                            example=dict(code=0, msg='', data=None))
                    else:
                        data_spec = dict(schema=route.response_schema)

                    operations[method]['responses'] = {
                        200: dict(content={'application/json': data_spec})}

                spec.path(path=route.path, operations=operations)

        self.router.add_route(
            path='/openapi.json',
            endpoint=lambda _: ORJSONResponse(content=spec.to_dict()),
            methods=['GET'])

    def build_middleware_stack(self) -> ASGIApp:
        self.router = Router(on_startup=self.on_startup_func_list,
                             on_shutdown=self.on_shutdown_func_list)
        for route_group in self.route_group_list:
            for route in route_group.route_list:
                self.router.add_route(
                    path=route.path, endpoint=route.endpoint,
                    methods=[route.method])

        if self.openapi:
            self._apispec()

        error_handler = None
        exception_handlers: dict[
            typing.Any, typing.Callable[[Request, Exception], Response],
        ] = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        contains_cors = False
        for item in self.user_middleware:
            if isinstance(item, CORSMiddleware):
                contains_cors = True
                break
        if not contains_cors and self.debug:
            cors_middleware = Middleware(
                CORSMiddleware, allow_origins=['*'], allow_methods=ALL_METHODS,
                allow_headers=['*'])
            self.user_middleware.insert(0, cors_middleware)

        middleware = (
                [Middleware(ServerErrorMiddleware, handler=error_handler,
                            # noqa
                            debug=self.debug)] +
                self.user_middleware +
                [Middleware(ExceptionMiddleware, handlers=exception_handlers,
                            # noqa
                            debug=self.debug)])

        if self.plugins:
            for plugin in self.plugins:
                plugin(self)

        app = self.router
        for cls, args, kwargs in reversed(middleware):
            app = cls(app=app, *args, **kwargs)     # noqa
        return app

    @property
    def routes(self) -> list[BaseRoute]:
        return self.router.routes

    def url_path_for(self, name: str, **path_params: typing.Any) -> URLPath:
        return self.router.url_path_for(name, **path_params)

    async def __call__(self, scope: Scope, receive: Receive,
                       send: Send) -> None:
        scope['app'] = self
        if self.middleware_stack is None:
            self.middleware_stack = self.build_middleware_stack()
        await self.middleware_stack(scope, receive, send)

    def mount(self, path: str, app: ASGIApp, name: str | None = None) -> None:
        self.router.mount(path, app=app, name=name)  # pragma: no cover

    def host(self, host: str, app: ASGIApp, name: str | None = None) -> None:
        self.router.host(host, app=app, name=name)  # pragma: no cover

    def exception_handler(
            self, exc_class_or_status_code: int | type[Exception],
    ) -> typing.Callable:  # type: ignore[type-arg]

        def decorator(
                func: typing.Callable) -> typing.Callable:  # type: ignore[type-arg]  # noqa: E501
            self.exception_handlers[exc_class_or_status_code] = func
            return func

        return decorator

    def add_middleware(
            self,
            middleware_class: _MiddlewareFactory[P],
            *args: P.args,
            **kwargs: P.kwargs,
    ) -> None:
        if self.middleware_stack is not None:
            raise RuntimeError(
                'Cannot add middleware after an application has started')
        self.user_middleware.insert(
            0,
            Middleware(middleware_class, *args, **kwargs))  # noqa

    def on_startup(self, func):
        self.on_startup_func_list.append(func)
        return func

    def on_shutdown(self, func):
        self.on_shutdown_func_list.append(func)
        return func


def _file_field_to_properties(self, field, **kwargs):
    if isinstance(field, StarletteFileField):
        return dict(type='string', format='binary')
    return dict()
