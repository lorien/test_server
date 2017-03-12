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
from test_server.container import CallbackDict

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


def bytes_to_unicode(obj, charset):
    if isinstance(obj, six.text_type):
        return obj
    elif isinstance(obj, six.binary_type):
        return obj.decode(charset)
    elif isinstance(obj, list):
        return [bytes_to_unicode(x, charset) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(bytes_to_unicode(x, charset) for x in obj)
    elif isinstance(obj, dict):
        return dict(bytes_to_unicode(x, charset) for x in obj.items())
    else:
        return obj


def prepare_loaded_state(state_key, state, charset, fix_headers=True):
    """
    Fix state loaded from JSON-serialized data:
    * all values of data keys have to be converted to <bytes> strings
    * headers should be converted to tornado.httputil.HTTPHeaders
    """
    if 'data' in state:
        if state['data'] is not None:
            state['data'] = state['data'].encode(charset)
    for key in list(state.keys()):
        if key.endswith('.data'):
            if state[key] is not None:
                state[key] = state[key].encode(charset)
    if state_key == 'request':
        if fix_headers:
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

        if method_key in self._server.response_once:
            value = self._server.response_once[method_key]
            if clear_once:
                del self._server.response_once[method_key]
                self._server.save_state(['response_once'])
            return value
        elif key in self._server.response_once:
            value = self._server.response_once[key]
            if clear_once:
                del self._server.response_once[key]
                self._server.save_state(['response_once'])
            return value
        elif method_key in self._server.response:
            return self._server.response[method_key]
        elif key in self._server.response:
            return self._server.response[key]
        else:
            raise TestServerError('Parameter %s does not exists in '
                                  'server response data' % key)

    def decode_argument(self, value, **kwargs):
        # pylint: disable=unused-argument
        return value.decode(self._server.request['charset'])

    @tornado.web.asynchronous
    @tornado.gen.engine
    def request_handler(self):
        from test_server import __version__

        # load request state
        # required to track request['charset'] if it is set
        self._server.request.read_callback()

        # FIXME
        # load response state?? could be same issue as with
        # request['charset']

        with (yield self._server._locks['request_handler'].acquire()):
            # Remove some standard tornado headers
            for key in ('Content-Type', 'Server'):
                if key in self._headers:
                    del self._headers[key]

            method = self.request.method.lower()

            sleep = self.get_param('sleep', method)
            if sleep:
                yield tornado.gen.Task(self._server.ioloop.add_timeout,
                                       time.time() + sleep)
            self._server.request['client_ip'] = self.request.remote_ip
            self._server.request['args'] = {}
            for key in self.request.arguments.keys():
                self._server.request['args'][key] = self.get_argument(key)
            if self._server._engine == 'subprocess':
                self._server.request['headers'] = (
                    list(self.request.headers.get_all())
                )
            else:
                self._server.request['headers'] = self.request.headers
            self._server.request['path'] = self.request.path
            self._server.request['method'] = self.request.method

            cookies = {}
            for key, cookie in self.request.cookies.items():
                cookies[key] = dict(cookie)
                cookies[key]['name'] = cookie.key
                cookies[key]['value'] = cookie.value
            self._server.request['cookies'] = cookies

            self._server.request['data'] = self.request.body
            self._server.request['files'] = self.request.files

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
                        response['data'] = b'data generator has no more data'
                else:
                    raise TestServerError('Data parameter should '
                                          'be string or iterable '
                                          'object')

                header_keys = [x[0].lower() for x in response['headers']]
                if 'content-type' not in header_keys:
                    response['headers'].append(
                        ('Content-Type', 'text/html; charset=%s'
                         % self._server.response['charset'])
                    )
                if 'server' not in header_keys:
                    response['headers'].append(
                        ('Server', 'TestServer/%s' % __version__))

                self.set_status(response['code'])
                for key, val in response['headers']:
                    self.add_header(key, val)
                self.write(response['data'])

            self._server.request['done'] = True

            if not callback:
                self.finish()

    get = post = put = patch = delete = options = request_handler


# pylint: disable=abstract-method
class StateCallbackDict(CallbackDict):
    def __init__(self, server, state):
        self.server = server
        self.state = state
        super(StateCallbackDict, self).__init__()

    def write_callback(self):
        self.server.save_state([self.state])

    def read_callback(self):
        self.server.load_state([self.state])
# pylint: enable=abstract-method


class TestServer(object):
    def __init__(self, port=0, address='127.0.0.1',
                 engine='thread', role='master', **kwargs):
        assert engine in ('thread', 'subprocess')
        self.request = StateCallbackDict(self, 'request')
        self.response = StateCallbackDict(self, 'response')
        self.response_once = StateCallbackDict(self, 'response_once')
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
            #print('Request file: %s' % self.request_file)
            #print('Response file: %s' % self.response_file)
            #print('Response_once file: %s'
            #      % self.response_once_file)
            #print('config file: %s' % self.config_file)
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
        self.config = StateCallbackDict(self, 'config')
        self.config.update({
            'port': self.port,
        })
        self.reset()

    def save_state(self, keys=None):
        if self._engine == 'subprocess':
            if keys is None:
                keys = ('request', 'response', 'response_once')
            for key in keys:
                attr = '%s_file' % key
                with self._locks[attr].acquire(timeout=-1):
                    obj = getattr(self, key)
                    with obj.disable_callbacks():
                        state = obj.get_dict()

                    if key == 'request':
                        charset_state = 'request'
                    else:
                        charset_state = 'response'
                    charset_obj = getattr(self, charset_state)
                    with charset_obj.disable_callbacks():
                        try:
                            charset = state['charset']
                        except KeyError:
                            try:
                                charset = charset_obj['charset']
                            except KeyError:
                                charset = 'utf-8'

                    #if key == 'request':
                    #    print('----- save begins -------------------------')
                    #    print('STATE', state)
                    #    print('CHARSET', charset)
                    #    traceback.print_stack()
                    #    print('----- save ends -------------------------')
                    with obj.disable_callbacks():
                        state_prep = bytes_to_unicode(state, charset)
                    with open(getattr(self, attr), 'w') as out:
                        json.dump(state_prep, out)

    def load_state(self, keys=None):
        if self._engine == 'subprocess':
            if keys is None:
                keys = ('request', 'response', 'response_once')
            for key in keys:
                attr = '%s_file' % key
                with self._locks[attr].acquire(timeout=-1):
                    with open(getattr(self, attr)) as inp:
                        raw_content = inp.read()
                    fix_headers = (self._role == 'master')
                    state = json.loads(raw_content)

                    if key == 'request':
                        charset_state = 'request'
                    else:
                        charset_state = 'response'
                    charset_obj = getattr(self, charset_state)
                    with charset_obj.disable_callbacks():
                        try:
                            charset = state['charset']
                        except KeyError:
                            try:
                                charset = charset_obj['charset']
                            except KeyError:
                                charset = 'utf-8'

                    state_prep = prepare_loaded_state(key, state, charset,
                                                      fix_headers=fix_headers)
                    #if key == 'request':
                    #    print('----- load begins -------------------------')
                    #    print('STATE', state_prep)
                    #    print('CHARSET', charset)
                    #    traceback.print_stack()
                    #    print('----- load ends -------------------------')
                    obj = getattr(self, key)
                    with obj.disable_callbacks():
                        obj.clear()
                        obj.update(state_prep)

    def reset(self):
        self.request.clear()
        self.request.update({
            'args': {},
            'headers': {},
            'cookies': None,
            'path': None,
            'method': None,
            'data': None,
            'files': {},
            'client_ip': None,
            'done': False,
            'charset': 'utf-8',
        })
        #print('.reset(): just reset the request!')
        #print('.reset(): content of request: %s' % self.request.get_dict())
        #print('.reset(): content of request file: %s'
        #      % open(self.request_file).read())
        self.response.clear()
        self.response.update({
            'code': 200,
            'data': '',
            'headers': [],
            'cookies': [],
            'callback': None,
            'sleep': None,
            'charset': 'utf-8',
        })
        self.response_once.clear()

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
        if self.port == 0:
            socket = bind_sockets(0, self.address, family=AF_INET)[0]
            self.port = int(socket.getsockname()[1])
            self.config['port'] = self.port
        else:
            socket = bind_sockets(self.port, self.address, family=AF_INET)[0]

        app = self._build_web_app()
        server = HTTPServer(app, no_keep_alive=not keep_alive)

        try_limit = 10
        try_pause = 1 / float(try_limit)
        for count in range(try_limit):
            try:
                server.add_sockets([socket])
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
                        self.config['port']
                    except ValueError:
                        time.sleep(try_pause)
                    else:
                        if self.config['port'] != 0:
                            config_loaded = True
                            break
                        else:
                            time.sleep(try_pause)
                if not config_loaded:
                    raise TestServerError(
                        'Could not load from master process the config file'
                        ' saved by server process'
                    )
                self.port = self.config['port']

            try_limit = 10
            try_pause = 1 / float(try_limit)
            for count in range(try_limit):
                try:
                    urlopen(self.get_url() + '?method=start').read()
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
            #req = self.request.get_dict()
            if self.request['done']:
            #if req['done']:
                #print('wait_request [timeout=%s]: req is done: %s'
                #      % (timeout, req))
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
