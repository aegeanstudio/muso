# -*- coding: UTF-8 -*-

import orjson
import tzlocal
from marshmallow import Schema, fields


class BaseSchema(Schema):
    class Meta:
        render_module = orjson


class LimitOffsetSchema(BaseSchema):
    limit = fields.Integer(required=True, description='限制数量')
    offset = fields.Integer(required=True, description='偏移量')


class PaginatorSchema(BaseSchema):
    page_no = fields.Integer(
        data_key='pageNo', required=True, description='页码')
    page_size = fields.Integer(
        data_key='pageSize', required=True, description='每页数量')


class EmptyResponseSchema(BaseSchema):
    code = fields.Integer(missing=0, allow_none=False, dump_default=0)
    msg = fields.String(missing='', dump_default='')
    data = fields.Raw(missing=None, allow_none=True)


class LocalDateTimeField(fields.DateTime):

    def __init__(self, ignore_microsecond: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ignore_microsecond = ignore_microsecond

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        if self.ignore_microsecond:
            value = value.replace(microsecond=0)
        return super()._serialize(value.astimezone(
            tz=tzlocal.get_localzone()), attr, obj, **kwargs)


class StarletteFileField(fields.Field):

    def __init__(self, content_type_list: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_type_list = content_type_list
