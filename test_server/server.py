# from __future__ import annotations

import logging
import time
from collections import defaultdict
from email.message import Message
from pprint import pprint  # pylint: disable=unused-import
from threading import Event, Thread
from typing import Any, cast

import six
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler

# pylint: disable=import-error
from six.moves.collections_abc import Callable, Mapping, MutableMapping

# pylint: enable=import-error
from six.moves.http_cookies import SimpleCookie
from six.moves.socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn
from six.moves.urllib.parse import parse_qsl, urljoin

from .const import TEST_SERVER_PACKAGE_VERSION
from .error import (
    InternalError,
    NoResponseError,
    RequestNotProcessedError,
    TestServerError,
    WaitTimeoutError,
)
from .multipart import parse_content_header, parse_multipart_form
from .structure import HttpHeaderStorage, HttpHeaderStream

__all__ = ["Request", "Response", "TestServer", "WaitTimeoutError"]  # type: list[str]
LOG = logging.getLogger()
INTERNAL_ERROR_RESPONSE_STATUS = 555  # type: int


class HandlerResult(object):
    __slots__ = ["data", "headers", "status"]

    def __init__(
        self,
        status=None,  # type: None | int
        headers=None,  # type: None | HttpHeaderStorage
        data=None,  # type: None | bytes
    ):
        # type: (...) -> None
        self.status = status if status is not None else 200
        self.headers = headers if headers else HttpHeaderStorage()
        self.data = data if data else b""


class Response(object):
    def __init__(
        self,
        callback=None,  # type: None | Callable[..., Mapping[str, Any]]
        raw_callback=None,  # type: None | Callable[..., bytes]
        data=None,  # type: None | bytes
        headers=None,  # type: None | HttpHeaderStream
        sleep=None,  # type: None | float
        status=None,  # type: None | int
    ):
        # type: (...) -> None
        self.callback = callback
        self.raw_callback = raw_callback
        self.data = b"" if data is None else data
        self.headers = HttpHeaderStorage(headers)
        self.sleep = sleep
        self.status = 200 if status is None else status


class Request(object):  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        args,  # type: Mapping[str, Any]
        client_ip,  # type: str
        cookies,  # type: SimpleCookie
        data,  # type: bytes
        files,  # type: Mapping[str, Any]
        headers,  # type: HttpHeaderStream
        method,  # type: str
        path,  # type: str
    ):
        # type: (...) -> None
        self.args = args
        self.client_ip = client_ip
        self.cookies = cookies
        self.data = data
        self.files = files
        self.headers = HttpHeaderStorage(headers)
        self.method = method
        self.path = path


VALID_METHODS = ["get", "post", "put", "delete", "options", "patch"]  # type: list[str]


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True  # type: bool
    started = False  # type: bool

    # fmt: off
    def __init__(
        self,
        server_address,  # type: tuple[str, int]
        # pylint: disable=line-too-long
        request_handler_class,  # type: Callable[[Any, Any, ThreadingTCPServer], BaseRequestHandler]
        # pylint: enable=line-too-long
        test_server,  # type: TestServer
        **kwargs # type: Any
    ):
    # fmt: on
        # type: (...) -> None
        TCPServer.__init__(self, server_address, request_handler_class, **kwargs)
        self.test_server = test_server
        self.test_server.server_started.set()


class TestServerHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        # type: (Any, Any, ThreadingTCPServer) -> None
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)
        # This assignment is only to ceclare type of self.server attribute
        self.server = server  # type: ThreadingTCPServer

    def process_multipart_files(
        self,
        request_data,  # type: bytes
        headers,  # type: Message
    ):
        # type: (...) -> Mapping[str, list[Mapping[str, Any]]]
        if not headers.get("Content-Type", "").startswith("multipart/form-data;"):
            return {}
        _content_type, options = parse_content_header(headers["Content-Type"])
        files = parse_multipart_form(request_data, options.get("boundary", "").encode())
        ret = {}  # type: MutableMapping[str, list[Mapping[str, Any]]]
        for field_key, item in files.items():
            ret.setdefault(field_key, []).append(
                {
                    "name": field_key,
                    "content_type": item["content_type"],
                    "filename": item["filename"],
                    "content": item["content"],
                }
            )
        return ret

    def _read_request_data(self):
        # type: () -> bytes
        content_len = int(self.headers.get("Content-Length", "0"))  # type: int
        return self.rfile.read(content_len)

    def _parse_qs_args(self):
        # type: () -> Mapping[str, Any]
        try:
            qs = self.path.split("?")[1]
        except IndexError:
            qs = ""
        return dict(parse_qsl(qs))

    def _collect_request_data(
        self,
        method,  # type: str
    ):
        # type: (...) -> Request
        req_data = self._read_request_data()
        return Request(
            args=self._parse_qs_args(),
            client_ip=self.client_address[0],
            path=self.path.split("?")[0],
            data=req_data,
            method=method.upper(),
            cookies=SimpleCookie(self.headers.get("Cookie", "")),
            files=self.process_multipart_files(req_data, self.headers),
            headers=dict(self.headers),
        )

    def process_callback_result(
        self,
        cb_res,  # type: Mapping[str, Any]
        result,  # type: HandlerResult
    ):
        # type: (...) -> None
        if not isinstance(cb_res, dict):
            raise InternalError("Callback response is not a dict")
        if cb_res.get("type") != "response":
            raise InternalError(
                "Callback response has invalid type key: {}".format(
                    cb_res.get("type", "NA")
                )
            )
        for key in cb_res:
            if key not in ("type", "status", "headers", "data"):
                raise InternalError(
                    "Callback response contains invalid key: {}".format(key)
                )
        if "status" in cb_res:
            result.status = cb_res["status"]
        if "headers" in cb_res:
            result.headers.extend(cb_res["headers"])
        if "data" in cb_res:
            if isinstance(cb_res["data"], bytes):
                result.data = cb_res["data"]
            else:
                raise InternalError('Callback repsponse field "data" must be bytes')

    def _add_required_response_headers(
        self,
        headers,  # type: HttpHeaderStorage
    ):
        # type: (...) -> None
        port = self.server.test_server.port
        headers.set("Listen-Port", str(port))
        if "content-type" not in headers:
            headers.set("Content-Type", "text/html; charset=utf-8")
        if "server" not in headers:
            headers.set("Server", "TestServer/{}".format(TEST_SERVER_PACKAGE_VERSION))

    def _request_handler(self):
        # type: () -> None
        try:
            test_srv = self.server.test_server
            method = self.command.lower()
            resp = test_srv.get_response(method)
            if resp.sleep:
                time.sleep(resp.sleep)
            test_srv.add_request(self._collect_request_data(method))
            result = HandlerResult()
            if resp.raw_callback:
                data = resp.raw_callback()
                if isinstance(data, bytes):
                    self.write_raw_response_data(data)
                    return
                raise InternalError(  # noqa: TRY301
                    "Raw callback must return bytes data"
                )
            if resp.callback:
                self.process_callback_result(resp.callback(), result)
            else:
                result.status = resp.status
                result.headers.extend(resp.headers.items())
                data = resp.data
                if isinstance(data, bytes):
                    result.data = data
                else:
                    raise InternalError(  # noqa: TRY301
                        'Response parameter "data" must be bytes'
                    )
            self._write_response_data(result.status, result.headers, result.data)
        except Exception as ex:
            LOG.exception("Unexpected error happend in test server request handler")
            self._write_response_data(
                INTERNAL_ERROR_RESPONSE_STATUS,
                HttpHeaderStorage(),
                str(ex).encode("utf-8"),
            )
        finally:
            test_srv.num_req_processed += 1

    def _write_response_data(self, status, headers, data):
        # type: (int, HttpHeaderStorage, six.binary_type) -> None
        self._add_required_response_headers(headers)
        self.send_response(status)
        for key, val in headers.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(data)

    def write_raw_response_data(
        self,
        data,  # type: bytes
    ):
        # type: (...) -> None
        self.wfile.write(data)
        # pylint: disable=attribute-defined-outside-init
        self._headers_buffer = []  # type: list[str]

    # https://github.com/python/cpython/blob/main/Lib/http/server.py
    def send_response(
        self,
        code,  # type: int
        message=None,  # type: None | str
    ):
        # type: (...) -> None
        """Do not send Server and Date headers.

        This method overrides standard method from super class.
        """
        self.log_request(code)
        self.send_response_only(code, message)

    def send_response_only(self, code, message=None):
        # type: (int, None|str) -> None
        if message is None:
            message = self.responses[code][0] if code in self.responses else ""
        if self.request_version != "HTTP/0.9":
            # fmt: off
            self.wfile.write((u"{} {:d} {}\r\n" .format (
                self.protocol_version, code, message)).encode("latin")
            )
            # fmt: on

    do_GET = _request_handler  # noqa: N815
    do_POST = _request_handler  # noqa: N815
    do_PUT = _request_handler  # noqa: N815
    do_DELETE = _request_handler  # noqa: N815
    do_OPTIONS = _request_handler  # noqa: N815
    do_PATCH = _request_handler  # noqa: N815


class TestServer(object):  # pylint: disable=too-many-instance-attributes
    __test__ = False  # for pytest ignore this class

    def __init__(
        self,
        address="127.0.0.1",  # type: str
        port=0,  # type: int
    ):
        # type: (...) -> None
        self.server_started = Event()  # type: Event
        self._requests = []  # type: list[Request]
        self._responses = defaultdict(
            list
        )  # type: MutableMapping[None | str, list[MutableMapping[str, Any]]]
        self.port = None  # type: None | int
        self._config_port = port  # type: int
        self.address = address  # type: str
        self._thread = None  # type: None | Thread
        self._server = None  # type: None | ThreadingTCPServer
        self._started = Event()  # type: Event
        self.num_req_processed = 0  # type: int
        self.reset()

    def _thread_server(self):
        # type: () -> None
        """Ask HTTP server start processing requests.

        This function is supposed to be run in separate thread.
        """
        self._server = ThreadingTCPServer(
            (self.address, self._config_port), TestServerHandler, test_server=self
        )
        self._server.serve_forever(poll_interval=0.1)

    # ****************
    # Public Interface
    # ****************

    def add_request(
        self,
        req,  # type: Request
    ):
        # type: (...) -> None
        self._requests.append(req)

    def reset(self):
        # type: () -> None
        self.num_req_processed = 0
        # self._requests.clear()
        del self._requests[:]
        self._responses.clear()

    def start(
        self,
        daemon=True,  # type: bool
    ):
        # type: (...) -> None
        """Start the HTTP server."""
        self._thread = Thread(
            target=self._thread_server,
        )
        self._thread.daemon = daemon
        self._thread.start()
        self.wait_server_started()
        self.port = cast(ThreadingTCPServer, self._server).socket.getsockname()[1]

    def wait_server_started(self):
        # type: () -> None
        # I could not foind another way
        # to handle multiple socket issues
        # other than taking some sleep
        time.sleep(0.01)
        self.server_started.wait()

    def stop(self):
        # type: () -> None
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def get_url(
        self,
        path="",  # type: str
        port=None,  # type: None | int
    ):
        # type: (...) -> str
        """Build URL that is served by HTTP server."""
        if port is None:
            port = cast(int, self.port)
        return urljoin("http://{}:{:d}".format(self.address, port), path)

    def wait_request(
        self,
        timeout,  # type: float
    ):
        # type: (...) -> None
        """Stupid implementation that eats CPU."""
        start = time.time()  # type: float
        while True:
            if self.num_req_processed:
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError(
                    "No request processed in {} seconds".format(timeout)
                )

    def request_is_done(self):
        # type: () -> bool
        return self.num_req_processed > 0

    def get_request(self):
        # type: () -> Request
        try:
            return self._requests[-1]
        except IndexError:
            # TODO: from ex
            raise RequestNotProcessedError("Request has not been processed")

    @property
    def request(self):
        # type: () -> Request
        return self.get_request()

    def add_response(
        self,
        resp,  # type: Response
        count=1,  # type: int
        method=None,  # type: None | str
    ):
        # type: (...) -> None
        assert method is None or isinstance(method, str)
        assert count < 0 or count > 0
        if method and method not in VALID_METHODS:
            raise TestServerError("Invalid method: {}".format(method))
        self._responses[method].append(
            {
                "count": count,
                "response": resp,
            },
        )

    def get_response(
        self,
        method,  # type: str
    ):
        # type: (...) -> Response
        while True:
            item = None
            scope = None
            try:
                scope = self._responses[method]
                item = scope[0]
            except IndexError:
                try:
                    scope = self._responses[None]
                    item = scope[0]
                except IndexError:
                    # TODO: from ex
                    raise NoResponseError("No response available")
            if item["count"] == -1:
                return cast(Response, item["response"])
            item["count"] -= 1
            if item["count"] < 1:
                scope.pop(0)
            return cast(Response, item["response"])
