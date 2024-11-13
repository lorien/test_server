from __future__ import annotations

import time
from pprint import pprint  # pylint: disable=unused-import
from threading import Thread
from typing import Any
from urllib.parse import quote, unquote

import pytest
from urllib3 import PoolManager
from urllib3.response import BaseHTTPResponse
from urllib3.util.retry import Retry

import test_server
from test_server import (
    Request,
    RequestNotProcessedError,
    Response,
    TestServer,
    TestServerError,
    WaitTimeoutError,
)
from test_server.server import INTERNAL_ERROR_RESPONSE_STATUS

from .util import fixture_global_server, fixture_server  # pylint: disable=unused-import

NETWORK_TIMEOUT = 1
SPECIFIC_TEST_PORT = 10100
HTTP_STATUS_OK = 200
pool = PoolManager()


def request(
    url: str,
    data: None | bytes = None,
    method: None | str = None,
    headers: None | dict[str, Any] = None,
    fields: None | dict[str, Any] = None,
    retries_redirect: int = 10,
) -> BaseHTTPResponse:
    params: dict[str, Any] = {
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
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
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
    server = TestServer()
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

    def worker() -> None:
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
    for _ in range(30):
        server = TestServer()
        server.start()
        try:
            server.add_response(Response(data=b"zorro"), count=10)
            for _ in range(10):
                res = request(server.get_url())
                assert res.data == b"zorro"
        finally:
            server.stop()


def test_specific_port() -> None:
    server = TestServer(address="localhost", port=SPECIFIC_TEST_PORT)
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


def test_callback(server: TestServer) -> None:
    def get_callback() -> dict[str, Any]:
        return {
            "type": "response",
            "data": b"Hello",
            "headers": [
                ("method", "get"),
            ],
        }

    def post_callback() -> dict[str, Any]:
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
    assert info.status == 201  # noqa: PLR2004


def test_response_data_invalid_type(server: TestServer) -> None:
    server.add_response(Response(data=1))  # type: ignore[arg-type]
    res = request(server.get_url())
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
    assert b"must be bytes" in res.data


def test_stop_not_started_server() -> None:
    server = TestServer()
    server.stop()


def test_start_request_stop_same_port() -> None:
    server = TestServer()
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
    img_file = server.get_request().files["image"][0]
    assert img_file["name"] == "image"


def test_callback_response_not_dict(server: TestServer) -> None:
    def callback() -> list[str]:
        return ["foo", "bar"]

    server.add_response(Response(callback=callback))  # type: ignore[arg-type]
    res = request(server.get_url())
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
    assert b"is not a dict" in res.data


def test_callback_response_invalid_type(server: TestServer) -> None:
    def callback() -> dict[str, Any]:
        return {
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
    assert b"invalid type key" in res.data


def test_callback_response_invalid_key(server: TestServer) -> None:
    def callback() -> dict[str, Any]:
        return {
            "type": "response",
            "foo": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
    assert b"contains invalid key" in res.data


def test_callback_data_non_bytes(server: TestServer) -> None:
    def callback() -> dict[str, Any]:
        return {
            "type": "response",
            "data": "bar",
        }

    server.add_response(Response(callback=callback))
    res = request(server.get_url())
    assert res.status == INTERNAL_ERROR_RESPONSE_STATUS
    assert b"must be bytes" in res.data


def test_invalid_response_key() -> None:
    with pytest.raises(TypeError) as ex:
        # pylint: disable=unexpected-keyword-arg
        Response(foo="bar")  # type: ignore[call-arg]
    assert "unexpected keyword argument" in str(ex.value)


def test_get_request_no_request(server: TestServer) -> None:
    with pytest.raises(RequestNotProcessedError):
        server.get_request()


def test_add_response_invalid_method(server: TestServer) -> None:
    with pytest.raises(TestServerError) as ex:
        server.add_response(Response(), method="foo")
    assert "Invalid method" in str(ex.value)


def test_add_response_count_minus_one(server: TestServer) -> None:
    server.add_response(Response(), count=-1)
    for _ in range(3):
        assert request(server.get_url()).status == HTTP_STATUS_OK


def test_add_response_count_one_default(server: TestServer) -> None:
    server.add_response(Response())
    assert request(server.get_url()).status == HTTP_STATUS_OK
    assert b"No response" in request(server.get_url()).data

    server.add_response(Response(), count=1)
    assert request(server.get_url()).status == HTTP_STATUS_OK
    assert b"No response" in request(server.get_url()).data


def test_add_response_count_two(server: TestServer) -> None:
    server.add_response(Response(), count=2)
    assert request(server.get_url()).status == HTTP_STATUS_OK
    assert request(server.get_url()).status == HTTP_STATUS_OK
    assert b"No response" in request(server.get_url()).data


def test_raw_callback(server: TestServer) -> None:
    def callback() -> bytes:
        return b"HTTP/1.0 200 OK\nFoo: Bar\nGaz: Baz\nContent-Length: 5\n\nhello"

    server.add_response(Response(raw_callback=callback))
    res = request(server.get_url())
    assert "foo" in res.headers
    assert res.data == b"hello"


def test_raw_callback_invalid_type(server: TestServer) -> None:
    def callback() -> str:
        return "hey"

    server.add_response(Response(raw_callback=callback))  # type: ignore[arg-type]
    res = request(server.get_url())
    assert b"must return bytes" in res.data


def test_request_property(server: TestServer) -> None:
    server.add_response(Response())
    request(server.get_url())
    assert isinstance(server.request, Request)


def test_put_request(server: TestServer) -> None:
    server.add_response(Response())
    request(server.get_url(), data=b"foo", method="put")
    assert server.request.method == "PUT"
