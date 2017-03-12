# coding: utf-8
# pylint: disable=redefined-outer-name
import time
from threading import Thread
import os

from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError, URLError
import pytest

from test_server import TestServer, WaitTimeoutError
import test_server


@pytest.fixture(scope='session')
def global_server(opt_engine):
    server = TestServer(engine=opt_engine)
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope='function')
def server(global_server):
    global_server.reset()
    return global_server


@pytest.fixture(autouse=True)
def skip_by_engine(request, opt_engine):
    if request.node.get_marker('skip_engine'):
        if request.node.get_marker('skip_engine').args[0] == opt_engine:
            pytest.skip('Skipped on engine %s' % opt_engine)


def test_get(server):
    valid_data = b'zorro'
    server.response['data'] = valid_data
    data = urlopen(server.get_url()).read()
    assert data == valid_data


def test_non_utf_request_data(server):
    server.request['charset'] = 'cp1251'
    server.response['data'] = 'abc'
    req = Request(url=server.get_url(), data=u'конь'.encode('cp1251'))
    assert urlopen(req).read() == b'abc'
    assert server.request['data'] == u'конь'.encode('cp1251')


def test_request_client_ip(server):
    urlopen(server.get_url()).read()
    assert server.address == server.request['client_ip']


def test_path(server):
    urlopen(server.get_url('/foo?bar=1')).read()
    assert server.request['path'] == '/foo'
    assert server.request['args']['bar'] == '1'


def test_post(server):
    server.response['post.data'] = b'resp-data'
    data = urlopen(server.get_url(), b'req-data').read()
    assert data == b'resp-data'
    assert server.request['data'] == b'req-data'


def test_response_once_get(server):
    server.response['data'] = b'base'
    assert urlopen(server.get_url()).read() == b'base'
    server.response_once['data'] = b'tmp'
    assert urlopen(server.get_url()).read() == b'tmp'
    assert urlopen(server.get_url()).read() == b'base'


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


def test_request_headers(server):
    req = Request(server.get_url(), headers={'Foo': 'Bar'})
    urlopen(req).read()
    assert server.request['headers']['foo'] == 'Bar'


def test_response_once_reset_headers(server):
    server.response_once['headers'] = [('foo', 'bar')]
    server.reset()
    info = urlopen(server.get_url())
    assert 'foo' not in info.headers


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


def test_response_once_code(server):
    info = urlopen(server.get_url())
    assert info.getcode() == 200
    server.response_once['code'] = 403
    with pytest.raises(HTTPError):
        urlopen(server.get_url())
    info = urlopen(server.get_url())
    assert info.getcode() == 200


def test_request_done_after_start(server):
    server = TestServer()
    server.start()
    assert server.request['done'] is False


def test_request_done(server):
    assert server.request['done'] is False
    urlopen(server.get_url()).read()
    assert server.request['done'] is True


def test_wait_request(server):
    server.response['data'] = b'foo'
    #print('.test_wait_request(): started')

    def worker():
        time.sleep(1)
        urlopen(server.get_url() + '?method=test-wait-request').read()
        #print('.test_wait_request(): end of thread')
    th = Thread(target=worker)
    th.start()
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.5)
    server.wait_request(2)
    #res = result.get()
    #assert res == b'foo'
    th.join()
    #print('.test_wait_request(): last line')


def test_wait_timeout_error(server):
    """Need many iterations to be sure"""
    #print('.test_wait_timeout_error(): started')
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.01)


def test_request_cookies(server):
    req = Request(url=server.get_url())
    req.add_header('Cookie', 'foo=bar')
    urlopen(req)
    assert server.request['cookies']['foo']['value'] == 'bar'


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


def test_default_header_content_type(server):
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=utf-8'

# FIXME: FIX IT
# FAILS WITH
# >       assert server.request['args']['who'] == u'конь'
# E       assert 'ГЄГ®Г­Гј' == 'конь'
# E         - ГЄГ®Г­Гј
# E         + конь
#def test_non_utf_request_charset(server):
#    server.request['charset'] = 'cp1251'
#    server.response['data'] = 'abc'
#    req = Request(url=server.get_url() + u'?who=конь'.encode('cp1251'))
#    assert urlopen(req).read() == b'abc'
#    assert server.request['args']['who'] == u'конь'


def test_custom_header_content_type(server):
    server.response['headers'] = (
        ('Content-Type', 'text/html; charset=koi8-r'),
    )
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=koi8-r'


def test_default_header_server(server):
    info = urlopen(server.get_url())
    assert (info.headers['server'] ==
            ('TestServer/%s' % test_server.__version__))


def test_custom_header_server(server):
    server.response['headers'] = (
        ('Server', 'Google'),
    )
    info = urlopen(server.get_url())
    assert info.headers['server'] == 'Google'


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


def test_multiple_start_stop_cycles():
    for _ in range(30):
        server2 = TestServer()
        server2.start()
        try:
            server2.response['data'] = b'zorro'
            for _ in range(10):
                data = urlopen(server2.get_url()).read()
                assert data == b'zorro'
        finally:
            server2.stop()


@pytest.mark.skip_engine('thread')
def test_temp_files_are_removed():
    server2 = TestServer(engine='subprocess')
    server2.start()
    files = [
        server2.request_file,
        server2.response_file,
        server2.response_once_file,
        server2.request_lock_file,
        server2.response_lock_file,
        server2.response_once_lock_file,
    ]
    server2.stop()
    assert all(not os.path.exists(x) for x in files)


@pytest.mark.skip_engine('subprocess')
def test_data_generator(server):

    def data():
        yield b'foo'
        yield b'bar'

    server.response['data'] = data()
    data1 = urlopen(server.get_url()).read()
    assert data1 == b'foo'
    data2 = urlopen(server.get_url()).read()
    assert data2 == b'bar'
    with pytest.raises(URLError) as ex:
        urlopen(server.get_url())
    assert ex.value.code == 405
    assert ex.value.read() == b'data generator has no more data'


def test_specific_port():
    server = TestServer(address='localhost', port=9876)
    server.start()
    server.response['data'] = b'abc'
    data = urlopen(server.get_url()).read()
    assert data == b'abc'
