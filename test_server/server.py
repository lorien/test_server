# pylint: disable=consider-using-f-string
from pprint import pprint  # pylint: disable=unused-import
import time
from collections.abc import Iterable
from threading import Thread, Event
import cgi
from io import BytesIO
from copy import deepcopy
import logging

from socketserver import ThreadingMixIn, TCPServer
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urljoin, parse_qsl

from test_server.version import TEST_SERVER_VERSION
from test_server.error import TestServerError, WaitTimeoutError, InternalError

__all__ = ("TestServer", "WaitTimeoutError")

INTERNAL_ERROR_RESPONSE_STATUS = 555
CLEAN_RESPONSE_DATA = {
    "status": 200,
    "data": "",
    "headers": [],
    "cookies": [],
    "callback": None,
    "sleep": None,
    "charset": "utf-8",
}
CLEAN_REQUEST_DATA = {
    "args": {},
    "args_binary": {},
    "headers": {},
    "cookies": None,
    "path": None,
    "method": None,
    "data": None,
    "files": {},
    "client_ip": None,
    "done": False,
    "charset": "utf-8",
}
VALID_RESPONSE_KEYS = list(CLEAN_RESPONSE_DATA.keys())
VALID_METHODS = ["get", "post", "put", "delete", "options", "patch"]


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True
    started = False

    def __init__(self, server_address, RequestHandlerClass, test_server=None, **kwargs):
        super().__init__(server_address, RequestHandlerClass, **kwargs)
        self.test_server = test_server
        self.test_server.server_started.set()


class TestServerHandler(BaseHTTPRequestHandler):
    def _collect_request_data(self, method):
        request = deepcopy(CLEAN_REQUEST_DATA)
        request["client_ip"] = self.client_address[0]
        request["args"] = {}
        try:
            qs = self.path.split("?")[1]
        except IndexError:
            qs = ""
        params = dict(parse_qsl(qs))
        for key, val in params.items():
            request["args"][key] = val
        #    #request['args_binary'][key] = request.params[key]
        for key, val in self.headers.items():
            request["headers"][key.lower()] = val

        path = self.path
        # WTF is this?
        # if isinstance(path, bytes):
        #    path = path.decode("utf-8")
        request["path"] = path.split("?")[0]
        request["method"] = method.upper()

        cookies = {}
        items = SimpleCookie(self.headers["Cookie"])
        for item_key, item in items.items():
            cookies[item_key] = {}
            cookies[item_key]["name"] = item_key
            cookies[item_key]["value"] = item.value
        request["cookies"] = cookies

        clen = int(self.headers["Content-Length"] or "0")
        request_data = self.rfile.read(clen)
        request["data"] = request_data

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
                    request["files"].setdefault(field_key, []).append(
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
            sleep = test_srv.get_param("sleep", method)
            if sleep:
                time.sleep(sleep)
            test_srv.request = self._collect_request_data(method)

            response = {
                "status": 200,
                "headers": [],
                "data": b"",
            }

            callback = test_srv.get_param("callback", method)
            if callback:
                cb_res = callback()
                if not isinstance(cb_res, dict):
                    raise InternalError("Callback response is not a dict")
                elif cb_res.get("type") == "response":
                    for key in cb_res:
                        if key not in ("type", "status", "headers", "cookies", "body"):
                            raise InternalError(
                                "Callback response contains invalid key: %s" % key
                            )
                    if "status" in cb_res:
                        response["status"] = cb_res["status"]
                    if "headers" in cb_res:
                        for key, val in cb_res["headers"]:
                            response["headers"].append((key, val))
                    if "cookies" in cb_res:
                        for key, val in cb_res["cookies"]:
                            response["headers"].append(
                                ("Set-Cookie", "%s=%s" % (key, val))
                            )
                    if "body" in cb_res:
                        if isinstance(cb_res["body"], str):
                            # TODO: do not use hardcoded "utf-8"
                            response["data"] = cb_res["body"].encode("utf-8")
                        elif isinstance(cb_res["body"], bytes):
                            response["data"] = cb_res["body"]
                else:
                    raise InternalError(
                        "Callback response has invalid type key: %s"
                        % cb_res.get("type", "NA")
                    )
            else:
                response["status"] = test_srv.get_param("status", method)

                for key, val in test_srv.get_param("cookies", method):
                    # Set-Cookie: name=newvalue; expires=date;
                    # path=/; domain=.example.org.
                    response["headers"].append(("Set-Cookie", "%s=%s" % (key, val)))

                for key, value in test_srv.get_param("headers", method):
                    response["headers"].append((key, value))

                port = self.server.test_server.port  # pytype: disable=attribute-error
                response["headers"].append(("Listen-Port", str(port)))

                data = test_srv.get_param("data", method)
                charset = test_srv.get_param("charset", method)
                if isinstance(data, str):
                    response["data"] = data.encode(charset)
                elif isinstance(data, bytes):
                    response["data"] = data
                elif isinstance(data, Iterable):
                    try:
                        next_data = next(data)
                        if isinstance(next_data, str):
                            next_data = next_data.encode(charset)
                        response["data"] = next_data
                    except StopIteration:
                        response["status"] = 503
                else:
                    raise InternalError(
                        'Response parameter "data" must be string or iterable'
                    )

                header_keys = [x[0].lower() for x in response["headers"]]
                if "content-type" not in header_keys:
                    response["headers"].append(
                        (
                            "Content-Type",
                            "text/html; charset=%s" % charset,
                        )
                    )
                if "server" not in header_keys:
                    response["headers"].append(
                        ("Server", "TestServer/%s" % TEST_SERVER_VERSION)
                    )

            self.write_response_data(
                response["status"], response["headers"], response["data"]
            )
        except Exception as ex:
            logging.exception("Internal error happend in test server request handler")
            self.write_response_data(
                INTERNAL_ERROR_RESPONSE_STATUS, [], str(ex).encode("utf-8")
            )
        finally:
            test_srv.request["done"] = True

    def write_response_data(self, status, headers, data):
        self.send_response(status)
        for key, val in headers:
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(data)

    # https://github.com/python/cpython/blob/main/Lib/http/server.py
    def send_response(self, code, message=None):
        """
        Custom method which does not send Server and Date headers
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
        self.request = {}
        self.response = {}
        self.response_once = {}
        self.port = port
        self.address = address
        self._handler = None
        self._thread = None
        self._server = None
        self._started = Event()
        self.config = {}
        self.config.update(
            {
                "port": self.port,
            }
        )
        self.reset()

    def reset(self):
        self.request.clear()
        self.response.clear()
        self.response.update(deepcopy(CLEAN_RESPONSE_DATA))
        self.response_once.clear()

    def thread_server(self):
        """Ask HTTP server start processing requests

        This function is supposed to be run in separate thread.
        """

        self._server = ThreadingTCPServer(
            (self.address, self.port), TestServerHandler, test_server=self
        )
        self._server.serve_forever(poll_interval=0.1)

    def start(self, daemon=True):
        """Start the HTTP server."""
        self._thread = Thread(
            target=self.thread_server,
        )
        self._thread.daemon = daemon
        self._thread.start()
        self.wait_server_started()

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
        # Yeah, stupid, just tryng to fail my Grab tests ASAP
        self.validate_response_keys()
        if port is None:
            port = self.port
        return urljoin("http://%s:%d" % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.request_is_done():
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError("No request processed in %d seconds" % timeout)

    def get_param(self, key, method="get"):
        method_key = "%s.%s" % (method, key)
        if method_key in self.response_once:
            return self.response_once.pop(method_key)
        elif key in self.response_once:
            return self.response_once.pop(key)
        elif method_key in self.response:
            return self.response[method_key]
        elif key in self.response:
            return self.response[key]
        else:
            raise TestServerError("Response parameter {} is not configured".format(key))

    def validate_response_keys(self):
        for scope_name, scope in [
            ("response", self.response),
            ("response_once", self.response_once),
        ]:
            for key_item in scope:
                if "." in key_item:
                    method, key = key_item.split(".", 1)
                else:
                    method = None
                    key = key_item
                if (
                    method and method not in VALID_METHODS
                ) or key not in VALID_RESPONSE_KEYS:
                    raise TestServerError("Invalid %s key: %s" % (scope_name, key_item))

    def request_is_done(self):
        return self.request and self.request["done"]
