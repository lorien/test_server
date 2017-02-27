"""
Test server could be run in two modes: thread and subprocess.
The later mode could be used when you doing something/anything with
standard python socket library and do not want side-effects. Running test
server in separate process ensures that test_server uses unmodified stdlib.

Most tests functions in this module are duplicated with *_with_state
function:
* test_foo tests default test_server engine (based on thread) and operates
    with request and response directly (in-place)
* tests_foo_with_state tests subprocess engine (based on separate process) and
    use settter/getter functions to access request and response because the
    API and test server work in different processes.
"""
# pylint: disable=redefined-outer-name
import time
from threading import Thread
import os

from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.error import HTTPError
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


def test_get_with_state(server):
    valid_data = b'zorro'
    server.set_response('data', valid_data)
    data = urlopen(server.get_url()).read()
    assert data == valid_data


def test_request_client_ip_with_state(server):
    urlopen(server.get_url()).read()
    assert server.address == server.get_request('client_ip')


def test_path_with_state(server):
    urlopen(server.get_url('/foo?bar=1')).read()
    assert server.get_request('path') == '/foo'
    assert server.get_request('args')['bar'] == '1'


def test_post_with_state(server):
    server.set_response('post.data', b'resp-data')
    data = urlopen(server.get_url(), b'req-data').read()
    assert data == b'resp-data'
    assert server.get_request('data') == b'req-data'


def test_response_once_get_with_state(server):
    server.set_response('data', b'base')
    assert urlopen(server.get_url()).read() == b'base'
    server.set_response_once('data', b'tmp')
    assert urlopen(server.get_url()).read() == b'tmp'
    assert urlopen(server.get_url()).read() == b'base'


def test_response_once_headers_with_state(server):
    server.set_response('headers', [('foo', 'bar')])
    info = urlopen(server.get_url())
    assert info.headers['foo'] == 'bar'

    server.set_response_once('headers', [('baz', 'gaz')])
    info = urlopen(server.get_url())
    assert info.headers['baz'] == 'gaz'
    assert 'foo' not in info.headers

    info = urlopen(server.get_url())
    assert 'baz' not in info.headers
    assert info.headers['foo'] == 'bar'


def test_request_headers_with_state(server):
    req = Request(server.get_url(), headers={'Foo': 'Bar'})
    urlopen(req).read()
    assert server.get_request('headers')['foo'] == 'Bar'


def test_response_once_reset_headers_with_state(server):
    server.set_response_once('headers', [('foo', 'bar')])
    server.reset()
    info = urlopen(server.get_url())
    assert 'foo' not in info.headers


def test_method_sleep_with_state(server):
    delay = 0.3

    start = time.time()
    urlopen(server.get_url())
    elapsed = time.time() - start
    assert elapsed <= delay

    server.set_response('sleep', delay)
    start = time.time()
    urlopen(server.get_url())
    elapsed = time.time() - start
    assert elapsed > delay


def test_response_once_code_with_state(server):
    info = urlopen(server.get_url())
    assert info.getcode() == 200
    server.set_response_once('code', 403)
    with pytest.raises(HTTPError):
        urlopen(server.get_url())
    info = urlopen(server.get_url())
    assert info.getcode() == 200


def test_request_done_after_start_with_state(server):
    server = TestServer()
    server.start()
    assert server.get_request('done') is False


def test_request_done_with_state(server):
    assert server.get_request('done') is False
    urlopen(server.get_url()).read()
    assert server.get_request('done') is True


def test_wait_request(server):
    def worker():
        time.sleep(1)
        urlopen(server.get_url()).read()
    Thread(target=worker).start()
    server.wait_request(2)


def test_wait_timeout_error(server):
    """Need many iterations to be sure"""
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.01)


def test_response_once_cookies_with_state(server):
    server.set_response('cookies', [('foo', 'bar')])
    info = urlopen(server.get_url())
    assert 'foo=bar' in info.headers['Set-Cookie']

    server.set_response_once('cookies', [('baz', 'gaz')])
    info = urlopen(server.get_url())
    assert 'foo=bar' not in info.headers['Set-Cookie']
    assert 'baz=gaz' in info.headers['Set-Cookie']

    info = urlopen(server.get_url())
    assert 'foo=bar' in info.headers['Set-Cookie']
    assert 'baz=gaz' not in info.headers['Set-Cookie']


def test_default_header_content_type(server):
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=UTF-8'


def test_custom_header_content_type_with_state(server):
    server.set_response('headers', [
        ('Content-Type', 'text/html; charset=koi8-r'),
    ])
    info = urlopen(server.get_url())
    assert info.headers['content-type'] == 'text/html; charset=koi8-r'


def test_default_header_server(server):
    info = urlopen(server.get_url())
    assert (info.headers['server'] ==
            ('TestServer/%s' % test_server.__version__))


def test_custom_header_server_with_state(server):
    server.set_response('headers', [
        ('Server', 'Google'),
    ])
    info = urlopen(server.get_url())
    assert info.headers['server'] == 'Google'


def test_options_method_with_state(server):
    server.set_response('data', b'abc')

    class RequestWithMethod(Request):
        def __init__(self, method, *args, **kwargs):
            self._method = method
            Request.__init__(self, *args, **kwargs)

        def get_method(self):
            return self._method

    req = RequestWithMethod(url=server.get_url(),
                            method='OPTIONS')
    info = urlopen(req)
    assert server.get_request('method') == 'OPTIONS'
    assert info.read() == b'abc'


def test_multiple_start_stop_cycles():
    for _ in range(30):
        server2 = TestServer()
        server2.start()
        try:
            server2.set_response('data', b'zorro')
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
