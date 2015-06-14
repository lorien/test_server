from threading import Thread
from tornado.ioloop import IOLoop
import tornado.web
import time
import collections
import tornado.gen
from tornado.httpserver import HTTPServer
from six.moves.urllib.parse import urljoin
import six
from six.moves.urllib.request import urlopen
import logging

from test_server.error import TestServerRuntimeError
import test_server

__all__ = ('TestServer',)


class TestServer(object):
    request = {}
    response = {}
    response_once = {'headers': []}
    sleep = {}
    timeout_iterator = None
    methods = ('get', 'post', 'head', 'options', 'put', 'delete',
               'patch', 'trace', 'connect')

    def __init__(self, port=9876, address='127.0.0.1', extra_ports=None):
        self.port = port
        self.address = address
        self.extra_ports = list(extra_ports or [])
        self.reset()
        self._handler = None
        self._thread = None

    def get_param(self, key, method='get', clear_once=True):
        method_key = '%s.%s' % (method, key)
        if method_key in self.response_once:
            value = self.response_once[method_key]
            if clear_once:
                del self.response_once[method_key]
            return value
        elif key in self.response_once:
            value = self.response_once[key]
            if clear_once:
                del self.response_once[key]
            return value
        elif method_key in self.response:
            return self.response[method_key]
        elif key in self.response:
            return self.response[key]
        else:
            raise TestServerRuntimeError('Parameter %s does not exists in '
                                         'server response data' % key)

    def reset(self):
        self.request.update({
            'args': {},
            'headers': {},
            'cookies': None,
            'path': None,
            'method': None,
            'charset': 'UTF-8',
            'data': None,
            'files': {},
        })
        self.response = {
            'code': 200,
            'data': '',
            'headers': [],
            'cookies': [],
            'callback': None,
            'sleep': None,
        }

        self.response_once = {}

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
                # Remove some standard tornado headers
                for key in ('Content-Type', 'Server'):
                    if key in self._headers:
                        del self._headers[key]

                method = self.request.method.lower()

                sleep = SERVER.get_param('sleep', method)
                if sleep:
                    yield tornado.gen.Task(IOLoop.instance().add_timeout,
                                           time.time() + sleep)
                SERVER.request['args'] = {}
                for key in self.request.arguments.keys():
                    SERVER.request['args'][key] = self.get_argument(key)
                SERVER.request['headers'] = self.request.headers
                SERVER.request['path'] = self.request.path
                SERVER.request['method'] = self.request.method
                SERVER.request['cookies'] = self.request.cookies
                charset = SERVER.request['charset']
                SERVER.request['data'] = self.request.body
                SERVER.request['files'] = self.request.files

                callback = SERVER.get_param('callback', method)
                if callback:
                    callback(self)
                else:
                    response = {
                        'code': None,
                        'headers': [],
                        'data': None,
                    }

                    response['code'] = SERVER.get_param('code', method)

                    for key, val in SERVER.get_param('cookies', method):
                        # Set-Cookie: name=newvalue; expires=date;
                        # path=/; domain=.example.org.
                        response['headers'].append(
                            ('Set-Cookie', '%s=%s' % (key, val)))

                    for key, value in SERVER.get_param('headers', method):
                        response['headers'].append((key, value))

                    response['headers'].append(
                        ('Listen-Port', str(self.application.listen_port)))

                    data = SERVER.get_param('data', method)
                    if isinstance(data, six.string_types):
                        response['data'] = data
                    elif isinstance(data, six.binary_type):
                        response['data'] = data
                    elif isinstance(data, collections.Iterable):
                        try:
                            response['data'] = next(data)
                        except StopIteration:
                            response['code'] = 405
                            response['data'] = b''
                    else:
                        raise TestServerRuntimeError('Data parameter should '
                                                     'be string or iterable '
                                                     'object')

                    if SERVER.timeout_iterator:
                        yield tornado.gen.Task(IOLoop.instance().add_timeout,
                                               time.time() +
                                               next(SERVER.timeout_iterator))

                    header_keys = [x[0].lower() for x in response['headers']]
                    if 'content-type' not in header_keys:
                        response['headers'].append(
                            ('Content-Type',
                             'text/html; charset=%s' % charset))
                    if 'server' not in header_keys:
                        response['headers'].append(
                            ('Server', 'TestServer/%s' % test_server.version))

                    self.set_status(response['code'])
                    for key, val in response['headers']:
                        self.add_header(key, val)
                    self.write(response['data'])
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

            try_limit = 10
            try_pause = 0.1
            for x in range(try_limit):
                try:
                    server.listen(port, self.address)
                except OSError:
                    if x == (try_limit - 1):
                        raise
                    else:
                        logging.debug('Socket %s:%d is busy, '
                                      'waiting %.2f seconds.'
                                      % (self.address, self.port, try_pause))
                        time.sleep(0.1)
                else:
                    break

            print('Listening on port %d' % port)
            servers.append(server)

        try:
            tornado.ioloop.IOLoop.instance().start()
        finally:
            # manually close sockets
            # to be able to create other HTTP servers
            # on same sockets
            for server in servers:
                # pylint: disable=protected-access
                server.stop()

    def start(self):
        """Create new thread with tornado loop and start there
        HTTP server."""

        self.is_stopped = False
        self._thread = Thread(target=self.main_loop_function)
        self._thread.start()

        try_limit = 10
        try_pause = 0.05
        for x in range(try_limit):
            try:
                urlopen(self.get_url()).read()
            except Exception as ex:
                if x == (try_limit - 1):
                    raise
                else:
                    time.sleep(try_pause)
            else:
                break

    def stop(self):
        "Stop tornado loop and wait for thread finished it work"
        tornado.ioloop.IOLoop.instance().stop()
        self._thread.join()
        self.is_stopped = True

    def get_url(self, extra='', port=None):
        "Build URL that is served by HTTP server"
        if port is None:
            port = self.port
        return urljoin('http://%s:%d/' % (self.address, port), extra)


if __name__ == '__main__':
    server = TestServer()
    server.response['data'] = 'home page'
    server.start()
    try:
        while not server.is_stopped:
            time.sleep(0.1)
    except KeyboardInterrupt:
        server.stop()
