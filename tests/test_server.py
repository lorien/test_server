# pylint: disable=consider-using-f-string
from pprint import pprint  # pylint: disable=unused-import
from threading import Thread
import time
from urllib.parse import unquote

from urllib3 import PoolManager
from urllib3.util.retry import Retry
import pytest

from test_server import (
    TestServer,
    WaitTimeoutError,
    TestServerError,
    Response,
    RequestNotProcessed,
)
import test_server

from .util import fixture_global_server, fixture_server  # pylint: disable=unused-import

NETWORK_TIMEOUT = 1
EXTRA_PORT = 10100
pool = PoolManager()


def request(url, data=None, method=None, headers=None, fields=None):
    params = {
        "headers": headers,
        "timeout": NETWORK_TIMEOUT,
        "retries": Retry(
            connect=0,
            read=0,
            redirect=10,
            other=0,
        ),
        "fields": fields,
    }
    if data:
        assert isinstance(data, bytes)
        params["body"] = data
    if not method:
        method = "POST" if (data or fields) else "GET"
    return pool.request(method, url, **params)


def test_get(server):
    valid_data = b"zorro"
    server.add_response(Response(data=valid_data))
    res = request(server.get_url())
    assert res.data == valid_data


def test_non_utf_request_data(server):
    server.add_response(Response(data="abc"))
    res = request(url=server.get_url(), data=u"конь".encode("cp1251"))
    assert res.data == b"abc"
    assert server.get_request()["data"] == u"конь".encode("cp1251")


def test_request_client_ip(server):
    server.add_response(Response())
    request(server.get_url())
    assert server.address == server.get_request()["client_ip"]


def test_path(server):
    server.add_response(Response())
    request(server.get_url("/foo?bar=1"))
    assert server.get_request()["path"] == "/foo"
    assert server.get_request()["args"]["bar"] == "1"


def test_post(server):
    server.add_response(Response(data="abc"), method="post")
    res = request(server.get_url(), b"req-data")
    assert res.data == b"abc"
    assert server.get_request()["data"] == b"req-data"


def test_response_once_get(server):
    server.add_response(Response(data="base"), count=2)
    assert request(server.get_url()).data == b"base"
    server.add_response(Response(data="tmp"))
    assert request(server.get_url()).data == b"tmp"
    assert request(server.get_url()).data == b"base"


def test_response_once_specific_method(server):
    server.add_response(Response(data="bar"), method="get")
    server.add_response(Response(data="foo"))
    assert request(server.get_url()).data == b"bar"


def test_response_once_headers(server):
    server.add_response(Response(headers=[("foo", "bar")]), count=2)
    info = request(server.get_url())
    assert info.headers["foo"] == "bar"

    server.add_response(Response(headers=[("baz", "gaz")]))
    info = request(server.get_url())
    assert info.headers["baz"] == "gaz"
    assert "foo" not in info.headers

    info = request(server.get_url())
    assert "baz" not in info.headers
    assert info.headers["foo"] == "bar"


def test_request_headers(server):
    server.add_response(Response())
    request(server.get_url(), headers={"Foo": "Bar"})
    assert server.get_request()["headers"]["foo"] == "Bar"


def test_response_once_reset_headers(server):
    server.add_response(Response(headers=[("foo", "bar")]))
    server.reset()
    res = request(server.get_url())
    assert res.status == 555
    assert b"No response" in res.data


def test_method_sleep(server):
    server.add_response(Response())
    delay = 0.3

    start = time.time()
    request(server.get_url())
    elapsed = time.time() - start
    assert elapsed <= delay

    server.add_response(Response(sleep=delay))
    start = time.time()
    request(server.get_url())
    elapsed = time.time() - start
    assert elapsed > delay


def test_response_once_code(server):
    server.add_response(Response(), count=2)
    res = request(server.get_url())
    assert res.status == 200
    server.add_response(Response(status=403))
    res = request(server.get_url())
    assert res.status == 403
    res = request(server.get_url())
    assert res.status == 200


def test_request_done_after_start(server):
    server = TestServer(port=EXTRA_PORT)
    try:
        server.start()
        assert not server.request_is_done()
    finally:
        server.stop()


def test_request_done(server):
    assert not server.request_is_done()
    server.add_response(Response())
    request(server.get_url())
    assert server.request_is_done()


def test_wait_request(server):
    server.add_response(Response(data=b"foo"))

    def worker():
        time.sleep(1)
        request(server.get_url() + "?method=test-wait-request")

    th = Thread(target=worker)
    th.start()
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.5)
    server.wait_request(2)
    th.join()


def test_request_cookies(server):
    server.add_response(Response())
    request(url=server.get_url(), headers={"Cookie": "foo=bar"})
    assert server.get_request()["cookies"]["foo"]["value"] == "bar"


def test_response_once_cookies(server):
    server.add_response(Response(cookies=[("foo", "bar")]), count=2)
    info = request(server.get_url())
    assert "foo=bar" in info.headers["Set-Cookie"]

    server.add_response(Response(cookies=[("baz", "gaz")]))
    info = request(server.get_url())
    assert "foo=bar" not in info.headers["Set-Cookie"]
    assert "baz=gaz" in info.headers["Set-Cookie"]

    info = request(server.get_url())
    assert "foo=bar" in info.headers["Set-Cookie"]
    assert "baz=gaz" not in info.headers["Set-Cookie"]


def test_default_header_content_type(server):
    server.add_response(Response())
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=utf-8"


def test_custom_header_content_type(server):
    server.add_response(
        Response(headers=[("Content-Type", "text/html; charset=koi8-r")])
    )
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=koi8-r"


def test_default_header_server(server):
    server.add_response(Response())
    info = request(server.get_url())
    assert info.headers["server"] == ("TestServer/%s" % test_server.__version__)


def test_custom_header_server(server):
    server.add_response(Response(headers=[("Server", "Google")]))
    info = request(server.get_url())
    assert info.headers["server"] == "Google"


def test_options_method(server):
    server.add_response(Response(data=b"abc"))
    res = request(url=server.get_url(), method="OPTIONS")
    assert server.get_request()["method"] == "OPTIONS"
    assert res.data == b"abc"


def test_multiple_start_stop_cycles():
    for cnt in range(30):
        server = TestServer(port=EXTRA_PORT + cnt)
        server.start()
        try:
            server.add_response(Response(data=b"zorro"), count=10)
            for _ in range(10):
                res = request(server.get_url())
                assert res.data == b"zorro"
        finally:
            server.stop()


def test_specific_port():
    server = TestServer(address="localhost", port=EXTRA_PORT)
    try:
        server.start()
        server.add_response(Response(data=b"abc"))
        data = request(server.get_url()).data
        assert data == b"abc"
    finally:
        server.stop()


def test_null_bytes(server):
    server.add_response(Response(data=b"zzz"))
    server.add_response(
        Response(
            status=302,
            headers=[
                ("Location", server.get_url().rstrip("/") + "/\x00/"),
            ],
        )
    )
    res = request(server.get_url())
    assert res.data == b"zzz"
    assert unquote(server.get_request()["path"]) == "/\x00/"


# def send_get_request(host, port, path):
#    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#    sock.connect((host, port))
#    data = (
#        b'GET %s HTTP/1.1\r\n'
#        b'Host: %s\r\n'
#        b'\r\n'
#        #% (quote(path, safe='/').encode('utf-8'), host.encode('utf-8'))
#        % (path, host.encode('utf-8'))
#    )
#    sock.send(data)
#    data = sock.recv(1024 * 10)
#    sock.close()
#    return data


def test_utf_header(server):
    server.add_response(
        Response(headers=[("Location", (server.get_url() + u"фыва").encode("utf-8"))])
    )
    request(server.get_url())
    # WTF ???


def test_callback(server):
    non_ascii_str = "фыва"

    def get_callback():
        return {
            "type": "response",
            "body": b"Hello",
            "headers": [
                ("method", "get"),
            ],
        }

    def post_callback():
        return {
            "type": "response",
            "status": 201,
            "body": non_ascii_str,
            "headers": [
                ("method", "post"),
            ],
            "cookies": [
                ("foo", "bar"),
            ],
        }

    server.add_response(Response(callback=get_callback))
    server.add_response(Response(callback=post_callback), method="post")

    info = request(server.get_url())
    assert info.headers["method"] == "get"
    assert info.data == b"Hello"

    info = request(server.get_url(), b"key=val")
    assert info.headers["method"] == "post"
    assert info.headers["set-cookie"] == "foo=bar"
    assert info.data == non_ascii_str.encode("utf-8")
    assert info.status == 201


def test_response_data_invalid_type(server):
    server.add_response(Response(data=1))
    res = request(server.get_url())
    assert res.status == 555
    assert b"must be string or bytes" in res.data


def test_stop_not_started_server():
    server = TestServer(port=EXTRA_PORT)
    server.stop()


def test_start_request_stop_same_port():
    server = TestServer(port=EXTRA_PORT)
    for _ in range(10):
        try:
            server.start()
            server.add_response(Response())
            request(server.get_url())
        finally:
            server.stop()


def test_file_uploading(server):
    server.add_response(Response())
    request(
        server.get_url(),
        fields={
            "image": ("emoji.png", b"zzz"),
        },
    )
    assert server.get_request()["files"]["image"][0]["name"] == "image"


def test_callback_response_not_dict(server):
    def callback():
        return ["foo", "bar"]

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"is not a dict" in res.data


def test_callback_response_invalid_type(server):
    def callback():
        return {
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"invalid type key" in res.data


def test_callback_response_invalid_key(server):
    def callback():
        return {
            "type": "response",
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"contains invalid key" in res.data


def test_invalid_response_key(server):
    with pytest.raises(TypeError) as ex:
        Response(foo="bar")
    assert "unexpected keyword argument" in str(ex.value)


def test_get_request_no_request(server):
    with pytest.raises(RequestNotProcessed):
        server.get_request()


def test_add_response_invalid_method(server):
    with pytest.raises(TestServerError) as ex:
        server.add_response(Response(), method="foo")
    assert "Invalid method" in str(ex.value)


def test_add_response_count_minus_one(server):
    server.add_response(Response(), count=-1)
    for _ in range(3):
        assert 200 == request(server.get_url()).status


def test_add_response_count_one_default(server):
    server.add_response(Response())
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data

    server.add_response(Response(), count=1)
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data


def test_add_response_count_two(server):
    server.add_response(Response(), count=2)
    assert 200 == request(server.get_url()).status
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data
