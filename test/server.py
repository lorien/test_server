from unittest import TestCase
import time
from threading import Thread

from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError
import pytest

from test_server import TestServer, WaitTimeoutError
import test_server


@pytest.fixture(scope='module')
def global_server():
    server = TestServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope='function')
def server(global_server):
    global_server.reset()
    return global_server


def test_get(server):
    server.response['data'] = b'zorro'
    data = urlopen(server.get_url()).read()
    assert data == server.response['data']


def test_request_client_ip(server):
    urlopen(server.get_url()).read()
    assert server.address == server.request['client_ip']


def test_path(server):
    urlopen(server.get_url('/foo')).read()
    assert server.request['path'] == '/foo'

    urlopen(server.get_url('/foo?bar=1')).read()
    assert server.request['path'] == '/foo'
    assert server.request['args']['bar'] == '1'


def test_post(server):
    server.response['post.data'] = b'foo'
    data = urlopen(server.get_url(), b'THE POST').read()
    assert data == server.response['post.data']


def test_data_iterator(server):
    class ContentGenerator(object):
        def __init__(self):
            self.count = 0

        def __iter__(self):
            return self

        def next(self):
            self.count += 1
            return 'foo'

        __next__ = next

    gen = ContentGenerator()
    server.response['get.data'] = gen
    urlopen(server.get_url()).read()
    assert gen.count == 1
    urlopen(server.get_url()).read()
    assert gen.count == 2
    # Now create POST request which should no be
    # processed with ContentGenerator which is bind to GET
    # requests
    urlopen(server.get_url(), b'some post').read()
    assert gen.count == 2


def test_data_generator(server):
    def gen():
        yield b'one'
        yield b'two'

    server.response['get.data'] = gen()
    assert b'one' == urlopen(server.get_url()).read()
    assert b'two' == urlopen(server.get_url()).read()
    with pytest.raises(HTTPError):
       urlopen(server.get_url())


def test_response_once_get(server):
    server.response['data'] = b'base'
    assert b'base' == urlopen(server.get_url()).read()

    server.response_once['data'] = b'tmp'
    assert b'tmp' == urlopen(server.get_url()).read()

    assert b'base' == urlopen(server.get_url()).read()


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


def test_callback(server):
    def get_callback(self):
        self.set_header('method', 'get')
        self.write(b'Hello')
        self.finish()

    def post_callback(self):
        self.set_header('method', 'post')
        self.write(b'Hello')
        self.finish()

    server.response['callback'] = get_callback
    info = urlopen(server.get_url())
    assert info.headers['method'] == 'get'
    assert info.read() == b'Hello'

    server.response['post.callback'] = post_callback
    info = urlopen(server.get_url(), b'key=val')
    assert info.headers['method'] == 'post'
    assert info.read() == b'Hello'


def test_callback_yield_(server):
    def callback(self):
        self.set_header('method', 'get')
        self.write(b'Hello')
        yield {'type': 'sleep', 'time': 0.0001}
        self.write(b'World')

        self.finish()

    server.response['callback'] = callback
    info = urlopen(server.get_url())
    assert info.read() == b'HelloWorld'


def test_response_once_code(server):
    info = urlopen(server.get_url())
    assert info.getcode() == 200

    server.response_once['code'] = 403
    with pytest.raises(HTTPError):
        urlopen(server.get_url())

    info = urlopen(server.get_url())
    assert info.getcode() == 200


def test_request_done_after_start(server):
    server = TestServer(port=server.port + 1)
    server.start()
    assert server.request['done'] is False


def test_request_done(server):
    assert server.request['done'] is False
    urlopen(server.get_url()).read()
    assert server.request['done'] is True


def test_wait_request(server):
    def worker():
        time.sleep(1)
        urlopen(server.get_url()).read()
    Thread(target=worker).start()
    server.wait_request(2)


def test_wait_timeout_error(server):
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.5)


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
    assert info.headers['content-type'] == 'text/html; charset=UTF-8'


def test_custom_header_content_type(server):
    server.response['headers'] = [
        ('Content-Type', 'text/html; charset=koi8-r')]
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=koi8-r'


def test_default_header_server(server):
    info = urlopen(server.get_url())
    assert (info.headers['server'] ==
            ('TestServer/%s' % test_server.__version__))


def test_custom_header_server(server):
    server.response['headers'] = [
        ('Server', 'Google')]
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
    assert 'OPTIONS' == server.request['method']
    assert b'abc' == server.response['data']


def test_multiple_start_stop_cycles():
    for x in range(30):
        server = TestServer()
        server.start()
        try:
            server.response['data'] = b'zorro'
            for y in range(10):
                data = urlopen(server.get_url()).read()
                assert data == server.response['data']
        finally:
            server.stop()


def test_extra_ports():
    port = 9878
    extra_ports = [9879, 9880]
    server = TestServer(port=port, extra_ports=extra_ports)
    server.start()
    try:
        server.response['data'] = b'zorro'
        for port in [port] + extra_ports:
            data = urlopen(server.get_url(port=port)).read()
            assert data == server.response['data']
    finally:
        server.stop()
