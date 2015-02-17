from threading import Thread
from tornado.ioloop import IOLoop
import tornado.web
import time
import collections
import tornado.gen
from tornado.httpserver import HTTPServer

__all__ = ('TestServer',)


class TestServer(object):
    port = 9876
    extra_port1 = 9877
    extra_port2 = 9878
    base_url = None
    request = {}
    response = {}
    response_once = {'headers': []}
    sleep = {}
    timeout_iterator = None

    def __init__(self):
        self.reset()
        self._handler = None

    def reset(self):
        self.base_url = 'http://localhost:%d' % self.port
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
        """
        Ok, ok, I know that this is f**g strange code.
        """
        SERVER = self

        class MainHandler(tornado.web.RequestHandler):
            def decode_argument(self, value, **kwargs):
                return value.decode(SERVER.request['charset'])

            @tornado.web.asynchronous
            @tornado.gen.engine
            def method_handler(self):
                """
                if '/::stop' in self.request.path:
                    print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1'
                    self.write('')
                    self.finish()
                    print('done')
                    loop = tornado.ioloop.IOLoop.instance()
                    loop.add_callback(callback=loop.stop)
                """

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
                                    str(self.application._listen_port))

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

    def start(self):
        def func():
            app1 = tornado.web.Application([
                (r"^.*", self.get_handler()),
            ])
            app2 = tornado.web.Application([
                (r"^.*", self.get_handler()),
            ])
            app3 = tornado.web.Application([
                (r"^.*", self.get_handler()),
            ])

            app1._listen_port = self.port
            app2._listen_port = self.extra_port1
            app3._listen_port = self.extra_port2

            server1 = HTTPServer(app1)
            server1.listen(app1._listen_port, '')
            print('Listening on port %d' % app1._listen_port)

            server2 = HTTPServer(app2)
            server2.listen(app2._listen_port, '')
            print('Listening on port %d' % app2._listen_port)

            server3 = HTTPServer(app3)
            server3.listen(app3._listen_port, '')
            print('Listening on port %d' % app3._listen_port)

            tornado.ioloop.IOLoop.instance().start()
            # manually close sockets
            # to be able to creat anoterh HTTP servers
            # on same sockets
            for server in (server1, server2, server3):
                for key in server._sockets:
                    server._sockets[key].close()

        self._thread = Thread(target=func)
        self._thread.start()
        time.sleep(0.1)

    def stop(self):
        tornado.ioloop.IOLoop.instance().stop()
        self._thread.join()
