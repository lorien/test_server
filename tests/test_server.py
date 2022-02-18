# pylint: disable=consider-using-f-string
from pprint import pprint  # pylint: disable=unused-import
from threading import Thread
import time
from urllib.parse import unquote

from urllib3 import PoolManager
from urllib3.util.retry import Retry
import pytest

from test_server import TestServer, WaitTimeoutError, TestServerError
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
    server.response["data"] = valid_data
    res = request(server.get_url())
    assert res.data == valid_data


def test_non_utf_request_data(server):
    server.request["charset"] = "cp1251"
    server.response["data"] = "abc"
    res = request(url=server.get_url(), data=u"конь".encode("cp1251"))
    assert res.data == b"abc"
    assert server.request["data"] == u"конь".encode("cp1251")


def test_request_client_ip(server):
    request(server.get_url())
    assert server.address == server.request["client_ip"]


def test_path(server):
    request(server.get_url("/foo?bar=1"))
    assert server.request["path"] == "/foo"
    assert server.request["args"]["bar"] == "1"


def test_post(server):
    server.response["post.data"] = b"resp-data"
    data = request(server.get_url(), b"req-data").data
    assert data == b"resp-data"
    assert server.request["data"] == b"req-data"


def test_response_once_get(server):
    server.response["data"] = b"base"
    assert request(server.get_url()).data == b"base"
    server.response_once["data"] = b"tmp"
    assert request(server.get_url()).data == b"tmp"
    assert request(server.get_url()).data == b"base"


def test_response_once_specific_method(server):
    server.response_once["data"] = b"foo"
    server.response_once["get.data"] = b"bar"
    assert request(server.get_url()).data == b"bar"


def test_get_param_unconfigured(server):
    with pytest.raises(TestServerError):
        server.get_param("FOOBAR")


def test_response_once_headers(server):
    server.response["headers"] = [("foo", "bar")]
    info = request(server.get_url())
    assert info.headers["foo"] == "bar"

    server.response_once["headers"] = [("baz", "gaz")]
    info = request(server.get_url())
    assert info.headers["baz"] == "gaz"
    assert "foo" not in info.headers

    info = request(server.get_url())
    assert "baz" not in info.headers
    assert info.headers["foo"] == "bar"


def test_request_headers(server):
    request(server.get_url(), headers={"Foo": "Bar"})
    assert server.request["headers"]["foo"] == "Bar"


def test_response_once_reset_headers(server):
    server.response_once["headers"] = [("foo", "bar")]
    server.reset()
    info = request(server.get_url())
    assert "foo" not in info.headers


def test_method_sleep(server):
    delay = 0.3

    start = time.time()
    request(server.get_url())
    elapsed = time.time() - start
    assert elapsed <= delay

    server.response["sleep"] = delay
    start = time.time()
    request(server.get_url())
    elapsed = time.time() - start
    assert elapsed > delay


def test_response_once_code(server):
    res = request(server.get_url())
    assert res.status == 200
    server.response_once["status"] = 403
    res = request(server.get_url())
    assert res.status == 403
    res = request(server.get_url())
    assert res.status == 200


def test_request_done_after_start(server):
    server = TestServer(port=EXTRA_PORT)
    try:
        server.start()
        assert server.request["done"] is False
    finally:
        server.stop()


def test_request_done(server):
    assert server.request["done"] is False
    request(server.get_url())
    assert server.request["done"] is True


def test_wait_request(server):
    server.response["data"] = b"foo"

    def worker():
        time.sleep(1)
        request(server.get_url() + "?method=test-wait-request")

    th = Thread(target=worker)
    th.start()
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.5)
    server.wait_request(2)
    # res = result.get()
    # assert res == b'foo'
    th.join()


def test_request_cookies(server):
    request(url=server.get_url(), headers={"Cookie": "foo=bar"})
    assert server.request["cookies"]["foo"]["value"] == "bar"


def test_response_once_cookies(server):
    server.response["cookies"] = [("foo", "bar")]
    info = request(server.get_url())
    assert "foo=bar" in info.headers["Set-Cookie"]

    server.response_once["cookies"] = [("baz", "gaz")]
    info = request(server.get_url())
    assert "foo=bar" not in info.headers["Set-Cookie"]
    assert "baz=gaz" in info.headers["Set-Cookie"]

    info = request(server.get_url())
    assert "foo=bar" in info.headers["Set-Cookie"]
    assert "baz=gaz" not in info.headers["Set-Cookie"]


def test_default_header_content_type(server):
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=utf-8"


# def test_non_utf_request_charset(server):
#    #server.request['charset'] = 'cp1251'
#    server.response['data'] = 'abc'
#    req = Request(
#        url=server.get_url() + quote(u'?who=конь'.encode('cp1251'), safe='?=')
#    )
#    assert request(req).data == b'abc'
#    assert server.request['args']['who'] == u'конь'.encode('cp1251')


def test_custom_header_content_type(server):
    server.response["headers"] = (("Content-Type", "text/html; charset=koi8-r"),)
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=koi8-r"


def test_default_header_server(server):
    info = request(server.get_url())
    assert info.headers["server"] == ("TestServer/%s" % test_server.__version__)


def test_custom_header_server(server):
    server.response["headers"] = (("Server", "Google"),)
    info = request(server.get_url())
    assert info.headers["server"] == "Google"


def test_options_method(server):
    server.response["data"] = b"abc"
    res = request(url=server.get_url(), method="OPTIONS")
    assert server.request["method"] == "OPTIONS"
    assert res.data == b"abc"


def test_multiple_start_stop_cycles():
    for cnt in range(30):
        server2 = TestServer(port=EXTRA_PORT + cnt)
        server2.start()
        try:
            server2.response["data"] = b"zorro"
            for _ in range(10):
                data = request(server2.get_url()).data
                assert data == b"zorro"
        finally:
            server2.stop()


def test_specific_port():
    server = TestServer(address="localhost", port=EXTRA_PORT)
    try:
        server.start()
        server.response["data"] = b"abc"
        data = request(server.get_url()).data
        assert data == b"abc"
    finally:
        server.stop()


def test_null_bytes(server):
    server.response_once["status"] = 302
    server.response_once["headers"] = [
        ("Location", server.get_url().rstrip("/") + "/\x00/")
    ]
    server.response["data"] = "zzz"
    res = request(server.get_url())
    assert res.data == b"zzz"
    assert unquote(server.request["path"]) == "/\x00/"


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
    server.response["headers"] = [
        ("Location", (server.get_url() + u"фыва").encode("utf-8"))
    ]
    request(server.get_url())


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
            "status": 201,
            "type": "response",
            "body": non_ascii_str,
            "headers": [
                ("method", "post"),
            ],
            "cookies": [
                ("foo", "bar"),
            ],
        }

    server.response["callback"] = get_callback
    info = request(server.get_url())
    assert info.headers["method"] == "get"
    assert info.data == b"Hello"

    server.response["post.callback"] = post_callback
    info = request(server.get_url(), b"key=val")
    assert info.headers["method"] == "post"
    assert info.headers["set-cookie"] == "foo=bar"
    assert info.data == non_ascii_str.encode("utf-8")
    assert info.status == 201


def test_response_data_iterable(server):
    server.response["data"] = iter(["foo", "bar"])
    res = request(server.get_url())
    assert res.data == b"foo"
    res = request(server.get_url())
    assert res.data == b"bar"
    res = request(server.get_url())
    assert res.status == 503


def test_response_data_invalid_type(server):
    server.response["data"] = 1
    res = request(server.get_url())
    assert res.status == 555
    assert b"must be string or iterable" in res.data


def test_stop_not_started_server():
    server = TestServer(port=EXTRA_PORT)
    server.stop()


def test_start_request_stop_same_port():
    server = TestServer(port=EXTRA_PORT)
    for _ in range(10):
        try:
            server.start()
            request(server.get_url())
        finally:
            server.stop()


def test_file_uploading(server):
    request(
        server.get_url(),
        fields={
            "image": ("emoji.png", b"zzz"),
        },
    )
    assert server.request["files"]["image"][0]["name"] == "image"


def test_callback_response_not_dict(server):
    def callback():
        return ["foo", "bar"]

    server.response["callback"] = callback
    res = request(server.get_url())
    assert res.status == 555
    assert b"is not a dict" in res.data


def test_callback_response_invalid_type(server):
    def callback():
        return {
            "foo": "bar",
        }

    server.response["callback"] = callback
    res = request(server.get_url())
    assert res.status == 555
    assert b"invalid type key" in res.data


def test_callback_response_invalid_key(server):
    def callback():
        return {
            "type": "response",
            "foo": "bar",
        }

    server.response["callback"] = callback
    res = request(server.get_url())
    assert res.status == 555
    assert b"contains invalid key" in res.data


def test_invalid_response_key(server):
    server.response["foo"] = "bar"
    with pytest.raises(TestServerError) as ex:
        server.get_url()
    assert "Invalid response key" in str(ex.value)
