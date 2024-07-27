# -*- coding: UTF-8 -*-

import abc
import typing

from muso.request import MusoRequest


class OpenAPIAuthMarkBase(metaclass=abc.ABCMeta):

    def __init__(self, *, key: str, description: str = ''):
        self.key = key
        self.description = description

    @property
    @abc.abstractmethod
    def as_dict(self) -> dict:
        ...


class AuthMarkHTTPBearer(OpenAPIAuthMarkBase):

    @property
    def as_dict(self) -> dict:
        return {
            'type': 'http',
            'scheme': 'bearer',
            'description': self.description,
        }


class AuthMarkAPIKeyInHeader(OpenAPIAuthMarkBase):

    def __init__(self, *, key: str, header_key: str, description: str = ''):
        super().__init__(key=key, description=description)
        self.header_key = header_key

    @property
    def as_dict(self) -> dict:
        return {
            'type': 'apiKey',
            'name': self.header_key,
            'in': 'header',
            'description': self.description,
        }


class AuthBase(metaclass=abc.ABCMeta):

    def __init__(self, *, auth_marks: typing.Sequence[OpenAPIAuthMarkBase]):
        self.auth_marks = auth_marks

    @abc.abstractmethod
    def __call__(self, *, request: MusoRequest) -> typing.Any:
        ...
