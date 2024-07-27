# -*- coding: UTF-8 -*-
import dataclasses

from marshmallow import fields

from muso.application import Muso
from muso.auth import AuthBase, AuthMarkAPIKeyInHeader, AuthMarkHTTPBearer
from muso.request import MusoRequest
from muso.response import FileBytesResponse
from muso.route import RouteGroup
from muso.schema import BaseSchema


class Config:
    MUSO_DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5001


api_v1 = RouteGroup(prefix='/api/v1', tag='apiV1Tag',
                    description='api v1 desc')
api_v2 = RouteGroup(prefix='/api/v2', tag='apiV2Tag',
                    description='api v2 desc')


@dataclasses.dataclass
class User:
    id_: int
    name: str


class AuthTest(AuthBase):

    def __init__(self, role: str):
        super().__init__(
            auth_marks=(
                AuthMarkHTTPBearer(
                    key='tenantBearerToken', description='测试BearerToken'),
                AuthMarkAPIKeyInHeader(
                    key='TenantKeyAuth', header_key='X-Tenant-Key',
                    description='测试ApiKeyInHeader'),
            ),
        )
        self.role = role

    async def __call__(self, *, request: MusoRequest) -> User:
        print(request)
        print(request.headers())
        print(request._starlette_request.url)
        print(request._starlette_request.headers)
        return User(id_=1, name='test')


class ResponseTestNested(BaseSchema):
    d = fields.String()


class ResponseTest(BaseSchema):
    test_result = fields.String(data_key='testResult')
    b = fields.String()
    nested = fields.Nested(nested=ResponseTestNested(), data_key='nestedField')


@api_v1.get(uri='/testResponse', auth=AuthTest(role='123456'),
            response=ResponseTest())
def test_response(current_user: User):
    """ 测试返回值 """
    print(current_user)
    return {'test_result': 1, 'b': '2', 'test': True,
            'nested': {'d': 'nested'}}


class RequestQueryTest(BaseSchema):
    normal_field = fields.Bool(required=True, data_key='normalField')


@api_v1.get(uri='/testQuery', query_args=RequestQueryTest())
async def test_query(request: MusoRequest):
    query_args = await request.query_args()
    return {'a': 1, 'b': '2', 'test2': query_args['normal_field']}


class RequestFormTest3(BaseSchema):
    normal_field = fields.Bool(required=True, data_key='normalField')


@api_v1.post(uri='/testForm', form_data=RequestFormTest3())
async def test_form(request: MusoRequest):
    form_data = await request.form_data()
    return {'a': 1, 'b': '2', 'test3': form_data['normal_field']}


@api_v1.post(uri='/testJson', json_body=RequestFormTest3())
async def test_json(request: MusoRequest):
    json_body = await request.json_body()
    return {'a': 1, 'b': '2', 'test4': json_body['normal_field']}


class RequestFormTestUpload(BaseSchema):
    normal_field = fields.Raw(required=True, data_key='fileField')


@api_v2.post(uri='/testUpload', form_data=RequestFormTestUpload())
async def test_upload(request: MusoRequest):
    """ 测试上传 """
    form_data = await request.form_data()
    print(form_data)
    return None


with open('test.pdf', 'rb') as f:
    file_bytes = f.read()


@api_v2.get(uri='/testDownload', is_streaming_response=True)
async def test_download():
    """ 测试下载 """
    return FileBytesResponse(content=file_bytes)


app = Muso(name='exampleApp', version='1.0.0', description='example app',
           debug=True)
app.add_route_group(route_group=api_v1)
app.add_route_group(route_group=api_v2)


@app.on_startup
async def test_startup():
    print('on_startup')


@app.on_shutdown
async def test_shutdown():
    print('on_shutdown')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app='examples.hello:app',
                host='0.0.0.0', port=5001, loop='uvloop', reload=True)
