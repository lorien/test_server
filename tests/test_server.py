# pylint: disable=consider-using-f-string
from pprint import pprint  # pylint: disable=unused-import
from threading import Thread
import time
from urllib.parse import unquote, quote

from urllib3 import PoolManager
from urllib3.util.retry import Retry
from urllib3.response import HTTPResponse
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


def request(
    url, data=None, method=None, headers=None, fields=None, retries_redirect=10
) -> HTTPResponse:
    params = {
        "headers": headers,
        "timeout": NETWORK_TIMEOUT,
        "retries": Retry(
            total=None,
            connect=0,
            read=0,
            redirect=retries_redirect,
            other=0,
        ),
        "fields": fields,
    }
    if data:
        assert isinstance(data, bytes)
        params["body"] = data
    if not method:
        method = "POST" if (data or fields) else "GET"
    print("~" * 10, method, url, params)
    return pool.request(method, url, **params)


# WTF: urllib3 makes TWO requests :-/
# def test_non_ascii_header(server: TestServer) -> None:
#    server.add_response(Response(headers=[("z", server.get_url() + "фыва")]))
#    res = request(server.get_url(), retries_redirect=False)
#    print(res.headers)


def test_non_ascii_header(server: TestServer) -> None:
    server.add_response(
        Response(status=301, headers=[("Location", server.get_url(quote("фыва")))])
    )
    server.add_response(Response())
    request(server.get_url())
    assert quote("фыва") in server.get_request().path


def test_get(server: TestServer) -> None:
    valid_data = b"zorro"
    server.add_response(Response(data=valid_data))
    res = request(server.get_url())
    assert res.data == valid_data


def test_non_utf_request_data(server: TestServer) -> None:
    server.add_response(Response(data=b"abc"))
    res = request(url=server.get_url(), data="конь".encode("cp1251"))
    assert res.data == b"abc"
    assert server.get_request().data == "конь".encode("cp1251")


def test_request_client_ip(server: TestServer) -> None:
    server.add_response(Response())
    request(server.get_url())
    assert server.address == server.get_request().client_ip


def test_path(server: TestServer) -> None:
    server.add_response(Response())
    request(server.get_url("/foo?bar=1"))
    assert server.get_request().path == "/foo"
    assert server.get_request().args["bar"] == "1"


def test_post(server: TestServer) -> None:
    server.add_response(Response(data=b"abc"), method="post")
    res = request(server.get_url(), b"req-data")
    assert res.data == b"abc"
    assert server.get_request().data == b"req-data"


def test_response_once_specific_method(server: TestServer) -> None:
    server.add_response(Response(data=b"bar"), method="get")
    server.add_response(Response(data=b"foo"))
    assert request(server.get_url()).data == b"bar"


def test_request_headers(server: TestServer) -> None:
    server.add_response(Response())
    request(server.get_url(), headers={"Foo": "Bar"})
    assert server.get_request().headers.get("foo") == "Bar"


def test_response_once_reset_headers(server: TestServer) -> None:
    server.add_response(Response(headers=[("foo", "bar")]))
    server.reset()
    res = request(server.get_url())
    assert res.status == 555
    assert b"No response" in res.data


def test_method_sleep(server: TestServer) -> None:
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


def test_request_done_after_start(server: TestServer) -> None:
    server = TestServer(port=EXTRA_PORT)
    try:
        server.start()
        assert not server.request_is_done()
    finally:
        server.stop()


def test_request_done(server: TestServer) -> None:
    assert not server.request_is_done()
    server.add_response(Response())
    request(server.get_url())
    assert server.request_is_done()


def test_wait_request(server: TestServer) -> None:
    server.add_response(Response(data=b"foo"))

    def worker():
        time.sleep(1)
        request(server.get_url("?method=test-wait-request"))

    th = Thread(target=worker)
    th.start()
    with pytest.raises(WaitTimeoutError):
        server.wait_request(0.5)
    server.wait_request(2)
    th.join()


def test_request_cookies(server: TestServer) -> None:
    server.add_response(Response())
    request(url=server.get_url(), headers={"Cookie": "foo=bar"})
    assert server.get_request().cookies["foo"].value == "bar"


def test_default_header_content_type(server: TestServer) -> None:
    server.add_response(Response())
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=utf-8"


def test_custom_header_content_type(server: TestServer) -> None:
    server.add_response(
        Response(headers=[("Content-Type", "text/html; charset=koi8-r")])
    )
    info = request(server.get_url())
    assert info.headers["content-type"] == "text/html; charset=koi8-r"


def test_default_header_server(server: TestServer) -> None:
    server.add_response(Response())
    info = request(server.get_url())
    assert info.headers["server"] == ("TestServer/%s" % test_server.__version__)


def test_custom_header_server(server: TestServer) -> None:
    server.add_response(Response(headers=[("Server", "Google")]))
    info = request(server.get_url())
    assert info.headers["server"] == "Google"


def test_options_method(server: TestServer) -> None:
    server.add_response(Response(data=b"abc"))
    res = request(url=server.get_url(), method="OPTIONS")
    assert server.get_request().method == "OPTIONS"
    assert res.data == b"abc"


def test_multiple_start_stop_cycles() -> None:
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


def test_specific_port() -> None:
    server = TestServer(address="localhost", port=EXTRA_PORT)
    try:
        server.start()
        server.add_response(Response(data=b"abc"))
        data = request(server.get_url()).data
        assert data == b"abc"
    finally:
        server.stop()


def test_null_bytes(server: TestServer) -> None:
    server.add_response(
        Response(
            status=302,
            headers=[
                ("Location", server.get_url().rstrip("/") + "/\x00/"),
            ],
        )
    )
    server.add_response(Response(data=b"zzz"))
    res = request(server.get_url())
    assert res.data == b"zzz"
    assert unquote(server.get_request().path) == "/\x00/"


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


def test_callback(server: TestServer) -> None:
    def get_callback():
        return {
            "type": "response",
            "data": b"Hello",
            "headers": [
                ("method", "get"),
            ],
        }

    def post_callback():
        return {
            "type": "response",
            "status": 201,
            "data": b"hey",
            "headers": [
                ("method", "post"),
                ("set-cookie", "foo=bar"),
            ],
        }

    server.add_response(Response(callback=get_callback))
    server.add_response(Response(callback=post_callback), method="post")

    info = request(server.get_url())
    assert info.headers.get("method") == "get"
    assert info.data == b"Hello"

    info = request(server.get_url(), b"key=val")
    assert info.headers["method"] == "post"
    assert info.headers["set-cookie"] == "foo=bar"
    assert info.data == b"hey"
    assert info.status == 201


def test_response_data_invalid_type(server: TestServer) -> None:
    server.add_response(Response(data=1))  # type: ignore
    res = request(server.get_url())
    assert res.status == 555
    assert b"must be bytes" in res.data


def test_stop_not_started_server() -> None:
    server = TestServer(port=EXTRA_PORT)
    server.stop()


def test_start_request_stop_same_port() -> None:
    server = TestServer(port=EXTRA_PORT)
    for _ in range(10):
        try:
            server.start()
            server.add_response(Response())
            request(server.get_url())
        finally:
            server.stop()


def test_file_uploading(server: TestServer) -> None:
    server.add_response(Response())
    request(
        server.get_url(),
        fields={
            "image": ("emoji.png", b"zzz"),
        },
    )
    assert server.get_request().files["image"][0]["name"] == "image"


def test_callback_response_not_dict(server: TestServer) -> None:
    def callback():
        return ["foo", "bar"]

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"is not a dict" in res.data


def test_callback_response_invalid_type(server: TestServer) -> None:
    def callback():
        return {
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"invalid type key" in res.data


def test_callback_response_invalid_key(server: TestServer) -> None:
    def callback():
        return {
            "type": "response",
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"contains invalid key" in res.data


def test_callback_data_non_bytes(server: TestServer) -> None:
    def callback():
        return {
            "type": "response",
            "data": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == 555
    assert b"must be bytes" in res.data


def test_invalid_response_key() -> None:
    with pytest.raises(TypeError) as ex:
        # pylint: disable=unexpected-keyword-arg
        Response(foo="bar")  # type: ignore
    assert "unexpected keyword argument" in str(ex.value)


def test_get_request_no_request(server: TestServer) -> None:
    with pytest.raises(RequestNotProcessed):
        server.get_request()


def test_add_response_invalid_method(server: TestServer) -> None:
    with pytest.raises(TestServerError) as ex:
        server.add_response(Response(), method="foo")
    assert "Invalid method" in str(ex.value)


def test_add_response_count_minus_one(server: TestServer) -> None:
    server.add_response(Response(), count=-1)
    for _ in range(3):
        assert 200 == request(server.get_url()).status


def test_add_response_count_one_default(server: TestServer) -> None:
    server.add_response(Response())
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data

    server.add_response(Response(), count=1)
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data


def test_add_response_count_two(server: TestServer) -> None:
    server.add_response(Response(), count=2)
    assert 200 == request(server.get_url()).status
    assert 200 == request(server.get_url()).status
    assert b"No response" in request(server.get_url()).data


def test_raw_callback(server):
    def callback():
        return b"HTTP/1.1 200 OK\nFoo: Bar\nGaz: Baz\nContent-Length: 5\n\nhello"

    server.add_response(Response(raw_callback=callback))
    res = request(server.get_url())
    assert "foo" in res.headers


def test_raw_callback_invalid_type(server):
    def callback():
        return "hey"

    server.add_response(Response(raw_callback=callback))
    res = request(server.get_url())
    assert b"must return bytes" in res.data
