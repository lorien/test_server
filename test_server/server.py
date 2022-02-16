from pprint import pprint  # pylint: disable=unused-import
import time
from collections.abc import Iterable
from threading import Thread, Event

from six.moves.socketserver import ThreadingMixIn, TCPServer
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler
from six.moves.http_cookies import SimpleCookie
from six.moves.urllib.parse import urljoin, parse_qsl
import six

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
    def get_param(self, key, method="get", clear_once=True):
        method_key = "%s.%s" % (method, key)
        test_srv = self.server.test_server
        if method_key in test_srv.response_once:
            value = test_srv.response_once[method_key]
            if clear_once:
                del test_srv.response_once[method_key]
            return value
        elif key in test_srv.response_once:
            value = test_srv.response_once[key]
            if clear_once:
                del test_srv.response_once[key]
            return value
        elif method_key in test_srv.response:
            return test_srv.response[method_key]
        elif key in test_srv.response:
            return test_srv.response[key]
        else:
            raise TestServerError(
                "Parameter %s does not exists in " "server response data" % key
            )

    def _request_handler(self):
        from test_server import __version__  # pylint: disable=import-outside-toplevel

        test_srv = self.server.test_server
        method = self.command.lower()

        sleep = self.get_param("sleep", method)
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
        if isinstance(path, six.binary_type):
            path = path.decode("utf-8")
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

        callback = self.get_param("callback", method)
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
                    if isinstance(cb_res["body"], six.text_type):
                        # TODO: do not use hardcoded "utf-8"
                        response["data"] = cb_res["body"].encode("utf-8")
                    elif isinstance(cb_res["body"], six.binary_type):
                        response["data"] = cb_res["body"]
        else:
            response["code"] = self.get_param("code", method)

            for key, val in self.get_param("cookies", method):
                # Set-Cookie: name=newvalue; expires=date;
                # path=/; domain=.example.org.
                response["headers"].append(("Set-Cookie", "%s=%s" % (key, val)))

            for key, value in self.get_param("headers", method):
                response["headers"].append((key, value))

            response["headers"].append(
                ("Listen-Port", str(self.server.test_server.port))
            )

            data = self.get_param("data", method)
            charset = self.get_param("charset", method)
            if isinstance(data, six.text_type):
                response["data"] = data.encode(charset)
            elif isinstance(data, six.binary_type):
                response["data"] = data
            elif isinstance(data, Iterable):
                try:
                    next_data = next(data)
                    if isinstance(next_data, six.text_type):
                        next_data = next_data.encode("charset")
                    response["data"] = next_data
                except StopIteration:
                    response["code"] = 503
            else:
                raise TestServerError(
                    "Data parameter should " "be string or iterable " "object"
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
                response["headers"].append(("Server", "TestServer/%s" % __version__))

        self.send_response(response["code"])
        for key, val in response["headers"]:
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(response["data"])
        test_srv.request["done"] = True

    do_GET = _request_handler
    do_POST = _request_handler
    do_OPTIONS = _request_handler

    # https://github.com/python/cpython/blob/main/Lib/http/server.py
    def send_response(self, code, message=None):
        """
        Custom method which does not send Server and Date headers
        """
        self.log_request(code)
        self.send_response_only(code, message)


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

        self._server = ThreadingTCPServer(
            (self.address, self.port), TestServerHandler, test_server=self
        )
        self._server.serve_forever()

    def start(self, daemon=True):
        """Start the HTTP server."""
        self._thread = Thread(
            target=self.thread_server,
        )
        self._thread.daemon = daemon
        self._thread.start()
        self.wait_server_started()

    def wait_server_started(self):
        self.server_started.wait()

    def stop(self):
        """Stop tornado loop and wait for thread finished it work."""
        # TODO
        # self._server.shutdown()
        # self._thread.join()

    def get_url(self, path="", port=None):
        """Build URL that is served by HTTP server."""
        if port is None:
            port = self.port
        return urljoin("http://%s:%d/" % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.request["done"]:
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError("No request processed in %d seconds" % timeout)
