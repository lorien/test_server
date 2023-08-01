from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, MutableMapping
from email.message import Message
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from pprint import pprint  # pylint: disable=unused-import
from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn
from threading import Event, Thread
from typing import Any, cast
from urllib.parse import parse_qsl, urljoin

from multipart import parse_form_data

from .const import TEST_SERVER_PACKAGE_VERSION
from .error import (
    InternalError,
    NoResponseError,
    RequestNotProcessedError,
    TestServerError,
    WaitTimeoutError,
)
from .structure import HttpHeaderStorage, HttpHeaderStream

__all__: list[str] = ["TestServer", "WaitTimeoutError", "Response", "Request"]

INTERNAL_ERROR_RESPONSE_STATUS: int = 555


class HandlerResult:
    __slots__ = ["status", "headers", "data"]

    def __init__(
        self,
        status: None | int = None,
        headers: None | HttpHeaderStorage = None,
        data: None | bytes = None,
    ) -> None:
        self.status = status if status is not None else 200
        self.headers = headers if headers else HttpHeaderStorage()
        self.data = data if data else b""


class Response:
    def __init__(
        self,
        callback: None | Callable[..., Mapping[str, Any]] = None,
        raw_callback: None | Callable[..., bytes] = None,
        data: None | bytes = None,
        headers: None | HttpHeaderStream = None,
        sleep: None | float = None,
        status: None | int = None,
    ) -> None:
        self.callback = callback
        self.raw_callback = raw_callback
        self.data = b"" if data is None else data
        self.headers = HttpHeaderStorage(headers)
        self.sleep = sleep
        self.status = 200 if status is None else status


class Request:  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        args: Mapping[str, Any],
        client_ip: str,
        cookies: SimpleCookie[Any],
        data: bytes,
        files: Mapping[str, Any],
        headers: HttpHeaderStream,
        method: str,
        path: str,
    ) -> None:
        self.args = args
        self.client_ip = client_ip
        self.cookies = cookies
        self.data = data
        self.files = files
        self.headers = HttpHeaderStorage(headers)
        self.method = method
        self.path = path


VALID_METHODS: list[str] = ["get", "post", "put", "delete", "options", "patch"]


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address: bool = True
    started: bool = False

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: Callable[
            [Any, Any, ThreadingTCPServer], BaseRequestHandler
        ],
        test_server: TestServer,
        **kwargs: Any,
    ) -> None:
        super().__init__(server_address, request_handler_class, **kwargs)
        self.test_server = test_server
        self.test_server.server_started.set()


class TestServerHandler(BaseHTTPRequestHandler):
    server: ThreadingTCPServer

    def process_multipart_files(
        self, request_data: bytes, headers: Message
    ) -> Mapping[str, list[Mapping[str, Any]]]:
        if not headers.get("Content-Type", "").startswith("multipart/form-data;"):
            return {}
        env = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": headers["Content-Type"],
            "wsgi.input": BytesIO(request_data),
        }
        if "content-length" in headers:
            env["content-length"] = headers["content-length"]
        _, files = parse_form_data(env)
        ret: MutableMapping[str, list[Mapping[str, Any]]] = {}
        for field_key, item in files.iterallitems():
            ret.setdefault(field_key, []).append(
                {
                    "name": field_key,
                    "content_type": item.content_type,
                    "filename": item.filename,
                    "content": item.raw,
                }
            )
        return ret

    def _read_request_data(self) -> bytes:
        content_len: int = int(self.headers["Content-Length"] or "0")
        return self.rfile.read(content_len)

    def _parse_qs_args(self) -> Mapping[str, Any]:
        try:
            qs = self.path.split("?")[1]
        except IndexError:
            qs = ""
        return dict(parse_qsl(qs))

    def _collect_request_data(self, method: str) -> Request:
        req_data = self._read_request_data()
        return Request(
            args=self._parse_qs_args(),
            client_ip=self.client_address[0],
            path=self.path.split("?")[0],
            data=req_data,
            method=method.upper(),
            cookies=SimpleCookie(self.headers["Cookie"]),
            files=self.process_multipart_files(req_data, self.headers),
            headers=dict(self.headers),
        )

    def process_callback_result(
        self, cb_res: Mapping[str, Any], result: HandlerResult
    ) -> None:
        if not isinstance(cb_res, dict):
            raise InternalError("Callback response is not a dict")
        if cb_res.get("type") != "response":
            raise InternalError(
                "Callback response has invalid type key: %s" % cb_res.get("type", "NA")
            )
        for key in cb_res:
            if key not in ("type", "status", "headers", "data"):
                raise InternalError("Callback response contains invalid key: %s" % key)
        if "status" in cb_res:
            result.status = cb_res["status"]
        if "headers" in cb_res:
            result.headers.extend(cb_res["headers"])
        if "data" in cb_res:
            if isinstance(cb_res["data"], bytes):
                result.data = cb_res["data"]
            else:
                raise InternalError('Callback repsponse field "data" must be bytes')

    def _process_required_response_headers(self, headers: HttpHeaderStorage) -> None:
        port = self.server.test_server.port
        headers.set("Listen-Port", str(port))
        if "content-type" not in headers:
            headers.set("Content-Type", "text/html; charset=utf-8")
        if "server" not in headers:
            headers.set("Server", "TestServer/%s" % TEST_SERVER_PACKAGE_VERSION)

    def _request_handler(self) -> None:
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
            self._process_required_response_headers(result.headers)
            self.write_response_data(result.status, result.headers, result.data)
        except Exception as ex:
            logging.exception("Unexpected error happend in test server request handler")
            self.write_response_data(
                INTERNAL_ERROR_RESPONSE_STATUS,
                HttpHeaderStorage(),
                str(ex).encode("utf-8"),
            )
        finally:
            test_srv.num_req_processed += 1

    def write_response_data(
        self, status: int, headers: HttpHeaderStorage, data: bytes
    ) -> None:
        self.send_response(status)
        for key, val in headers.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(data)

    def write_raw_response_data(self, data: bytes) -> None:
        self.wfile.write(data)
        # pylint: disable=attribute-defined-outside-init
        self._headers_buffer: list[str] = []

    # https://github.com/python/cpython/blob/main/Lib/http/server.py
    def send_response(self, code: int, message: None | str = None) -> None:
        """Do not send Server and Date headers.

        This method overrides standard method from super class.
        """
        self.log_request(code)
        self.send_response_only(code, message)

    do_GET = _request_handler  # noqa: N815
    do_POST = _request_handler  # noqa: N815
    do_PUT = _request_handler  # noqa: N815
    do_DELETE = _request_handler  # noqa: N815
    do_OPTIONS = _request_handler  # noqa: N815
    do_PATCH = _request_handler  # noqa: N815


class TestServer:  # pylint: disable=too-many-instance-attributes
    __test__ = False  # for pytest ignore this class

    def __init__(self, address: str = "127.0.0.1", port: int = 0) -> None:
        self.server_started: Event = Event()
        self._requests: list[Request] = []
        self._responses: MutableMapping[
            None | str, list[MutableMapping[str, Any]]
        ] = defaultdict(list)
        self.port: None | int = None
        self._config_port: int = port
        self.address: str = address
        self._thread: None | Thread = None
        self._server: None | ThreadingTCPServer = None
        self._started: Event = Event()
        self.num_req_processed: int = 0
        self.reset()

    def _thread_server(self) -> None:
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

    def add_request(self, req: Request) -> None:
        self._requests.append(req)

    def reset(self) -> None:
        self.num_req_processed = 0
        self._requests.clear()
        self._responses.clear()

    def start(self, daemon: bool = True) -> None:
        """Start the HTTP server."""
        self._thread = Thread(
            target=self._thread_server,
        )
        self._thread.daemon = daemon
        self._thread.start()
        self.wait_server_started()
        self.port = cast(ThreadingTCPServer, self._server).socket.getsockname()[1]

    def wait_server_started(self) -> None:
        # I could not foind another way
        # to handle multiple socket issues
        # other than taking some sleep
        time.sleep(0.01)
        self.server_started.wait()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def get_url(self, path: str = "", port: None | int = None) -> str:
        """Build URL that is served by HTTP server."""
        if port is None:
            port = cast(int, self.port)
        return urljoin("http://%s:%d" % (self.address, port), path)

    def wait_request(self, timeout: float) -> None:
        """Stupid implementation that eats CPU."""
        start: float = time.time()
        while True:
            if self.num_req_processed:
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError("No request processed in %d seconds" % timeout)

    def request_is_done(self) -> bool:
        return self.num_req_processed > 0

    def get_request(self) -> Request:
        try:
            return self._requests[-1]
        except IndexError as ex:
            raise RequestNotProcessedError("Request has not been processed") from ex

    @property
    def request(self) -> Request:
        return self.get_request()

    def add_response(
        self, resp: Response, count: int = 1, method: None | str = None
    ) -> None:
        assert method is None or isinstance(method, str)
        assert count < 0 or count > 0
        if method and method not in VALID_METHODS:
            raise TestServerError("Invalid method: %s" % method)
        self._responses[method].append(
            {
                "count": count,
                "response": resp,
            },
        )

    def get_response(self, method: str) -> Response:
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
                except IndexError as ex:
                    raise NoResponseError("No response available") from ex
            if item["count"] == -1:
                return cast(Response, item["response"])
            item["count"] -= 1
            if item["count"] < 1:
                scope.pop(0)
            return cast(Response, item["response"])
