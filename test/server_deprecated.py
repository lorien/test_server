"""
This module tests deprecated direct access to
request, response and response_once attributes.
You should use methods like get_request, set_response, etc.
"""
# pylint: disable=redefined-outer-name
import time

from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError
import pytest

from test_server import TestServer
from .server import (global_server, # pylint: disable=unused-import
                     server, skip_by_engine)


@pytest.mark.skip_engine('subprocess')
def test_get(server):
    valid_data = b'zorro'
    server.response['data'] = valid_data
    data = urlopen(server.get_url()).read()
    assert data == valid_data


@pytest.mark.skip_engine('subprocess')
def test_request_client_ip(server):
    urlopen(server.get_url()).read()
    assert server.address == server.request['client_ip']


@pytest.mark.skip_engine('subprocess')
def test_path(server):
    urlopen(server.get_url('/foo?bar=1')).read()
    assert server.request['path'] == '/foo'
    assert server.request['args']['bar'] == '1'


@pytest.mark.skip_engine('subprocess')
def test_post(server):
    server.response['post.data'] = b'resp-data'
    data = urlopen(server.get_url(), b'req-data').read()
    assert data == b'resp-data'
    assert server.request['data'] == b'req-data'


@pytest.mark.skip_engine('subprocess')
def test_response_once_get(server):
    server.response['data'] = b'base'
    assert urlopen(server.get_url()).read() == b'base'
    server.response_once['data'] = b'tmp'
    assert urlopen(server.get_url()).read() == b'tmp'
    assert urlopen(server.get_url()).read() == b'base'


@pytest.mark.skip_engine('subprocess')
def test_response_once_headers(server):
    server.response['headers'] = [('foo', 'bar')]
    info = urlopen(server.get_url())
    assert info.headers['foo'] == 'bar'

    server.response_once['headers'] = [('baz', 'gaz')]
    info = urlopen(server.get_url())
    assert info.headers['baz'] == 'gaz'
    assert 'foo' not in info.headers

    info = urlopen(server.get_url())
    assert 'baz' not in info.headers
    assert info.headers['foo'] == 'bar'


@pytest.mark.skip_engine('subprocess')
def test_request_headers(server):
    req = Request(server.get_url(), headers={'Foo': 'Bar'})
    urlopen(req).read()
    assert server.request['headers']['foo'] == 'Bar'


@pytest.mark.skip_engine('subprocess')
def test_response_once_reset_headers(server):
    server.response_once['headers'] = [('foo', 'bar')]
    server.reset()
    info = urlopen(server.get_url())
    assert 'foo' not in info.headers


@pytest.mark.skip_engine('subprocess')
def test_method_sleep(server):
    delay = 0.3

    start = time.time()
    urlopen(server.get_url())
    elapsed = time.time() - start
    assert elapsed <= delay

    server.response['sleep'] = delay
    start = time.time()
    urlopen(server.get_url())
    elapsed = time.time() - start
    assert elapsed > delay


@pytest.mark.skip_engine('subprocess')
def test_response_once_code(server):
    info = urlopen(server.get_url())
    assert info.getcode() == 200
    server.response_once['code'] = 403
    with pytest.raises(HTTPError):
        urlopen(server.get_url())
    info = urlopen(server.get_url())
    assert info.getcode() == 200


@pytest.mark.skip_engine('subprocess')
def test_request_done_after_start(server):
    server = TestServer()
    server.start()
    assert server.request['done'] is False


@pytest.mark.skip_engine('subprocess')
def test_request_done(server):
    assert server.request['done'] is False
    urlopen(server.get_url()).read()
    assert server.request['done'] is True


@pytest.mark.skip_engine('subprocess')
def test_response_once_cookies(server):
    server.response['cookies'] = [('foo', 'bar')]
    info = urlopen(server.get_url())
    assert 'foo=bar' in info.headers['Set-Cookie']

    server.response_once['cookies'] = [('baz', 'gaz')]
    info = urlopen(server.get_url())
    assert 'foo=bar' not in info.headers['Set-Cookie']
    assert 'baz=gaz' in info.headers['Set-Cookie']

    info = urlopen(server.get_url())
    assert 'foo=bar' in info.headers['Set-Cookie']
    assert 'baz=gaz' not in info.headers['Set-Cookie']


@pytest.mark.skip_engine('subprocess')
def test_custom_header_content_type(server):
    server.response['headers'] = [
        ('Content-Type', 'text/html; charset=koi8-r')]
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=koi8-r'


@pytest.mark.skip_engine('subprocess')
def test_custom_header_server(server):
    server.response['headers'] = [
        ('Server', 'Google')]
    info = urlopen(server.get_url())
    assert info.headers['server'] == 'Google'


@pytest.mark.skip_engine('subprocess')
def test_options_method(server):
    server.response['data'] = b'abc'

    class RequestWithMethod(Request):
        def __init__(self, method, *args, **kwargs):
            self._method = method
            Request.__init__(self, *args, **kwargs)

        def get_method(self):
            return self._method

    req = RequestWithMethod(url=server.get_url(),
                            method='OPTIONS')
    info = urlopen(req)
    assert server.request['method'] == 'OPTIONS'
    assert info.read() == b'abc'
