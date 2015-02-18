from threading import Thread
from tornado.ioloop import IOLoop
import tornado.web
import time
import collections
import tornado.gen
from tornado.httpserver import HTTPServer
from six.moves.urllib.parse import urljoin

__all__ = ('TestServer',)


class TestServer(object):
    request = {}
    response = {}
    response_once = {'headers': []}
    sleep = {}
    timeout_iterator = None

    def __init__(self, port=9876, address='127.0.0.1', extra_ports=None):
        self.port = port
        self.address = address
        self.extra_ports = list(extra_ports or [])
        self.reset()
        self._handler = None
        self._thread = None

    def reset(self):
        self.request.update({
            'args': {},
            'headers': {},
            'cookies': None,
            'path': None,
            'method': None,
            'charset': 'utf-8',
        })
        self.response.update({
            'get': '',
            'post': '',
            'cookies': None,
            'headers': [],
            'code': 200,
        })

        for method in ('get', 'post', 'head', 'options', 'put', 'delete',
                       'patch', 'trace', 'connect'):
            self.response['%s_callback' % method] = None

        self.response_once.update({
            'get': None,
            'post': None,
            'code': None,
            'cookies': None,
        })
        self.sleep.update({
            'get': 0,
            'post': 0,
        })
        for x in range(len(self.response_once['headers'])):
            self.response_once['headers'].pop()

    def get_handler(self):
        "Build tornado request handler that is used in HTTP server"
        SERVER = self

        class MainHandler(tornado.web.RequestHandler):
            def decode_argument(self, value, **kwargs):
                # pylint: disable=unused-argument
                return value.decode(SERVER.request['charset'])

            @tornado.web.asynchronous
            @tornado.gen.engine
            def method_handler(self):
                method_name = self.request.method.lower()

                if SERVER.sleep.get(method_name, None):
                    yield tornado.gen.Task(IOLoop.instance().add_timeout,
                                           time.time() +
                                           SERVER.sleep[method_name])
                SERVER.request['args'] = {}
                for key in self.request.arguments.keys():
                    SERVER.request['args'][key] = self.get_argument(key)
                SERVER.request['headers'] = self.request.headers
                SERVER.request['path'] = self.request.path
                SERVER.request['method'] = self.request.method
                SERVER.request['cookies'] = self.request.cookies
                charset = SERVER.request['charset']
                SERVER.request['post'] = self.request.body

                callback_name = '%s_callback' % method_name
                if SERVER.response.get(callback_name) is not None:
                    SERVER.response[callback_name](self)
                else:
                    headers_sent = set()

                    if SERVER.response_once['code']:
                        self.set_status(SERVER.response_once['code'])
                        SERVER.response_once['code'] = None
                    else:
                        self.set_status(SERVER.response['code'])

                    if SERVER.response_once['cookies']:
                        for key, val in sorted(SERVER.response_once['cookies']
                                                     .items()):
                            # Set-Cookie: name=newvalue; expires=date;
                            # path=/; domain=.example.org.
                            self.add_header('Set-Cookie', '%s=%s' % (key, val))
                        SERVER.response_once['cookies'] = None
                    else:
                        if SERVER.response['cookies']:
                            for key, val in sorted(SERVER.response['cookies']
                                                         .items()):
                                # Set-Cookie: name=newvalue; expires=date;
                                # path=/; domain=.example.org.
                                self.add_header('Set-Cookie',
                                                '%s=%s' % (key, val))

                    if SERVER.response_once['headers']:
                        while SERVER.response_once['headers']:
                            key, value = SERVER.response_once['headers'].pop()
                            self.set_header(key, value)
                            headers_sent.add(key)
                    else:
                        for name, value in SERVER.response['headers']:
                            self.set_header(name, value)

                    self.set_header('Listen-Port',
                                    str(self.application.listen_port))

                    if 'Content-Type' not in headers_sent:
                        charset = 'utf-8'
                        self.set_header('Content-Type',
                                        'text/html; charset=%s' % charset)
                        headers_sent.add('Content-Type')

                    if SERVER.response_once.get(method_name) is not None:
                        self.write(SERVER.response_once[method_name])
                        SERVER.response_once[method_name] = None
                    else:
                        resp = SERVER.response.get(method_name, '')
                        if isinstance(resp, collections.Callable):
                            self.write(resp())
                        else:
                            self.write(resp)

                    if SERVER.timeout_iterator:
                        yield tornado.gen.Task(IOLoop.instance().add_timeout,
                                               time.time() +
                                               next(SERVER.timeout_iterator))
                    self.finish()

            get = method_handler
            post = method_handler
            put = method_handler
            patch = method_handler
            delete = method_handler

        if not self._handler:
            self._handler = MainHandler
        return self._handler

    def _build_web_app(self):
        """Build tornado web application that is served by
        HTTP server"""
        return tornado.web.Application([
            (r"^.*", self.get_handler()),
        ])

    def main_loop_function(self):
        """This is function that is executed in separate thread:
         * start HTTP server
         * start tornado loop"""
        ports = [self.port] + self.extra_ports
        servers = []
        for port in ports:
            app = self._build_web_app()
            app.listen_port = port
            server = HTTPServer(app)
            server.listen(port, self.address)
            print('Listening on port %d' % port)
            servers.append(server)

        tornado.ioloop.IOLoop.instance().start()

        # manually close sockets
        # to be able to create other HTTP servers
        # on same sockets
        for server in servers:
            # pylint: disable=protected-access
            for socket in server._sockets.values():
                socket.close()

    def start(self):
        """Create new thread with tornado loop and start there
        HTTP server."""

        self._thread = Thread(target=self.main_loop_function)
        self._thread.start()
        time.sleep(0.1)

    def stop(self):
        "Stop tornado loop and wait for thread finished it work"
        tornado.ioloop.IOLoop.instance().stop()
        self._thread.join()

    def get_url(self, extra='', port=None):
        "Build URL that is served by HTTP server"
        if port is None:
            port = self.port
        return urljoin('http://%s:%d/' % (self.address, port), extra)
