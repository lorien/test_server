# pylint: disable=consider-using-f-string
from pprint import pprint  # pylint: disable=unused-import
import time
from collections import defaultdict
from threading import Thread, Event
import cgi
from io import BytesIO
import logging
from typing import Optional, Callable, List

from socketserver import ThreadingMixIn, TCPServer
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urljoin, parse_qsl

from .version import TEST_SERVER_VERSION
from .error import (
    TestServerError,
    WaitTimeoutError,
    InternalError,
    RequestNotProcessed,
    NoResponse,
)
from .structure import HttpHeaderStorage, HttpHeaderStream

__all__: list = ["TestServer", "WaitTimeoutError", "Response"]

INTERNAL_ERROR_RESPONSE_STATUS: int = 555


class Response(object):
    def __init__(
        self,
        callback: Optional[Callable] = None,
        raw_callback: Optional[Callable] = None,
        data: Optional[bytes] = None,
        headers: Optional[HttpHeaderStream] = None,
        sleep: Optional[float] = None,
        status: Optional[int] = None,
    ) -> None:
        self.callback = callback
        self.raw_callback = raw_callback
        self.data = b"" if data is None else data
        self.headers = HttpHeaderStorage(headers)
        self.sleep = sleep
        self.status = 200 if status is None else status


class Request(object):
    def __init__(
        self,
        args: Optional[dict] = None,
        client_ip: Optional[str] = None,
        cookies: Optional[SimpleCookie] = None,
        data: Optional[bytes] = None,
        files: Optional[dict] = None,
        headers: Optional[HttpHeaderStream] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
    ):
        self.args = {} if args is None else args
        self.client_ip = {} if client_ip is None else client_ip
        self.cookies = cookies
        self.data = None if data is None else data
        self.files = {} if files is None else files
        self.headers = HttpHeaderStorage(headers)
        self.method = None if method is None else method
        self.path = None if path is None else path


VALID_METHODS: List[str] = ["get", "post", "put", "delete", "options", "patch"]


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True
    started = False

    def __init__(self, server_address, RequestHandlerClass, test_server=None, **kwargs):
        super().__init__(server_address, RequestHandlerClass, **kwargs)
        self.test_server = test_server
        self.test_server.server_started.set()


class TestServerHandler(BaseHTTPRequestHandler):
    def _collect_request_data(self, method):
        request = Request()
        request.client_ip = self.client_address[0]
        try:
            qs = self.path.split("?")[1]
        except IndexError:
            qs = ""
        params = dict(parse_qsl(qs))
        for key, val in params.items():
            request.args[key] = val
        for key, val in self.headers.items():
            request.headers.add(key, val)

        path = self.path
        request.path = path.split("?")[0]
        request.method = method.upper()

        request.cookies = SimpleCookie(self.headers["Cookie"])

        clen = int(self.headers["Content-Length"] or "0")
        request_data = self.rfile.read(clen)
        request.data = request_data

        ctype = self.headers["Content-Type"]
        if ctype and ctype.split(";")[0] == "multipart/form-data":
            form = cgi.FieldStorage(
                fp=BytesIO(request_data),
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers["Content-Type"],
                },
            )
            for field_key in form.keys():  # pylint: disable=consider-using-dict-items
                box = form[field_key]
                for field in box if isinstance(box, list) else [box]:
                    request.files.setdefault(field_key, []).append(
                        {
                            "name": field_key,
                            # "raw_filename": None,
                            "content_type": field.type,
                            "filename": field.filename,
                            "content": field.file.read(),
                        }
                    )

        return request

    def _request_handler(self):
        try:
            test_srv = self.server.test_server  # pytype: disable=attribute-error
            method = self.command.lower()
            resp = test_srv.get_response(method)
            if resp.sleep:
                time.sleep(resp.sleep)
            test_srv.add_request(self._collect_request_data(method))

            result = {
                "status": 200,
                "headers": HttpHeaderStorage(),
                "data": b"",
            }

            if resp.raw_callback:
                data = resp.raw_callback()
                if isinstance(data, bytes):
                    self.write_raw_response_data(data)
                else:
                    raise InternalError("Raw callback must return bytes data")

            if resp.callback:
                cb_res = resp.callback()
                if not isinstance(cb_res, dict):
                    raise InternalError("Callback response is not a dict")
                elif cb_res.get("type") == "response":
                    for key in cb_res:
                        if key not in (
                            "type",
                            "status",
                            "headers",
                            "data",
                        ):
                            raise InternalError(
                                "Callback response contains invalid key: %s" % key
                            )
                    if "status" in cb_res:
                        result["status"] = cb_res["status"]
                    if "headers" in cb_res:
                        result["headers"].extend(cb_res["headers"])
                    if "data" in cb_res:
                        if isinstance(cb_res["data"], bytes):
                            result["data"] = cb_res["data"]
                        else:
                            raise InternalError(
                                'Callback repsponse field "data" must be bytes'
                            )
                else:
                    raise InternalError(
                        "Callback response has invalid type key: %s"
                        % cb_res.get("type", "NA")
                    )
            else:
                result["status"] = resp.status
                result["headers"].extend(resp.headers.items())
                data = resp.data
                if isinstance(data, bytes):
                    result["data"] = data
                else:
                    raise InternalError('Response parameter "data" must be bytes')

            port = self.server.test_server.port  # pytype: disable=attribute-error
            result["headers"].set("Listen-Port", str(port))
            if "content-type" not in result["headers"]:
                result["headers"].set("Content-Type", "text/html; charset=utf-8")
            if "server" not in result["headers"]:
                result["headers"].set("Server", "TestServer/%s" % TEST_SERVER_VERSION)

            self.write_response_data(
                result["status"], result["headers"], result["data"]
            )
        except Exception as ex:  # pylint: disable=broad-except
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
        print(list(headers.items()))
        for key, val in headers.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(data)

    def write_raw_response_data(self, data: bytes) -> None:
        self.wfile.write(data)
        # pylint: disable=attribute-defined-outside-init
        self._headers_buffer: List[str] = []

    # https://github.com/python/cpython/blob/main/Lib/http/server.py
    def send_response(self, code: int, message: Optional[str] = None) -> None:
        """
        Custom method which does not send Server and Date headers

        This method overrides standard method from super class.
        """
        self.log_request(code)
        self.send_response_only(code, message)

    do_GET = _request_handler
    do_POST = _request_handler
    do_PUT = _request_handler
    do_DELETE = _request_handler
    do_OPTIONS = _request_handler
    do_PATCH = _request_handler


class TestServer(object):
    def __init__(self, address="127.0.0.1", port=0):
        self.server_started = Event()
        self._requests = []
        self._responses = defaultdict(list)
        self.port = None
        self._config_port = port
        self.address = address
        self._handler = None
        self._thread = None
        self._server = None
        self._started = Event()
        self.num_req_processed = 0
        self.reset()

    def _thread_server(self):
        """Ask HTTP server start processing requests

        This function is supposed to be run in separate thread.
        """

        self._server = ThreadingTCPServer(
            (self.address, self._config_port), TestServerHandler, test_server=self
        )
        self._server.serve_forever(poll_interval=0.1)

    # ****************
    # Public Interface
    # ****************

    def add_request(self, req):
        self._requests.append(req)

    def reset(self):
        self.num_req_processed = 0
        self._requests.clear()
        self._responses.clear()

    def start(self, daemon=True):
        """Start the HTTP server."""
        self._thread = Thread(
            target=self._thread_server,
        )
        self._thread.daemon = daemon
        self._thread.start()
        self.wait_server_started()
        self.port = self._server.socket.getsockname()[1]

    def wait_server_started(self):
        # I could not foind another way
        # to handle multiple socket issues
        # other than taking some sleep
        time.sleep(0.01)
        self.server_started.wait()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    def get_url(self, path="", port=None):
        """Build URL that is served by HTTP server."""
        if port is None:
            port = self.port
        return urljoin("http://%s:%d" % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.num_req_processed:
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError("No request processed in %d seconds" % timeout)

    def request_is_done(self):
        return self.num_req_processed

    def get_request(self):
        try:
            return self._requests[-1]
        except IndexError as ex:
            raise RequestNotProcessed("Request has not been processed") from ex

    def add_response(self, resp: Response, count=1, method=None):
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

    def get_response(self, method):
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
                    raise NoResponse("No response available") from ex
            if item["count"] == -1:
                return item["response"]
            else:
                item["count"] -= 1
                if item["count"] < 1:
                    scope.pop(0)
                return item["response"]
