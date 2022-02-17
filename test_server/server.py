from pprint import pprint  # pylint: disable=unused-import
import time
from collections.abc import Iterable
from threading import Thread, Event

from socketserver import ThreadingMixIn, TCPServer
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urljoin, parse_qsl

from test_server.version import TEST_SERVER_VERSION
from test_server.error import TestServerError

__all__ = ("TestServer", "WaitTimeoutError")


class WaitTimeoutError(Exception):
    pass


class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True
    started = False

    def __init__(self, server_address, RequestHandlerClass, test_server=None, **kwargs):
        super().__init__(server_address, RequestHandlerClass, **kwargs)
        self.test_server = test_server
        self.test_server.server_started.set()


class TestServerHandler(BaseHTTPRequestHandler):
    def _request_handler(self):
        test_srv = self.server.test_server  # pytype: disable=attribute-error
        method = self.command.lower()

        sleep = test_srv.get_param("sleep", method)
        if sleep:
            time.sleep(sleep)
        test_srv.request["client_ip"] = self.client_address[0]
        test_srv.request["args"] = {}
        # test_srv.request['args_binary'] = {}
        try:
            qs = self.path.split("?")[1]
        except IndexError:
            qs = ""
        params = dict(parse_qsl(qs))
        for key in params:
            test_srv.request["args"][key] = (
                params[key]
                # request.params.getunicode(key) # pylint: disable=no-member
            )
        #    #test_srv.request['args_binary'][key] = request.params[key]
        for key in self.headers.keys():
            test_srv.request["headers"][key.lower()] = self.headers[key]

        path = self.path
        # WTF is this?
        # if isinstance(path, bytes):
        #    path = path.decode("utf-8")
        test_srv.request["path"] = path.split("?")[0]
        test_srv.request["method"] = method.upper()

        cookies = {}
        items = SimpleCookie(self.headers["Cookie"])
        for key in items.keys():
            cookies[key] = {}
            cookies[key]["name"] = key
            cookies[key]["value"] = items[key].value
        test_srv.request["cookies"] = cookies

        clen = int(self.headers["Content-Length"] or "0")
        test_srv.request["data"] = self.rfile.read(clen)

        # self._server.request['files'] = defaultdict(list)
        # for file_ in request.files.values(): # pylint: disable=no-member
        #    self._server.request['files'][file_.name].append({
        #        'name': file_.name,
        #        'raw_filename': file_.raw_filename,
        #        'content_type': file_.content_type,
        #        'filename': file_.filename,
        #        'content': file_.file.read(),
        #    })

        response = {
            "code": 200,
            "headers": [],
            "data": b"",
        }

        callback = test_srv.get_param("callback", method)
        if callback:
            cb_res = callback()
            assert isinstance(cb_res, dict) and cb_res.get("type") in ("response",)
            if cb_res["type"] == "response":
                assert all(
                    x in ("type", "code", "headers", "cookies", "body")
                    for x in cb_res.keys()
                )
                if "code" in cb_res:
                    response["code"] = cb_res["code"]
                if "headers" in cb_res:
                    for key, val in cb_res["headers"]:
                        response["headers"].append((key, val))
                if "cookies" in cb_res:
                    for key, val in cb_res["cookies"]:
                        response["headers"].append(("Set-Cookie", "%s=%s" % (key, val)))
                if "body" in cb_res:
                    if isinstance(cb_res["body"], str):
                        # TODO: do not use hardcoded "utf-8"
                        response["data"] = cb_res["body"].encode("utf-8")
                    elif isinstance(cb_res["body"], bytes):
                        response["data"] = cb_res["body"]
        else:
            response["code"] = test_srv.get_param("code", method)

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
                    response["code"] = 503
            else:
                self.write_response_data(
                    500, [], b'Response parameter "data" must be string or iterable'
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
            response["code"], response["headers"], response["data"]
        )
        test_srv.request["done"] = True

    def write_response_data(self, code, headers, data):
        self.send_response(code)
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
    do_OPTIONS = _request_handler
    do_PATCH = _request_handler
    do_PUT = _request_handler


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
        self.request.update(
            {
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
        )
        self.response.clear()
        self.response.update(
            {
                "code": 200,
                "data": "",
                "headers": [],
                "cookies": [],
                "callback": None,
                "sleep": None,
                "charset": "utf-8",
            }
        )
        self.response_once.clear()

    def thread_server(self):
        """Ask HTTP server start processing requests

        This function is supposed to be run in separate thread.
        """

        print("PORT", self.port)
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
        if port is None:
            port = self.port
        return urljoin("http://%s:%d" % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.request["done"]:
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
