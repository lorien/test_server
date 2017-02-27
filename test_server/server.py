from threading import Thread
import time
import collections
import logging
import types
import os
import tempfile
import json
from subprocess import Popen
import signal
import atexit
from socket import AF_INET

from six.moves.urllib.parse import urljoin
import six
from six.moves.urllib.request import urlopen
from filelock import FileLock
import psutil
import tornado.web
from tornado.locks import Semaphore
import tornado.gen
from tornado.httpserver import HTTPServer
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop
from tornado.netutil import bind_sockets

from test_server.error import TestServerError
from test_server.util import DeprecatedAttribute

__all__ = ('TestServer', 'WaitTimeoutError')
logger = logging.getLogger('test_server.server') # pylint: disable=invalid-name

class WaitTimeoutError(Exception):
    pass


def kill_process(pid):
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        pass
    else:
        os.kill(pid, signal.SIGINT)
        try:
            proc.wait(timeout=1)
        except psutil.TimeoutExpired:
            os.kill(pid, signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except psutil.TimeoutExpired:
                raise WaitTimeoutError('Could not kill subprocess running'
                                       ' test_server')


def bytes_to_unicode(obj):
    if isinstance(obj, six.text_type):
        return obj
    elif isinstance(obj, six.binary_type):
        return obj.decode('utf-8')
    elif isinstance(obj, list):
        return [bytes_to_unicode(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple((bytes_to_unicode(x) for x in obj))
    elif isinstance(obj, dict):
        return dict(map(bytes_to_unicode, x) for x in obj.items())
    else:
        return obj


def prepare_loaded_state(state_key, state):
    """
    Fix state loaded from JSON-serialized data:
    * all values of data keys have to be converted to <bytes> strings
    * headers should be converted to tornado.httputil.HTTPHeaders
    """
    if 'data' in state:
        if state['data'] is not None:
            state['data'] = state['data'].encode('utf-8')
    for key in list(state.keys()):
        if key.endswith('.data'):
            if state[key] is not None:
                state[key] = state[key].encode('utf-8')
    if state_key == 'request':
        hdr = HTTPHeaders()
        if state['headers']:
            for key, val in state['headers']:
                hdr.add(key, val)
        state['headers'] = hdr
    return state


class TestServerRequestHandler(tornado.web.RequestHandler):
    # pylint: disable=abstract-method,protected-access
    def initialize(self, test_server): # pylint: disable=arguments-differ
        self._server = test_server

    def get_param(self, key, method='get', clear_once=True):
        method_key = '%s.%s' % (method, key)

        if method_key in self._server._response_once:
            value = self._server._response_once[method_key]
            if clear_once:
                del self._server._response_once[method_key]
                self._server.save_state(['response_once'])
            return value
        elif key in self._server._response_once:
            value = self._server._response_once[key]
            if clear_once:
                del self._server._response_once[key]
                self._server.save_state(['response_once'])
            return value
        elif method_key in self._server._response:
            return self._server._response[method_key]
        elif key in self._server._response:
            return self._server._response[key]
        else:
            raise TestServerError('Parameter %s does not exists in '
                                  'server response data' % key)

    def decode_argument(self, value, **kwargs):
        # pylint: disable=unused-argument
        return value.decode(self._server._request['charset'])

    @tornado.web.asynchronous
    @tornado.gen.engine
    def request_handler(self):
        from test_server import __version__

        with (yield self._server._locks['request_handler'].acquire()):
            self._server.load_response_state()
            # Remove some standard tornado headers
            for key in ('Content-Type', 'Server'):
                if key in self._headers:
                    del self._headers[key]

            method = self.request.method.lower()

            sleep = self.get_param('sleep', method)
            if sleep:
                yield tornado.gen.Task(self._server.ioloop.add_timeout,
                                       time.time() + sleep)
            self._server._request['client_ip'] = self.request.remote_ip
            self._server._request['args'] = {}
            for key in self.request.arguments.keys():
                self._server._request['args'][key] = self.get_argument(key)
            if self._server._engine == 'subprocess':
                self._server._request['headers'] = (
                    list(self.request.headers.get_all())
                )
            else:
                self._server._request['headers'] = self.request.headers
            self._server._request['path'] = self.request.path
            self._server._request['method'] = self.request.method

            cookies = {}
            for key, cookie in self.request.cookies.items():
                cookies[key] = dict(cookie)
                cookies[key]['name'] = cookie.key
                cookies[key]['value'] = cookie.value
            self._server._request['cookies'] = cookies

            charset = self._server._request['charset']
            self._server._request['data'] = self.request.body
            self._server._request['files'] = self.request.files

            callback = self.get_param('callback', method)
            if callback:
                call = callback(self)
                if isinstance(call, types.GeneratorType):
                    for item in call:
                        if isinstance(item, dict):
                            assert 'type' in item
                            assert item['type'] in ('sleep',)
                            if item['type'] == 'sleep':
                                yield tornado.gen.Task(
                                    self._server.ioloop.add_timeout,
                                    time.time() + item['time'],
                                )
                        else:
                            yield item
            else:
                response = {
                    'code': None,
                    'headers': [],
                    'data': None,
                }

                response['code'] = self.get_param('code', method)

                for key, val in self.get_param('cookies', method):
                    # Set-Cookie: name=newvalue; expires=date;
                    # path=/; domain=.example.org.
                    response['headers'].append(
                        ('Set-Cookie', '%s=%s' % (key, val)))

                for key, value in self.get_param('headers', method):
                    response['headers'].append((key, value))

                response['headers'].append(
                    ('Listen-Port', str(self._server.port)))

                data = self.get_param('data', method)
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
                    raise TestServerError('Data parameter should '
                                          'be string or iterable '
                                          'object')

                header_keys = [x[0].lower() for x in response['headers']]
                if 'content-type' not in header_keys:
                    response['headers'].append(
                        ('Content-Type',
                         'text/html; charset=%s' % charset))
                if 'server' not in header_keys:
                    response['headers'].append(
                        ('Server', 'TestServer/%s' % __version__))

                self.set_status(response['code'])
                for key, val in response['headers']:
                    self.add_header(key, val)
                self.write(response['data'])

                self._server._request['done'] = True
                self._server.save_request_state()

            self._server._request['done'] = True
            self._server.save_request_state()

            if not callback:
                self.finish()

    get = post = put = patch = delete = options = request_handler

    def finish(self, *args, **kwargs):
        # I am not sure about this.
        # I hope that solves strange error in tests
        # when request['done'] is not True after successful
        # request to the test server
        # I thinks it is about race-codition
        self._server._request['done'] = True
        self._server.save_request_state()
        super(TestServerRequestHandler, self).finish(*args, **kwargs)


class TestServer(object):
    _request = {}
    _response = {}
    _response_once = {}
    request = DeprecatedAttribute(
        '_request',
        'Attribute request is deprecated. Use set_request and'
        ' get_request methods instead.',
    )
    response = DeprecatedAttribute(
        '_response',
        'Attribute response is deprecated. Use set_response and'
        ' get_response methods instead.',
    )
    response_once = DeprecatedAttribute(
        '_response_once',
        'Attribute response_once is deprecated. Use set_response_once and'
        ' get_response_once methods instead.',
    )

    def __init__(self, port=0, address='127.0.0.1',
                 engine='thread', role='master', **kwargs):
        assert engine in ('thread', 'subprocess')
        self.port = port
        self.address = address
        self._handler = None
        self._thread = None # thread instance if thread engine
        self._proc = None # Process instance if subprocess engine
        self._engine = engine
        self._role = role
        self.request_file = None
        self.response_file = None
        self.response_once_file = None
        self.config_file = None
        self.request_lock_file = None
        self.response_lock_file = None
        self.response_once_lock_file = None
        if (role == 'master' and engine == 'thread') or role == 'server':
            self.ioloop = IOLoop()
            self.ioloop.make_current()
        # Restrict any activity untill the reset method
        # will setup initial content of request/respone files
        if role == 'master' and engine == 'subprocess':
            hdl, self.request_file = tempfile.mkstemp()
            os.close(hdl)
            hdl, self.response_file = tempfile.mkstemp()
            os.close(hdl)
            hdl, self.response_once_file = tempfile.mkstemp()
            os.close(hdl)
            hdl, self.config_file = tempfile.mkstemp()
            os.close(hdl)
            print('Request file: %s' % self.request_file)
            print('Response file: %s' % self.response_file)
            print('Response_once file: %s'
                  % self.response_once_file)
            print('config file: %s' % self.config_file)
        if role == 'server' and engine == 'subprocess':
            self.request_file = kwargs['request_file']
            self.response_file = kwargs['response_file']
            self.response_once_file = kwargs['response_once_file']
            self.config_file = kwargs['config_file']
        if engine == 'subprocess':
            self.request_lock_file = self.request_file + '.lock'
            self.response_lock_file = self.response_file + '.lock'
            self.response_once_lock_file = self.response_once_file + '.lock'
            self.config_lock_file = self.config_file + '.lock'
        self._locks = {
            'request_handler': Semaphore(),
            'request_file': (FileLock(self.request_lock_file)
                             if self.request_file else None),
            'response_file': (FileLock(self.response_lock_file)
                              if self.response_file else None),
            'response_once_file': (FileLock(self.response_once_lock_file)
                                   if self.response_once_file else None),
            'config_file': (FileLock(self.config_lock_file)
                            if self.config_file else None),
        }
        self._config = {
            'port': self.port,
        }
        self.reset()

    def save_state(self, keys=None):
        if self._engine == 'subprocess':
            if keys is None:
                keys = ('request', 'response', 'response_once')
            for key in keys:
                attr = '%s_file' % key
                with self._locks[attr].acquire(timeout=-1):
                    state = bytes_to_unicode(getattr(self, '_%s' % key))
                    with open(getattr(self, attr), 'w') as out:
                        json.dump(state, out)

    def load_state(self, keys=None):
        if self._engine == 'subprocess':
            if keys is None:
                keys = ('request', 'response', 'response_once')
            for key in keys:
                attr = '%s_file' % key
                with self._locks[attr].acquire(timeout=-1):
                    with open(getattr(self, attr)) as inp:
                        content = inp.read()
                    state = prepare_loaded_state(key, json.loads(content))
                    setattr(self, '_%s' % key, state)

    def save_response_state(self):
        self.save_state(['response', 'response_once'])

    def load_response_state(self):
        self.load_state(['response', 'response_once'])

    def save_request_state(self):
        self.save_state(['request'])

    def load_request_state(self):
        self.load_state(['request'])

    def get_response(self, key):
        """
        Load response state and return value of specified key
        """
        self.load_response_state()
        return self._response[key]

    def get_response_once(self, key):
        """
        Load response_once state and return value of specified key
        """
        self.load_response_state()
        return self._response_once[key]

    def get_request(self, key):
        """
        Load request state and return value of specified key
        """
        self.load_request_state()
        return self._request[key]

    def set_response(self, key, val):
        """
        Change response and save it state to file
        """
        self._response[key] = val
        self.save_response_state()


    def set_response_once(self, key, val):
        """
        Change response_once and save it state to file
        """
        self._response_once[key] = val
        self.save_response_state()

    def set_request(self, key, val):
        """
        Set request state and save its state
        """
        self._request[key] = val
        self.save_request_state()

    def reset(self):
        self._request.clear()
        self._request.update({
            'args': {},
            'headers': {},
            'cookies': None,
            'path': None,
            'method': None,
            'charset': 'UTF-8',
            'data': None,
            'files': {},
            'client_ip': None,
            'done': False,
        })
        self._response.clear()
        self._response.update({
            'code': 200,
            'data': '',
            'headers': [],
            'cookies': [],
            'callback': None,
            'sleep': None,
        })
        self._response_once.clear()
        self.save_request_state()
        self.save_response_state()

    def _build_web_app(self):
        """Build tornado web application that is served by
        HTTP server"""
        return tornado.web.Application([
            (r"^.*", TestServerRequestHandler, {'test_server': self}),
        ])

    def main_loop_function(self, keep_alive=False):
        """
        Ask HTTP server start processing requests.

        This is function that is executed in separate thread:
        * start HTTP server
        * start tornado loop
        """
        self.ioloop.make_current()
        socket = None
        if self.port == 0:
            socket = bind_sockets(0, self.address,
                                  family=AF_INET)[0]
            self.port = int(socket.getsockname()[1])
            self._config['port'] = self.port

        if self._engine == 'subprocess':
            self.save_state(['config'])

        app = self._build_web_app()
        #app.listen_port = self.port
        server = HTTPServer(app, no_keep_alive=not keep_alive)

        try_limit = 10
        try_pause = 1 / float(try_limit)
        for count in range(try_limit):
            try:
                if socket:
                    server.add_sockets([socket])
                else:
                    server.listen(self.port, self.address)
            except OSError:
                if count == (try_limit - 1):
                    raise
                else:
                    logging.debug('Socket %s:%d is busy, '
                                  'waiting %.2f seconds.',
                                  self.address, self.port, try_pause)
                    time.sleep(0.1)
            else:
                break

            logger.debug('Listening on port %d', self.port)

        try:
            self.ioloop.start()
        finally:
            # manually close sockets to be able to create
            # other HTTP servers on same sockets
            server.stop()

    def start(self, keep_alive=False, daemon=True):
        """Start the HTTP server."""
        if self._engine == 'thread' or self._role == 'server':
            self._thread = Thread(target=self.main_loop_function,
                                  args=[keep_alive])
            self._thread.daemon = daemon
            self._thread.start()
        elif self._engine == 'subprocess' and self._role == 'master':
            self._proc = Popen([
                'test_server',
                '%s:%d' % (self.address, self.port),
                '--req', self.request_file,
                '--resp', self.response_file,
                '--resp-once', self.response_once_file,
                '--config', self.config_file,
            ])

            def kill_child():
                try:
                    os.kill(self._proc.pid, signal.SIGINT)
                except OSError:
                    pass

            atexit.register(kill_child)
            atexit.register(self.remove_temp_files)
        else:
            raise Exception('Should not be raised ever')

        if self._role == 'master':
            if self._engine == 'subprocess':
                config_loaded = False
                try_limit = 50
                try_pause = 1 / float(try_limit)
                for count in range(try_limit):
                    try:
                        self.load_state(['config'])
                    except ValueError:
                        time.sleep(try_pause)
                    else:
                        config_loaded = True
                        break
                if not config_loaded:
                    raise TestServerError(
                        'Could not load from master process the config file'
                        ' saved by server process'
                    )
                self.port = self._config['port']

            try_limit = 10
            try_pause = 1 / float(try_limit)
            for count in range(try_limit):
                try:
                    urlopen(self.get_url()).read()
                except Exception: # pylint: disable=broad-except
                    if count == (try_limit - 1):
                        raise
                    else:
                        time.sleep(try_pause)
                else:
                    break

            self.reset()

    def stop(self):
        """Stop tornado loop and wait for thread finished it work."""
        if ((self._role == 'master' and self._engine == 'thread')
                or self._role == 'server'):
            self.ioloop.stop()
            self._thread.join()
        if self._role == 'master' and self._engine == 'subprocess':
            kill_process(self._proc.pid)
            self.remove_temp_files()
        #self.is_stopped = True

    def remove_temp_files(self):
        files = (
            self.request_file,
            self.response_file,
            self.response_once_file,
            self.config_file,
            self.request_lock_file,
            self.response_lock_file,
            self.response_once_lock_file,
            self.config_lock_file,
        )
        for file_ in files:
            try:
                os.unlink(file_)
            except OSError:
                pass

    def get_url(self, path='', port=None):
        """Build URL that is served by HTTP server."""
        if port is None:
            port = self.port
        return urljoin('http://%s:%d/' % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.get_request('done'):
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError('No request processed in %d seconds'
                                       % timeout)


def script_test_server():
    try:
        from argparse import ArgumentParser
        import sys

        parser = ArgumentParser()
        parser.add_argument('address')
        parser.add_argument('--req')
        parser.add_argument('--resp')
        parser.add_argument('--resp-once')
        parser.add_argument('--config')
        opts = parser.parse_args()
        if opts.req is None:
            sys.stderr.write('Option --req is not specified\n')
            sys.exit(1)
        if opts.resp is None:
            sys.stderr.write('Option --resp is not specified\n')
            sys.exit(1)
        if opts.resp_once is None:
            sys.stderr.write('Option --resp-once is not specified\n')
            sys.exit(1)
        if opts.config is None:
            sys.stderr.write('Option --config is not specified\n')
            sys.exit(1)
        host, port = opts.address.split(':')
        port = int(port)
        server = TestServer(address=host,
                            port=port,
                            request_file=opts.req,
                            response_file=opts.resp,
                            response_once_file=opts.resp_once,
                            config_file=opts.config,
                            engine='subprocess',
                            role='server')
        server.start()
        server.reset()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Do not throw exception to console becuase
        # it could came as standard shutdown signal
        # from master process
        sys.exit(1)
